## ADDED Requirements

### Requirement: BBI indicator computation
系统 SHALL 在规则评估前计算 BBI（多空指标）并传递给规则。BBI = (MA3 + MA6 + MA12 + MA24) / 4，使用日线 close 价格计算。

#### Scenario: BBI computed with sufficient data
- **WHEN** 日线数据至少有 24 个交易日
- **THEN** `market.indicators.bbi` 包含当日 BBI 值，`market.indicators.bbi_prev` 包含前一日 BBI 值

#### Scenario: BBI with insufficient data
- **WHEN** 日线数据不足 24 个交易日
- **THEN** `market.indicators` 中不包含 `bbi` 键

### Requirement: Yellow line and white line computation
系统 SHALL 计算黄线（短期趋势线）和白线（长期牵牛绳），通过可配置的均线周期计算，默认黄线 = MA13，白线 = MA30。

#### Scenario: Yellow and white lines computed
- **WHEN** 日线数据足够计算对应均线
- **THEN** `market.indicators.yellow_line` 包含黄线值，`market.indicators.white_line` 包含白线值

#### Scenario: Insufficient data for moving averages
- **WHEN** 日线数据不足以计算指定周期均线
- **THEN** `market.indicators` 中不包含对应的线值

### Requirement: Volume ratio computation
系统 SHALL 计算量比（当日成交量 / 近 20 日平均成交量）和 20 日均量。

#### Scenario: Volume ratio computed
- **WHEN** 日线数据至少有 20 个交易日且有当日成交量
- **THEN** `market.indicators.volume_ratio` 包含当日量比值，`market.indicators.avg_volume_20d` 包含 20 日均量

#### Scenario: Insufficient data for volume ratio
- **WHEN** 日线数据不足 20 个交易日
- **THEN** `market.indicators` 中不包含量比相关键

### Requirement: N-structure local low detection
系统 SHALL 检测最近的N型结构前低（局部最低点），用于N型结构破止损规则。

#### Scenario: Local low detected
- **WHEN** 日线数据中有足够数据形成局部极值
- **THEN** `market.indicators.n_structure_low` 包含最近的波段低点价格，`market.indicators.n_structure_low_date` 包含该低点日期

#### Scenario: No clear local low found
- **WHEN** 数据不足以检测局部极值（如持续上涨无回调）
- **THEN** `market.indicators` 中不包含 `n_structure_low` 键

### Requirement: Daily DataFrame passed to market
系统 SHALL 在 market 字典中传递最近 N 日（默认 60 日）日线 DataFrame，供规则直接使用。

#### Scenario: Daily DataFrame available
- **WHEN** 日线数据存在
- **THEN** `market.daily_df` 为 pandas DataFrame，包含 open/close/high/low/volume 列，按日期升序排列

#### Scenario: No daily data
- **WHEN** 该 symbol 无日线数据文件
- **THEN** `market.daily_df` 为 None
