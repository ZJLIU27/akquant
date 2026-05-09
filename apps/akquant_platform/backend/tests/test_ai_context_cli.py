"""Tests for AI position context export CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
POSITIONS_CLI = REPO_ROOT / "scripts" / "positions_cli.py"


def _write_config(tmp_path: Path, positions_file: Path) -> Path:
    daily_dir = tmp_path / "daily"
    intraday_dir = tmp_path / "intraday"
    workspace_dir = tmp_path / "workspace"
    registry_file = workspace_dir / "registry.yaml"
    daily_dir.mkdir()
    intraday_dir.mkdir()
    workspace_dir.mkdir()
    registry_file.write_text("position_rule_registry: {}\n", encoding="utf-8")

    config_file = tmp_path / "platform.yaml"
    config_file.write_text(
        "\n".join(
            [
                f"workspace_dir: {json.dumps(str(workspace_dir))}",
                f"registry_file: {json.dumps(str(registry_file))}",
                f"daily_data_dir: {json.dumps(str(daily_dir))}",
                f"intraday_data_dir: {json.dumps(str(intraday_dir))}",
                f"positions_file: {json.dumps(str(positions_file))}",
                "timezone: Asia/Shanghai",
            ]
        ),
        encoding="utf-8",
    )
    return config_file


def _write_daily_data(tmp_path: Path, symbol: str = "000001", rows: int = 130) -> None:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    df = pd.DataFrame(
        {
            "open": [10.0 + i * 0.01 for i in range(rows)],
            "close": [10.1 + i * 0.01 for i in range(rows)],
            "high": [10.2 + i * 0.01 for i in range(rows)],
            "low": [9.9 + i * 0.01 for i in range(rows)],
            "volume": [1000000.0] * (rows - 1) + [1300000.0],
        },
        index=dates,
    )
    df.to_parquet(tmp_path / "daily" / f"{symbol}.parquet")


def _run_cli(config_file: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(POSITIONS_CLI),
            "--config",
            str(config_file),
            "ai-context",
            *args,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_ai_context_symbol_exports_json(tmp_path: Path):
    positions_file = tmp_path / "positions.yaml"
    config_file = _write_config(tmp_path, positions_file)
    positions_file.write_text(
        """
positions:
  - id: position-000001
    symbol: '000001'
    name: 平安银行
    strategy_id: trend_following_breakout
    strategy_tags: [趋势, 突破]
    strategy_note_paths: ['策略/趋势策略.md']
    notes: 观察仓
    rules:
      - id: rule-1
        category: risk
        type: script
        script_id: missing_rule
        strategy_id: trend_following_breakout
        enabled: true
        params: {}
    transactions:
      - id: tx-1
        side: buy
        trade_date: '2026-05-08'
        quantity: 1000
        price: 10.5
        fee: 5.0
        source: manual
        tags: [initial]
        notes: 突破后小仓位观察
        created_at: '2026-05-08T10:30:00+08:00'
        updated_at: '2026-05-08T10:30:00+08:00'
        revision: 1
        voided: false
    audit_log: []
""",
        encoding="utf-8",
    )
    daily_df = pd.DataFrame(
        {"close": [11.2]},
        index=pd.to_datetime(["2026-05-08"]),
    )
    daily_df.to_parquet(tmp_path / "daily" / "000001.parquet")

    result = _run_cli(config_file, "--symbol", "000001")
    payload = json.loads(result.stdout)

    assert payload["schema_version"] == 1
    assert payload["symbol"] == "000001"
    assert payload["position"]["status"] == "open"
    assert payload["position"]["id"] == "position-000001"
    assert payload["position"]["strategy_id"] == "trend_following_breakout"
    assert payload["position"]["strategy_tags"] == ["趋势", "突破"]
    assert payload["position"]["strategy_note_paths"] == ["策略/趋势策略.md"]
    assert payload["position"]["trade_plan"]["obsidian_note_path"] == "策略/趋势策略.md"
    assert "rule_application_state" in payload["position"]
    assert payload["technical_summary"]["status"] == "ok"
    assert payload["position"]["quantity"] == 1000
    assert payload["position"]["holding_days"] is not None
    assert payload["position"]["latest_price"] == 11.2
    assert payload["position"]["price_source"] == "daily_fallback"
    assert payload["transactions"][0]["id"] == "tx-1"
    assert payload["rule_results"][0]["category"] == "risk"
    assert payload["rule_results"][0]["strategy_id"] == "trend_following_breakout"
    assert payload["data_warnings"][0].startswith("rule error: missing_rule")


def test_ai_context_symbol_include_daily_and_plan_fields(tmp_path: Path):
    positions_file = tmp_path / "positions.yaml"
    config_file = _write_config(tmp_path, positions_file)
    (tmp_path / "workspace" / "position_rules").mkdir()
    (tmp_path / "workspace" / "position_rules" / "always_normal.py").write_text(
        """
def evaluate(position, market, params):
    return {"status": "normal", "level": "info", "message": "ok"}
""",
        encoding="utf-8",
    )
    (tmp_path / "workspace" / "registry.yaml").write_text(
        """
position_rule_registry:
  always_normal:
    title: 常规检查
    module: position_rules.always_normal
    function: evaluate
    params_schema: []
  yellow_line_break:
    title: 黄线破止损
    module: position_rules.missing
    function: evaluate
    params_schema: []
""",
        encoding="utf-8",
    )
    positions_file.write_text(
        """
positions:
  - id: position-000001
    symbol: '000001'
    name: 平安银行
    buy_reason: B1反包黄线
    expected_level: 日线
    initial_stop_loss: 10.8
    target_price: 13.5
    allow_t: true
    max_holding_days: 20
    obsidian_note_path: '交易/000001.md'
    rules:
      - id: rule-1
        category: risk
        type: script
        script_id: always_normal
        enabled: true
        params: {}
    transactions:
      - id: tx-1
        side: buy
        trade_date: '2026-05-08'
        quantity: 1000
        price: 10.5
        fee: 5.0
        source: manual
        tags: []
        notes: ''
        created_at: '2026-05-08T10:30:00+08:00'
        updated_at: '2026-05-08T10:30:00+08:00'
        revision: 1
        voided: false
    audit_log: []
""",
        encoding="utf-8",
    )
    _write_daily_data(tmp_path)

    result = _run_cli(
        config_file, "--symbol", "000001", "--include-daily", "--days", "120"
    )
    payload = json.loads(result.stdout)

    assert payload["position"]["trade_plan"] == {
        "buy_reason": "B1反包黄线",
        "expected_level": "日线",
        "initial_stop_loss": 10.8,
        "target_price": 13.5,
        "allow_t": True,
        "max_holding_days": 20,
        "obsidian_note_path": "交易/000001.md",
    }
    assert payload["market"]["daily"]["rows"] == 120
    assert payload["market"]["daily"]["data"][-1]["bbi"] is not None
    assert payload["market"]["daily"]["data"][-1]["yellow_line"] is not None
    assert payload["market"]["daily"]["data"][-1]["white_line"] is not None
    assert payload["market"]["daily_indicators"]["bbi"] is not None
    assert payload["technical_summary"]["above_yellow_line"] is True
    assert payload["technical_summary"]["distance_to_stop_loss_pct"] is not None
    assert payload["technical_summary"]["return_3d_pct"] is not None
    assert payload["technical_summary"]["volume_status"] == "放量"
    state = payload["position"]["rule_application_state"]
    assert state["mounted"][0]["script_id"] == "always_normal"
    assert state["available_unmounted"][0]["script_id"] == "yellow_line_break"
    assert payload["rule_results"][0]["script_id"] == "always_normal"


def test_ai_context_all_open_includes_full_rule_results(tmp_path: Path):
    positions_file = tmp_path / "positions.yaml"
    config_file = _write_config(tmp_path, positions_file)
    positions_file.write_text(
        """
positions:
  - id: position-000001
    symbol: '000001'
    name: 平安银行
    rules:
      - id: rule-1
        category: risk
        type: script
        script_id: missing_rule
        enabled: true
        params: {}
    transactions:
      - id: tx-1
        side: buy
        trade_date: '2026-05-08'
        quantity: 1000
        price: 10.5
        fee: 5.0
        source: manual
        tags: []
        notes: ''
        created_at: '2026-05-08T10:30:00+08:00'
        updated_at: '2026-05-08T10:30:00+08:00'
        revision: 1
        voided: false
    audit_log: []
""",
        encoding="utf-8",
    )
    _write_daily_data(tmp_path, rows=130)

    result = _run_cli(config_file, "--all-open", "--include-rule-results")
    payload = json.loads(result.stdout)

    assert payload["positions"][0]["rule_results"][0]["script_id"] == "missing_rule"
    assert payload["positions"][0]["rule_results"][0]["status"] == "error"
    assert "rule_application_state" in payload["positions"][0]
    assert "technical_summary" in payload["positions"][0]


def test_ai_context_all_open_is_read_only_when_positions_file_missing(tmp_path: Path):
    positions_file = tmp_path / "missing_positions.yaml"
    config_file = _write_config(tmp_path, positions_file)

    result = _run_cli(config_file, "--all-open")
    payload = json.loads(result.stdout)

    assert payload["schema_version"] == 1
    assert payload["positions"] == []
    assert payload["portfolio_summary"]["open_position_count"] == 0
    assert not positions_file.exists()
