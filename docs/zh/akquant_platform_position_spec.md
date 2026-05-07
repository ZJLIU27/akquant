# AKQuant 平台持仓与规则 Spec

本文档沉淀本地回测平台第一阶段的持仓、交易流水、分时缓存、规则注册与规则执行规格。实施计划见 `docs/zh/akquant_platform_implementation_plan.md`。

## 1. 配置与目录

平台配置：

```text
configs/platform.example.yaml  # 主仓库跟踪
configs/platform.yaml          # 本地真实配置，忽略
```

推荐配置字段：

```yaml
workspace_dir: "./workspace"
registry_file: "./workspace/registry.yaml"
daily_data_dir: "./data"
intraday_data_dir: "./data/intraday"
positions_file: "./workspace/position_configs/current_positions.yaml"
backtest_output_dir: "./outputs/backtests"
timezone: "Asia/Shanghai"
intraday_cache_ttl_seconds: 300
intraday_cache_retention_days: 7
```

`workspace/` 是用户策略和规则工作区，整体不进入主仓库 Git 跟踪，后续可拆成独立仓库。

```text
workspace/
  registry.yaml
  strategies/
  position_rules/
  position_configs/
  backtest_configs/
```

主仓库保留持仓示例模板：

```text
configs/positions/current_positions.example.yaml
```

真实持仓文件：

```text
workspace/position_configs/current_positions.yaml
```

## 2. 持仓 YAML Schema

每个股票只允许一个 position；多次建仓、清仓都记录到该 position 的 `transactions`。

```yaml
positions:
  - id: "uuid-position-000001"
    symbol: "000001"
    name: "平安银行"
    notes: "银行股观察仓"
    rules:
      - id: "uuid-rule-1"
        category: "risk"
        type: "script"
        script_id: "manual_take_profit_stop_loss"
        enabled: true
        params:
          stop_loss_price: 9.80
    transactions:
      - id: "uuid-tx-1"
        side: "buy"
        trade_date: "2026-05-08"
        quantity: 1000
        price: 10.50
        fee: 5.0
        source: "manual"
        tags: ["initial"]
        notes: "突破后小仓位观察"
        created_at: "2026-05-08T10:30:00+08:00"
        updated_at: "2026-05-08T10:30:00+08:00"
        revision: 1
        voided: false
    audit_log: []
```

字段规则：

- `id` 使用 UUID，position、transaction、rule、audit_log 各自唯一。
- `symbol` 在 positions 中唯一；重复 symbol 是配置错误。
- `side` 第一阶段只支持 `buy` 和 `sell`。
- `trade_date` 只记录日期；同一天多笔交易按 YAML 数组顺序处理。
- `fee` 参与成本和盈亏计算，缺省为 0。
- `source`、`tags`、`notes` 放在 transaction 级别；position 也支持 `notes`。
- `status` 不写入 YAML，由流水自动计算。
- `cash` 第一阶段不管理，不参与持仓页计算。

## 3. 交易与计算规则

交易流水是事实来源，当前持仓由系统计算。

计算规则：

- 成本匹配使用移动加权平均成本。
- 买入时：`cost_amount += price * quantity + fee`。
- 卖出时：`sell_income = price * quantity - fee`，`realized_pnl = sell_income - avg_cost * quantity`。
- 卖出后剩余持仓的平均成本保持为卖出前移动平均成本。
- `voided: true` 的交易不参与持仓计算。
- `remaining_quantity > 0` 视为 `open`。
- `remaining_quantity == 0` 视为 `closed`，页面默认隐藏。
- `remaining_quantity < 0` 或任一 sell 超过当时剩余持仓，视为 `invalid`。

仓位占比：

- 持仓页不考虑现金。
- `position_weight = position_market_value / sum(open_position_market_value)`。

编辑与作废：

- 第一阶段允许新增、编辑、作废交易。
- 编辑交易必须更新 `updated_at`、递增 `revision`，并写入 position 级 `audit_log`。
- 作废交易不物理删除，设置 `voided: true`、`voided_at`、`void_reason`，并写入 `audit_log`。

审计示例：

```yaml
audit_log:
  - id: "uuid-audit-1"
    action: "update_transaction"
    transaction_id: "uuid-tx-1"
    changed_at: "2026-05-08T11:20:00+08:00"
    before:
      price: 10.50
      quantity: 1000
    after:
      price: 10.55
      quantity: 1000
```

## 4. 分时缓存与价格来源

当日分时缓存路径：

```text
data/intraday/{symbol}/{YYYY-MM-DD}.parquet
data/intraday/{symbol}/{YYYY-MM-DD}.meta.json
```

`meta.json`：

```json
{
  "symbol": "000001",
  "trade_date": "2026-05-08",
  "updated_at": "2026-05-08T10:35:20+08:00",
  "source": "akshare",
  "rows": 128,
  "status": "success"
}
```

刷新规则：

- 进入持仓页时检查所有 open 持仓 symbol。
- 当日缓存不存在或超过 5 分钟 TTL 时，后端启动温和更新任务。
- 自动刷新遵守 TTL。
- 手动刷新忽略 TTL，强制刷新全部 open 持仓分时。
- 若已有同类 running 任务，不重复启动，返回已有 `job_id`。
- 每次分时更新后清理 7 日前缓存。
- 新增第一笔 buy 导致某 symbol 从无 open 持仓变成 open 持仓时，自动触发该 symbol 分时刷新。
- 新增 sell、编辑交易、作废交易不触发分时刷新。

最新价来源：

- 优先使用当日分时缓存最后一条价格，标记为 `intraday`。
- 分时缺失时回退到日线缓存最后一个 `close`，标记为 `daily_fallback`。
- 两者都缺失时标记为 `missing`。

## 5. Registry 与 Rules

平台不自动扫描 `workspace/`，只读取显式注册表：

```text
workspace/registry.yaml
```

示例：

```yaml
strategy_registry:
  dual_ma:
    title: "双均线策略"
    module: "strategies.dual_ma"
    class_name: "DualMovingAverageStrategy"
    params_schema:
      - name: "short_window"
        type: "number"
        required: true
        label: "短均线"

position_rule_registry:
  manual_take_profit_stop_loss:
    title: "手动止盈止损"
    module: "position_rules.manual_take_profit_stop_loss"
    function: "evaluate"
    params_schema:
      - name: "stop_loss_price"
        type: "number"
        required: false
        label: "止损价"
```

注册规则：

- 模块路径相对于 `workspace_dir` 导入。
- 运行时临时把 `workspace_dir` 加入 `sys.path`。
- 注册项导入失败时平台仍可启动，该条目标记为 `invalid`。
- 持仓 rule 只允许引用注册过的 `script_id`。
- rule `category` 第一阶段固定为 `risk` / `alert`。
- 前端新增 rule 时从 registry 下拉选择 `script_id`，按轻量 `params_schema` 生成简单表单。
- 第一阶段支持新增和删除 rule，不支持编辑已有 rule。

持仓 rule 示例：

```yaml
rules:
  - id: "uuid-rule-1"
    category: "risk"
    type: "script"
    script_id: "manual_take_profit_stop_loss"
    enabled: true
    params:
      stop_loss_price: 9.80
```

## 6. Rule 执行接口

第一阶段执行 open 持仓上的已启用 rule，只在持仓页加载/刷新时计算，不做通知、不做定时任务。

规则函数接口：

```python
def evaluate(position, market, params):
    return {
        "status": "normal",
        "level": "info",
        "message": "规则说明或触发原因",
    }
```

输入：

- `position`：计算后的持仓汇总、交易流水、盈亏等。
- `market`：最新价、价格来源、当日分时 `DataFrame`；分时缺失时为 `None`。
- `params`：rule 中保存的参数。

返回最小 schema：

```python
{
    "status": "normal" | "triggered" | "unknown",
    "level": "info" | "warning" | "danger",
    "message": "规则说明或触发原因"
}
```

允许额外字段，例如 `details`。如果脚本抛异常或返回缺少必要字段，该 rule 标记为：

```text
status = error
level = danger
message = 错误摘要
```

单条 rule 失败不影响整个持仓页加载。

## 7. CLI 与 API 边界

基础持仓 CLI：

```text
python scripts/positions_cli.py init
python scripts/positions_cli.py buy --symbol 000001 --name 平安银行 --date 2026-05-08 --quantity 1000 --price 10.50 --fee 5
python scripts/positions_cli.py sell --symbol 000001 --date 2026-05-10 --quantity 500 --price 11.00 --fee 5
python scripts/positions_cli.py list
python scripts/positions_cli.py validate
```

后端 API 最小集合：

```text
GET  /api/positions
GET  /api/positions/{symbol}/intraday
POST /api/positions/{symbol}/transactions
PATCH /api/positions/{symbol}/transactions/{transaction_id}
POST /api/positions/{symbol}/transactions/{transaction_id}/void
POST /api/positions/{symbol}/rules
DELETE /api/positions/{symbol}/rules/{rule_id}
```

CLI 和 FastAPI 必须共用同一套持仓 service、repository、calculator、rules 逻辑。
