## ADDED Requirements

### Requirement: S1 sell signal rule
系统 SHALL 提供 S1 卖出信号规则（s1_sell_signal），检测放量大阴线见顶信号。S1 = 当天出波段最高点 + 放巨量 + 收大阴线 = 明确见顶。

#### Scenario: S1 signal detected - major sell signal
- **WHEN** 最新K线同时满足：收盘为近期（20日）最高点、收大阴线（close < open，跌幅 > 3%）、成交量 >= 近 20 日均量的 2 倍
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明 S1 卖出信号确认，见顶，必须卖出或减仓一半

#### Scenario: Partial S1 - volume spike with bearish candle but not new high
- **WHEN** 最新K线收大阴线且放量，但不是近期新高
- **THEN** 规则返回 `status: "triggered"`, `level: "warning"`, message 说明次高点放量阴线，需警惕

#### Scenario: No S1 signal
- **WHEN** 最新K线不满足 S1 条件
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明暂无卖出信号

#### Scenario: Insufficient data for S1 detection
- **WHEN** 日线数据不足 20 日或缺少成交量数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明数据不足

### Requirement: Support line break monitoring rule
系统 SHALL 提供支撑线破位监控规则（support_line_monitor），综合监控白线和黄线的支撑情况，给出持仓建议。

#### Scenario: Both support lines intact
- **WHEN** 当前价格 > 白线值 > 黄线值（多头排列）
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明双线支撑完好，白线牵牛绳持有

#### Scenario: Price below yellow line
- **WHEN** 当前价格 < 黄线值
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明跌破黄线，清仓（铁律）

#### Scenario: Price between yellow and white line
- **WHEN** 黄线值 >= 当前价格 >= 白线值
- **THEN** 规则返回 `status: "triggered"`, `level: "warning"`, message 说明跌破黄线但未破白线，减仓观察

#### Scenario: Price below white line
- **WHEN** 当前价格 < 白线值
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明跌破白线，建议清仓

#### Scenario: BBI below two bars confirmed
- **WHEN** 最近两根K线的收盘价均在 BBI 下方
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明 BBI 线下两根，一笔交易结束，走人

#### Scenario: Support line data unavailable
- **WHEN** 缺少白线、黄线或 BBI 数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明支撑线数据不足
