# AKQuant 本地回测平台实施计划

## Summary

基于现有 `akquant` 仓库新增一个本地平台：`React + FastAPI` 作为操作界面与后端服务，现有 `scripts/update_data.py` 继续负责日线增量更新，新增当日分时线缓存、持仓管理、交易流水管理和持仓规则展示/执行能力。

第一阶段先完成“持仓管理 + 交易流水维护 + 当日分时线自动缓存 + 持仓规则执行状态展示”，第二阶段接入回测 CLI，第三阶段再接入 Agent 辅助批量回测。

默认保留现有日线数据结构：`data/{symbol}.parquet`。新增分时缓存放在 `data/intraday/{symbol}/{YYYY-MM-DD}.parquet`，保留最近 7 日，超期自动清理。

## Key Changes

### 1. 项目结构

新增平台目录：

```text
apps/akquant_platform/
  backend/
    app/
    tests/
  frontend/
```

新增输出与配置目录：

```text
configs/
  platform.example.yaml
  positions/
    current_positions.example.yaml
  backtests/

outputs/
  backtests/

workspace/
  registry.yaml
  strategies/
  position_rules/
  position_configs/
  backtest_configs/
```

`workspace/` 作为用户策略、持仓规则和真实持仓配置工作区，整体不进入主仓库 Git 跟踪；后续可以拆成独立仓库维护。平台通过 `configs/platform.yaml` 指向 `workspace_dir` 和 `registry_file`。

保留现有日线缓存：

```text
data/
  000001.parquet
  600000.parquet
```

新增当日分时缓存：

```text
data/
  intraday/
    000001/
      2026-05-08.parquet
```

### 2. 持仓管理 v1

真实持仓文件位于 `workspace/position_configs/current_positions.yaml`，主仓库只保留 `configs/positions/current_positions.example.yaml` 作为 schema 示例。

持仓模型采用“每个股票一个 position，交易流水为事实来源”的结构：

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

前端页面提供：

- 持仓列表：代码、名称、数量、移动加权平均成本、最新价、市值、已实现盈亏、未实现盈亏、持仓内部占比
- 持仓详情：当日分时线、成本价线、当前价
- 交易流水：新增买入、卖出；编辑已有交易；作废交易，不物理删除
- 规则区域：新增/删除规则，展示并执行已启用规则的状态；不编辑已有规则
- 数据状态：日线最后更新时间、当日分时最后更新时间、价格来源、是否缺失
- 手动刷新按钮：强制刷新全部 open 持仓的当日分时线

持仓计算规则：

- 每个 `symbol` 只允许一个 position；分批建仓/清仓全部进入该 position 的 `transactions`
- `buy/sell` 是第一阶段唯一支持的交易方向
- `trade_date` 只记录日期，同一天多笔交易按 YAML 数组顺序处理
- 成本匹配使用移动加权平均成本
- `fee` 参与成本和盈亏计算，缺省为 0
- `status` 由流水自动计算：`open`、`closed`、`invalid`，不写入 YAML
- 卖出数量超过剩余持仓时判定 invalid，API 返回错误，CLI 拒绝写入
- 仓位占比只按持仓市值内部计算，不考虑现金；第一阶段不管理 `cash`

### 3. 数据更新

日线：

- 继续复用 `scripts/update_data.py`
- FastAPI 只负责调用白名单命令：

```text
python scripts/update_data.py --data-dir ./data --symbols 000001,600000
```

分时线：

- 新增分时更新 CLI，例如：

```text
python scripts/update_intraday_data.py --symbols 000001,600000 --data-dir ./data/intraday
```

行为要求：

- 只下载当日分时线
- 每个 symbol 单独保存为 `data/intraday/{symbol}/{YYYY-MM-DD}.parquet`
- 每个 Parquet 旁边保存 `data/intraday/{symbol}/{YYYY-MM-DD}.meta.json`
- 页面进入持仓管理时自动检查当前持仓标的的当日缓存
- 当日缓存不存在或超过 5 分钟 TTL 时，由后端启动温和更新任务
- 页面先展示已有缓存；更新完成后前端重新拉取
- 手动刷新忽略 TTL，强制刷新全部 open 持仓分时
- 如果已有同类任务 running，不重复启动，直接返回已有 `job_id`
- 每次分时更新后执行清理：删除 7 日前的分时缓存

最新价来源规则：

- 优先使用当日分时缓存最后一条价格，来源标记为 `intraday`
- 分时缺失时回退到日线缓存最后一个 `close`，来源标记为 `daily_fallback`
- 两者都缺失时标记为 `missing`

`meta.json` 示例：

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

### 4. Workspace 与注册表

用户策略和持仓规则放在 `workspace/`，后续可作为独立仓库维护。平台不自动扫描 Python 文件，只读取显式注册表 `workspace/registry.yaml`。

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

注册表规则：

- 模块路径相对于 `workspace_dir` 导入，运行时临时把 `workspace_dir` 加入 `sys.path`
- 注册项导入失败时平台仍可启动，该条目标记为 `invalid` 并展示错误
- 回测 CLI 第二阶段只允许使用 `strategy_id`，从 registry 解析，不允许直接写任意模块路径
- rules 使用 `script_id` 引用已注册持仓规则，不允许 YAML 写任意文件路径

### 5. FastAPI 后端

提供最小 API：

```text
GET  /api/health
GET  /api/positions
GET  /api/positions/{symbol}/intraday
POST /api/positions/{symbol}/transactions
PATCH /api/positions/{symbol}/transactions/{transaction_id}
POST /api/positions/{symbol}/transactions/{transaction_id}/void
POST /api/positions/{symbol}/rules
DELETE /api/positions/{symbol}/rules/{rule_id}
POST /api/data/update-daily
POST /api/data/update-intraday
GET  /api/data/status
GET  /api/jobs/{job_id}
```

任务执行规则：

- 后端不得执行任意 shell 命令
- 只允许调用白名单 CLI：日线更新、分时更新、后续回测 CLI
- 任务状态写入本地 JSON 或 SQLite；v1 默认用 SQLite
- 任务状态包含：`queued/running/success/failed`、开始时间、结束时间、日志路径、错误信息

持仓服务结构：

```text
apps/akquant_platform/backend/app/positions/
  models.py
  repository.py
  calculator.py
  service.py
  rules.py
```

CLI 和 FastAPI 共用上述模块，避免校验和计算规则分裂。

基础持仓 CLI：

```text
python scripts/positions_cli.py init
python scripts/positions_cli.py buy --symbol 000001 --name 平安银行 --date 2026-05-08 --quantity 1000 --price 10.50 --fee 5
python scripts/positions_cli.py sell --symbol 000001 --date 2026-05-10 --quantity 500 --price 11.00 --fee 5
python scripts/positions_cli.py list
python scripts/positions_cli.py validate
```

### 6. React 前端

页面结构：

```text
持仓管理
数据更新
回测任务
报告列表
```

第一阶段只实现：

- 持仓管理页
- 数据状态组件
- 分时线图表
- 数据刷新按钮
- 后端任务状态轮询
- 新增买入/卖出表单
- 编辑交易表单
- 作废交易操作
- 新增/删除 rules，rule 和 category 使用下拉选择

图表使用前端图表库渲染，不把 Plotly HTML 嵌入为主要交互页面。回测报告仍使用 `result.report()` 生成的 HTML 文件展示。

规则 UI：

- `category` 固定为 `risk` / `alert`
- `script_id` 从 `workspace/registry.yaml` 的 `position_rule_registry` 下拉选择
- 前端按 registry 中轻量 `params_schema` 生成简单参数表单
- 第一阶段支持新增和删除 rule，不支持编辑已有 rule
- 每条已启用 rule 在持仓页加载/刷新时执行并显示状态

规则执行接口：

```python
def evaluate(position, market, params):
    return {
        "status": "normal",  # normal | triggered | unknown
        "level": "info",     # info | warning | danger
        "message": "规则说明或触发原因",
    }
```

后端为规则传入：

- `position`：计算后的持仓汇总、交易流水、盈亏等
- `market`：最新价、价格来源、当日分时 `DataFrame`；分时缺失时为 `None`
- `params`：rule 中保存的参数

单条规则执行失败时只将该 rule 标记为 `error`，不影响整个持仓页加载。返回结果缺少必要字段时也标记为 `error`。

### 7. 回测平台 v2

新增标准化回测 CLI：

```text
python scripts/run_backtest_cli.py --config configs/backtests/demo.yaml
```

配置文件包含：

```yaml
strategy_id: "dual_ma"
symbols: ["000001"]
data_dir: "./data"
start_time: "2020-01-01"
end_time: "2026-05-08"
initial_cash: 100000
commission_rate: 0.0003
stamp_tax_rate: 0.001
params:
  short_window: 5
  long_window: 20
```

输出目录：

```text
outputs/backtests/{run_id}/
  config.yaml
  status.json
  stdout.log
  metrics.csv
  orders.csv
  trades.csv
  positions.csv
  report.html
```

FastAPI 后续新增：

```text
POST /api/backtests
GET  /api/backtests
GET  /api/backtests/{run_id}
GET  /api/backtests/{run_id}/report
POST /api/backtests/{run_id}/cancel
```

## Test Plan

- 后端单元测试：
  - 读取 `workspace/position_configs/current_positions.yaml` 并正确计算数量、移动平均成本、市值、已实现盈亏、未实现盈亏、持仓内部占比
  - 同一 symbol 多个 position 判定配置错误
  - `sell` 超过剩余持仓判定 invalid，CLI 拒绝写入
  - 编辑交易会增加 revision，并写入 audit_log 的 before/after
  - 作废交易不物理删除，计算时忽略，并写入 audit_log
  - rules 只能引用 registry 中注册过的 `script_id`
  - 单条 rule 执行失败时只返回该 rule 的 error 状态
  - 当日分时缓存存在时直接读取，不重复触发下载
  - 当日分时缓存缺失时创建更新任务
  - 当日分时缓存 5 分钟 TTL 内不自动重复下载
  - 手动刷新会忽略 TTL，但不会重复启动同类 running 任务
  - 7 日前分时缓存会被清理
  - 非白名单命令无法被任务执行器调用
- CLI 测试：
  - `scripts/update_data.py` 现有日线更新行为不被破坏
  - 新增分时 CLI 能为指定 symbol 写入标准 Parquet
  - `positions_cli.py buy/sell/list/validate` 与后端 service 计算一致
  - 回测 CLI 第二阶段能通过 `strategy_id` 读取 registry 并输出完整结果目录
- 前端测试：
  - 持仓表格字段展示正确
  - 点击持仓后加载对应当日分时线
  - 分时数据缺失时显示明确提示
  - 刷新任务运行中时禁用重复提交
  - 新增买入/卖出后持仓计算刷新
  - 编辑交易后审计字段更新
  - 作废交易后持仓计算忽略该交易
  - 新增/删除 rule 后页面状态刷新
- 端到端验收：
  - 启动 FastAPI 与 React 后，可以打开持仓管理页
  - 页面不依赖实时 AkShare 访问即可展示已有缓存
  - 点击刷新后可更新当日分时线并落盘
  - 超过 7 日的分时缓存会自动删除
  - 可以通过前端新增买入/卖出、编辑交易、作废交易
  - 可以通过前端新增/删除 rule，并看到 rule 执行状态
  - 第二阶段可以通过页面发起一次回测并打开 `report.html`

## Assumptions

- 现有 `data/{symbol}.parquet` 是日线缓存主目录，不在第一阶段迁移到 `data/akshare_daily/`。
- 真实持仓来源使用 `workspace/position_configs/current_positions.yaml`，不接券商、不接实盘账户。
- 主仓库保留 `configs/positions/current_positions.example.yaml` 作为 schema 示例。
- `workspace/` 整体不进入主仓库 Git 跟踪，后续可拆成独立仓库。
- 当日分时线只服务持仓管理页面，不用于日线回测。
- 自动分时刷新 TTL 为 5 分钟。
- 分时缓存保留 7 日是硬规则，暂不做页面配置。
- 第一阶段不管理现金，持仓占比只按持仓市值内部计算。
- 第一阶段回测 CLI 不实现，放到第二阶段。
- v1 只做本地单用户平台，不做权限、云部署、实盘下单、消息通知、定时规则任务。
- Agent 是增强入口，可调用标准 CLI；平台核心能力不依赖 Agent。
