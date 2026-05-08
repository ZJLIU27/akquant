## Why

持仓管理平台规则引擎需要实现基于"少妇战法"的完整交易规则体系。当前仅有一条手动止盈止损规则，无法覆盖实际交易中的止损五原则（BBI破、黄线破、N型结构破、横盘三天拍、止盈放飞）、防卖飞策略（阶梯减仓）、以及 S1 卖出信号检测。这些规则依赖 BBI 线、黄线、白线等技术指标，需要先建立指标计算基础设施，再在此基础上实现具体规则。

## What Changes

- 新增指标计算层：在 service 层预计算 BBI、黄线、白线、N型结构、量比等技术指标，通过 market 字典传递给规则
- 实现止损规则组（4条）：
  - BBI破止损：连续两天收盘跌破BBI线 → 趋势反转信号
  - 黄线破止损：跌破黄线 → 必卖铁律
  - N型结构破止损：跌破N型前低 → 主力控盘失败
  - 横盘三天止损：买入后三天无涨无跌 → 市场未证明你是对的
- 实现止盈规则组（2条）：
  - 止盈放飞：BBI线上出现两根中大阳线 → 减仓一半
  - 四分之三阴量线：突破后出现下跌且量=突破日75% → 假突破警告
- 实现卖出信号规则（1条）：
  - S1卖出信号：放量大阴线见顶检测
- 增强 `market` 数据传递：新增 `daily_df`（日线行情）、`indicators`（预计算指标）字段
- 注册表支持 `string`、`boolean`、`select` 参数类型

## Capabilities

### New Capabilities
- `indicator-computation`: 技术指标计算层，为规则提供 BBI、黄线、白线、N型结构、量比等预计算指标
- `stop-loss-rules`: 止损五原则规则组（BBI破、黄线破、N型结构破、横盘三天、含浮盈宽限逻辑）
- `take-profit-rules`: 防卖飞策略规则组（止盈放飞、四分之三阴量线）
- `sell-signal-rules`: 卖出信号检测（S1放量大阴线）

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- **后端代码**: `service.py`（market 数据扩展）、`rules.py`（指标传递）
- **新增指标计算**: `apps/akquant_platform/backend/app/positions/indicators.py`
- **新增规则脚本**: `workspace/position_rules/` 下新增 7 条规则
- **注册表**: `workspace/registry.yaml` 注册所有新规则
- **测试**: 新增指标计算测试和规则单元测试
- **数据依赖**: 所有规则依赖日线 OHLCV 数据（已有 `data/{symbol}.parquet`）
