# Agent 主动拉取 AKQuant 持仓数据的执行方案

## Summary

本文档定义“从 GenericAgent 侧手动发起分析，主动拉取 AKQuant 持仓数据，再结合 Obsidian 策略库进行判断”的落地方案。

本方案不让 AKQuant 持仓页直接在线调用 Agent，也不把 Agent 生命周期嵌入 FastAPI。AKQuant 只提供稳定、只读、结构化的数据导出能力；GenericAgent 负责读取 Obsidian 策略依据、调用 AKQuant 数据工具、完成分析，并可选把分析结果写回 `workspace/ai_reviews/`。后续持仓页只读取已落盘的分析记录。

第一阶段目标是手动可用、边界清楚、结果可追溯：

- 在 GenericAgent 对话里输入“分析当前持仓”。
- Agent 调用 AKQuant CLI 获取持仓上下文 JSON。
- Agent 按策略标识读取 Obsidian 策略库，生成结构化分析结论。
- 可选写回 AKQuant `workspace/ai_reviews/`。
- AKQuant 核心持仓、交易、规则计算不依赖 Agent。

## 1. 总体架构

```text
GenericAgent
  -> Obsidian vault
     - 策略依据
     - 复盘记录
     - 持仓规则说明
  -> AKQuant CLI
     - 导出持仓上下文
     - 导出单票或全量 open 持仓
     - 读取规则执行结果和行情快照
  -> Agent 分析
     - 生成 verdict / reasons / risks / evidence
  -> 可选写回
     - workspace/ai_reviews/{YYYY-MM-DD}/{symbol}.json

AKQuant
  -> 不启动 Agent
  -> 不直接读 Obsidian
  -> 只提供只读上下文导出和分析结果读取
```

## 2. 边界原则

- Agent 只读 AKQuant 数据，不直接修改 `current_positions.yaml`。
- Agent 不自动买入、卖出、编辑交易、作废交易。
- Agent 输出是投研辅助结论，不是交易指令。
- AKQuant 侧导出的上下文必须是 JSON，避免 Agent 解析页面文本。
- Obsidian 是策略知识源，优先由 GenericAgent 侧读取和检索。
- 分析结果若写回 AKQuant，只写入 `workspace/ai_reviews/`，不污染持仓事实来源。
- 持仓页后续展示 AI 结果时，只展示已生成记录，不在线等待 Agent 长任务。

## 3. AKQuant 侧改造

### 3.1 新增只读 CLI

在 `scripts/positions_cli.py` 中新增只读命令：

```text
python scripts/positions_cli.py ai-context --symbol 000001 --format json
python scripts/positions_cli.py ai-context --all-open --format json
```

如果后续 `positions_cli.py` 过于臃肿，可以拆为：

```text
python scripts/export_position_context.py --symbol 000001
python scripts/export_position_context.py --all-open
```

第一版优先复用 `positions_cli.py`，避免新增过多入口。

### 3.2 输出 JSON schema

单个持仓导出：

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-09T10:30:00+08:00",
  "source": "akquant",
  "symbol": "000001",
  "position": {
    "id": "uuid-position-000001",
    "symbol": "000001",
    "name": "平安银行",
    "status": "open",
    "strategy_id": "trend_following_breakout",
    "strategy_tags": ["趋势", "突破"],
    "strategy_note_paths": ["策略/趋势策略.md"],
    "quantity": 1000,
    "avg_cost": 10.5,
    "latest_price": 11.2,
    "price_source": "intraday",
    "market_value": 11200.0,
    "realized_pnl": 0.0,
    "unrealized_pnl": 700.0,
    "unrealized_pnl_pct": 6.67,
    "position_weight": 0.25,
    "holding_days": 12,
    "notes": "观察仓"
  },
  "transactions": [
    {
      "id": "uuid-tx-1",
      "side": "buy",
      "trade_date": "2026-05-01",
      "quantity": 1000,
      "price": 10.5,
      "fee": 5.0,
      "source": "manual",
      "tags": ["initial"],
      "notes": "突破后小仓位观察",
      "voided": false
    }
  ],
  "market": {
    "symbol": "000001",
    "latest_price": 11.2,
    "price_source": "intraday",
    "daily_last_date": "2026-05-08",
    "intraday_updated_at": "2026-05-09T10:25:00+08:00",
    "intraday_rows": 128
  },
  "rule_results": [
    {
      "rule_id": "uuid-rule-1",
      "script_id": "manual_take_profit_stop_loss",
      "strategy_id": "trend_following_breakout",
      "category": "risk",
      "status": "normal",
      "level": "info",
      "message": "未触发止损"
    }
  ],
  "data_warnings": []
}
```

全量 open 持仓导出：

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-09T10:30:00+08:00",
  "source": "akquant",
  "positions": [
    {
      "symbol": "000001",
      "name": "平安银行",
      "status": "open",
      "quantity": 1000,
      "avg_cost": 10.5,
      "latest_price": 11.2,
      "unrealized_pnl_pct": 6.67,
      "position_weight": 0.25,
      "rule_summary": {
        "danger": 0,
        "warning": 1,
        "info": 2
      }
    }
  ],
  "portfolio_summary": {
    "open_position_count": 1,
    "total_market_value": 11200.0,
    "total_unrealized_pnl": 700.0
  },
  "data_warnings": []
}
```

### 3.3 导出内容规则

- 只导出计算后的持仓摘要，不让 Agent 重新计算成本。
- `position.strategy_id`、`position.strategy_tags`、`position.strategy_note_paths` 用于定位 Obsidian 策略依据；Agent 不应默认按股票代码或股票名称检索策略笔记。
- `transactions` 保留必要字段，便于 Agent 判断建仓节奏。
- `market` 只给当前分析所需的行情快照，不把完整分时 `DataFrame` 全量塞入上下文。
- `rule_results` 复用现有持仓规则执行结果。
- 缺行情、规则执行失败、持仓 invalid 等问题进入 `data_warnings`。
- CLI 默认只导出 open 持仓；closed 持仓需要显式参数。

### 3.4 AI 分析结果落盘

新增目录：

```text
workspace/
  ai_reviews/
    2026-05-09/
      000001.json
      portfolio.json
```

单票分析结果 schema：

```json
{
  "schema_version": 1,
  "review_id": "uuid-review-1",
  "symbol": "000001",
  "generated_at": "2026-05-09T11:00:00+08:00",
  "agent": {
    "name": "GenericAgent",
    "version": "local"
  },
  "verdict": "hold",
  "confidence": 0.72,
  "summary": "当前未触发止损，趋势仍符合策略持有条件。",
  "reasons": [
    "价格仍高于移动加权平均成本",
    "策略库中该类趋势策略要求跌破关键条件才退出"
  ],
  "risks": [
    "若后续放量跌破止损线，需要重新评估"
  ],
  "suggested_actions": [
    "继续持有",
    "保留现有止损规则"
  ],
  "evidence": [
    {
      "title": "趋势持仓规则",
      "path": "策略/趋势策略.md",
      "section": "退出条件",
      "quote": "..."
    }
  ],
  "missing_metrics": [],
  "akquant_context": {
    "symbol": "000001",
    "generated_at": "2026-05-09T10:30:00+08:00",
    "schema_version": 1
  }
}
```

`verdict` 第一版限定为：

```text
hold | watch | reduce | take_profit | stop_loss | exit | unknown
```

当 Obsidian 策略依据要求的指标在 AKQuant 上下文中不存在时，Agent 不应猜测结论，应返回 `verdict=unknown`，并在 `missing_metrics` 中列出缺口，便于后续在 AKQuant 或其他数据项目中补充查询接口：

```json
{
  "schema_version": 1,
  "symbol": "000001",
  "generated_at": "2026-05-09T11:00:00+08:00",
  "verdict": "unknown",
  "confidence": 0.0,
  "summary": "当前缺少策略判断所需指标，无法形成有效结论。",
  "reasons": [],
  "risks": [],
  "suggested_actions": [],
  "evidence": [
    {
      "title": "趋势持仓规则",
      "path": "策略/趋势策略.md",
      "section": "退出条件",
      "quote": "策略要求价格跌破 20 日均线后重新评估。"
    }
  ],
  "missing_metrics": [
    {
      "metric": "ma20",
      "label": "20 日均线",
      "reason": "Obsidian 策略要求判断当前价格是否跌破 20 日均线。",
      "required_by": {
        "path": "策略/趋势策略.md",
        "section": "退出条件"
      },
      "suggested_provider": "akquant_metric_context"
    }
  ],
  "akquant_context": {
    "symbol": "000001",
    "generated_at": "2026-05-09T10:30:00+08:00",
    "schema_version": 1
  }
}
```

### 3.5 持仓页后续展示

持仓页后续可以增加只读区域：

- 最新 AI 结论
- 生成时间
- 置信度
- 主要理由
- 风险提示
- Obsidian 引用来源

页面不负责触发 Agent。若没有分析记录，展示“暂无 AI 分析记录”。

## 4. GenericAgent 侧改造方案

### 4.1 新增 AKQuant 工具封装

GenericAgent 侧新增一个内部工具或命令封装，建议命名：

```text
akquant_position_context
```

职责：

- 在固定 `cwd=D:/Git/akquant` 下执行 AKQuant CLI。
- 调用 `python scripts/positions_cli.py ai-context ...`。
- 读取 stdout JSON。
- 校验 JSON 是否包含 `schema_version`、`generated_at`、`position` 或 `positions`。
- 将结构化结果返回给 Agent 推理链路。

工具参数：

```json
{
  "symbol": "000001",
  "all_open": false,
  "include_transactions": true,
  "include_rule_results": true
}
```

安全规则：

- 命令白名单固定为 AKQuant 导出 CLI。
- `symbol` 只允许 A 股代码格式，例如 `000001`、`600000`。
- 不允许透传任意 shell 参数。
- 超时建议 30 秒。
- CLI 失败时把 stderr 和退出码作为工具错误返回。

### 4.2 Obsidian 策略上下文工具

GenericAgent 侧配置 Obsidian vault：

```yaml
obsidian:
  vault_path: "D:/Obsidian/TradingNotes"
  include:
    - "策略/**/*.md"
    - "复盘/**/*.md"
    - "持仓规则/**/*.md"
  exclude:
    - ".obsidian/**"
    - "模板/**"
```

GenericAgent 侧新增一个策略上下文工具，建议命名：

```text
obsidian_strategy_context
```

职责：

- 直接调用本地 Obsidian CLI 读取策略依据。
- 优先按 AKQuant 上下文中的 `strategy_id`、`strategy_tags`、`strategy_note_paths` 定位策略文档。
- 不默认按 `symbol` 或股票名称搜索 Obsidian；Obsidian 中保存的是策略依据，不是个股事实库。
- 读取命中的 Markdown 标题、路径、段落文本。
- 返回结构必须保留 `path`、`section`、`text`，供最终 `evidence` 引用。

工具参数：

```json
{
  "strategy_id": "trend_following_breakout",
  "strategy_tags": ["趋势", "突破"],
  "strategy_note_paths": ["策略/趋势策略.md"],
  "query": "退出条件"
}
```

返回示例：

```json
{
  "matches": [
    {
      "title": "趋势持仓规则",
      "path": "策略/趋势策略.md",
      "section": "退出条件",
      "text": "价格跌破 20 日均线后重新评估，若同时放量走弱则考虑减仓。"
    }
  ]
}
```

第二版再做向量索引和增量索引。第一版只要求策略文档可被稳定读取、证据路径可追溯。

### 4.3 指标补充工具

第一版可以不立即实现指标补充工具。若 Obsidian 策略依据要求的指标不在 `akquant_position_context` 返回结果中，Agent 应输出 `missing_metrics`，由用户后续在 AKQuant 或对应数据项目中补充查询接口。

后续可新增一个按需指标工具，建议命名：

```text
akquant_metric_context
```

职责：

- 在固定 `cwd=D:/Git/akquant` 下执行白名单 CLI。
- 按 `symbol` 和指标列表返回结构化 JSON。
- 只提供策略判断所需的指标，不返回整段原始 DataFrame。
- CLI 不存在、指标不支持、数据缺失时，返回明确错误，并允许 Agent 转写为 `missing_metrics`。

工具参数示例：

```json
{
  "symbol": "000001",
  "metrics": ["ma20", "volume_ratio_5d", "atr14"],
  "lookback_days": 60
}
```

返回示例：

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-09T11:05:00+08:00",
  "source": "akquant",
  "symbol": "000001",
  "metrics": {
    "ma20": 10.85,
    "volume_ratio_5d": 1.32
  },
  "missing_metrics": [
    {
      "metric": "atr14",
      "reason": "当前 AKQuant CLI 尚未提供 ATR 指标。"
    }
  ]
}
```

### 4.4 Agent 提示词模板

新增一个固定分析模板：

```text
你是本地投研辅助 Agent。请基于 AKQuant 导出的当前持仓事实、行情/规则数据，以及 Obsidian CLI 读取到的策略依据，判断当前持仓策略是否需要调整。

要求：
1. 不要给出自动交易指令。
2. 不要修改 AKQuant 持仓文件。
3. 结论必须落在 hold/watch/reduce/take_profit/stop_loss/exit/unknown 之一。
4. 必须说明依据来自 AKQuant 数据还是 Obsidian 笔记。
5. Obsidian 笔记是策略依据来源；AKQuant 是持仓事实和指标数据来源。
6. 如果策略要求的指标缺失，返回 unknown，并在 missing_metrics 中列出缺失指标、原因、依据路径和建议的数据提供工具。
7. 输出严格 JSON，不输出 Markdown。
```

### 4.5 Agent 输出 schema

GenericAgent 最终输出应符合 AKQuant `ai_reviews` schema：

```json
{
  "schema_version": 1,
  "symbol": "000001",
  "generated_at": "2026-05-09T11:00:00+08:00",
  "verdict": "hold",
  "confidence": 0.72,
  "summary": "...",
  "reasons": [],
  "risks": [],
  "suggested_actions": [],
  "evidence": [],
  "missing_metrics": [],
  "akquant_context": {
    "symbol": "000001",
    "generated_at": "2026-05-09T10:30:00+08:00",
    "schema_version": 1
  }
}
```

### 4.6 可选写回工具

GenericAgent 侧可以新增：

```text
akquant_write_ai_review
```

职责：

- 写入 `D:/Git/akquant/workspace/ai_reviews/{YYYY-MM-DD}/{symbol}.json`。
- 写入前校验 JSON schema。
- 同一天同一 symbol 可以覆盖最新结果，也可以按 `review_id` 保留历史；第一版建议覆盖最新结果。
- 不写入 `workspace/position_configs/current_positions.yaml`。

如果暂时不做写回工具，也可以先让 Agent 把 JSON 输出到对话中，人工复制或后续再接。

## 5. 执行阶段

### Phase 1: AKQuant 只读上下文导出

目标：

- `positions_cli.py ai-context --symbol 000001 --format json` 可用。
- 能返回持仓、交易、行情、规则执行结果。
- 不触发任何写操作。

验收：

```text
python scripts/positions_cli.py ai-context --symbol 000001 --format json
python scripts/positions_cli.py ai-context --all-open --format json
```

输出能被 `json.loads()` 解析，并包含 `schema_version=1`。

### Phase 2: GenericAgent 工具接入

目标：

- GenericAgent 能通过内部工具调用 AKQuant CLI。
- 能按策略标识调用 Obsidian CLI 读取相关策略依据。
- 能输出符合 schema 的 JSON 分析。
- 策略所需指标不足时，能输出 `missing_metrics`，而不是猜测结论。
- 后续若 `akquant_metric_context` 已实现，Agent 可以按策略需求补取指标；若未实现或指标仍缺失，继续输出 `missing_metrics`。

验收：

```text
分析 AKQuant 当前持仓 000001，参考 Obsidian 策略库。
```

Agent 应先调用 AKQuant 上下文工具，再根据 `strategy_id`、`strategy_tags` 或 `strategy_note_paths` 读取 Obsidian 策略依据，最后输出结构化结果。若 Obsidian 策略要求的指标不在 AKQuant 上下文中，输出 `missing_metrics`。

### Phase 3: 分析结果写回

目标：

- Agent 分析结果写入 `workspace/ai_reviews/`。
- AKQuant 可以读取最新分析记录。

验收：

```text
workspace/ai_reviews/{YYYY-MM-DD}/000001.json
```

文件存在，字段符合 schema，并能在持仓页或 CLI 中读取。

### Phase 4: 持仓页只读展示

目标：

- 持仓详情页展示最新 AI 分析记录。
- 不在页面里同步调用 Agent。

验收：

- 有记录时展示结论、理由、风险、证据。
- 无记录时展示空状态。
- 记录 schema 异常时显示解析错误，不影响持仓页核心展示。

## 6. 测试计划

AKQuant 侧：

- `ai-context --symbol` 输出合法 JSON。
- `ai-context --all-open` 输出合法 JSON。
- closed 持仓默认不出现在 all-open。
- invalid 持仓进入 `data_warnings`。
- 分时缺失时 `price_source=daily_fallback` 或 `missing`。
- 单条 rule 执行失败时只影响对应 `rule_results`。
- CLI 不写入持仓 YAML。

GenericAgent 侧：

- AKQuant 工具只允许白名单命令。
- symbol 参数校验能拒绝异常输入。
- AKQuant CLI 超时时返回明确错误。
- Obsidian 策略读取结果包含路径。
- Obsidian 策略读取不默认依赖股票代码或股票名称。
- 输出 JSON 能通过 schema 校验。
- 缺少策略所需指标时输出 `missing_metrics`，并包含 `required_by.path`。
- 写回工具不会修改 `current_positions.yaml`。

端到端：

- 在 GenericAgent 中输入单票分析请求，能得到结构化结论。
- 分析结果包含 AKQuant 数据时间戳和 Obsidian 引用来源。
- 当策略要求的指标缺失时，分析结果为 `verdict=unknown`，并列出可交给 AKQuant 侧补接口的指标清单。
- 可选写回后，AKQuant 能读取 `workspace/ai_reviews/` 中的最新结果。

## 7. 暂不做

- 不做 AKQuant 调用 GenericAgent。
- 不做 GenericAgent HTTP API。
- 不做自动定时分析。
- 不做交易自动执行。
- 不做 Obsidian 全量向量索引作为第一阶段前置条件。
- 不把 Obsidian vault 内容复制进 AKQuant 仓库。

## 8. 风险与处理

- Agent 输出不是合法 JSON：GenericAgent 侧增加 schema 校验和重试；AKQuant 侧读取失败时只显示错误。
- AKQuant CLI 太慢：先限制导出字段；必要时增加缓存。
- Obsidian 命中依据不足：返回 `unknown`，并列出缺失策略依据。
- AKQuant 上下文缺少策略所需指标：返回 `unknown`，并在 `missing_metrics` 中列出指标名、用途、来源策略段落和建议补充的数据接口。
- 分析结论过度自信：要求 `confidence`，低置信度在 UI 中明确标识。
- 两边 schema 漂移：固定 `schema_version`，变更时同时更新 AKQuant 和 GenericAgent 文档。
