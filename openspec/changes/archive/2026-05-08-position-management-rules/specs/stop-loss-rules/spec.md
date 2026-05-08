## ADDED Requirements

### Requirement: BBI break stop-loss rule
系统 SHALL 提供 BBI 破止损规则（bbi_break_stop_loss），当连续两天收盘跌破 BBI 线时触发，作为基本止损信号，提示趋势反转。

#### Scenario: BBI break triggered - two consecutive days below BBI
- **WHEN** 当日收盘价 < 当日 BBI，且前一日收盘价 < 前一日 BBI
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明连续两天跌破 BBI，趋势反转

#### Scenario: First day below BBI - warning
- **WHEN** 当日收盘价 < 当日 BBI，但前一日收盘价 >= 前一日 BBI
- **THEN** 规则返回 `status: "normal"`, `level: "warning"`, message 说明首日跌破 BBI，需关注

#### Scenario: Price above BBI
- **WHEN** 当日收盘价 >= 当日 BBI
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 包含当前价和 BBI 值

#### Scenario: BBI data unavailable
- **WHEN** market.indicators 中无 BBI 数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明 BBI 数据不足

### Requirement: Yellow line break stop-loss rule
系统 SHALL 提供黄线破止损规则（yellow_line_break），当价格跌破黄线时触发。黄线破是铁律，跌破必卖。

#### Scenario: Yellow line break triggered
- **WHEN** 当日收盘价 < 黄线值
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明已跌破黄线，必须卖出

#### Scenario: Price above yellow line
- **WHEN** 当日收盘价 >= 黄线值
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 包含当前价和黄线值

#### Scenario: With unrealized profit - tolerance
- **WHEN** 当日收盘价 < 黄线值，但持仓有浮盈（unrealized_pnl > 0）
- **THEN** 规则返回 `status: "triggered"`, `level: "warning"`, message 说明跌破黄线但有浮盈可再观察一次

#### Scenario: Yellow line data unavailable
- **WHEN** market.indicators 中无黄线数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明黄线数据不足

### Requirement: N-structure break stop-loss rule
系统 SHALL 提供 N 型结构破止损规则（n_structure_break），当价格跌破 N 型前低时触发，提示主力控盘失败。

#### Scenario: N-structure break triggered
- **WHEN** 当日收盘价 < N型前低价格
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明跌破N型前低，主力控盘失败

#### Scenario: Price above N-structure low
- **WHEN** 当日收盘价 >= N型前低价格
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 包含当前价和N型前低

#### Scenario: N-structure low not detected
- **WHEN** market.indicators 中无 n_structure_low 数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明N型结构数据不足

### Requirement: Sideways three days stop-loss rule
系统 SHALL 提供横盘三天止损规则（sideways_three_days），当买入后连续三个交易日涨跌幅均在 ±1.5% 以内时触发。

#### Scenario: Sideways three days triggered
- **WHEN** 买入日期已过 3 个交易日，这 3 天每日涨跌幅（相对前日收盘）均在 ±1.5% 以内
- **THEN** 规则返回 `status: "triggered"`, `level: "warning"`, message 说明横盘三天无方向，建议退出（亏损 1-1.5% 可走）

#### Scenario: Price has moved within three days
- **WHEN** 买入后 3 个交易日内有任一天涨跌幅超过 ±1.5%
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明市场已有方向

#### Scenario: Holding period less than three days
- **WHEN** 买入后不足 3 个交易日
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明持仓不足三天，继续观察

#### Scenario: No buy transaction found
- **WHEN** 持仓无有效买入交易记录
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明无法确定建仓日期

#### Scenario: No daily data for post-buy period
- **WHEN** 买入日期后的日线数据不足
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明数据不足
