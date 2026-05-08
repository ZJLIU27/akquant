## ADDED Requirements

### Requirement: Take-profit release rule
系统 SHALL 提供止盈放飞规则（take_profit_release），当 BBI 线上方出现两根中大阳线时触发，提示必须减仓一半。中大阳线定义为阳线（close > open）且涨幅 > 3.25%。

#### Scenario: Two bullish candles above BBI
- **WHEN** 最近交易日在 BBI 线上方，且近期出现至少 2 根中大阳线（涨幅 > 3.25%）
- **THEN** 规则返回 `status: "triggered"`, `level: "warning"`, message 说明已出现两根中大阳线，必须放飞一半

#### Scenario: Only one bullish candle above BBI
- **WHEN** 最近在 BBI 线上方仅出现 1 根中大阳线
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明出现第一根阳线，等待确认

#### Scenario: No bullish candles above BBI
- **WHEN** 近期在 BBI 线上方未出现中大阳线
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 包含当前价格和 BBI 关系

#### Scenario: Price below BBI
- **WHEN** 当前价格在 BBI 线下方
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明价格在 BBI 下方，暂不适放飞

#### Scenario: BBI data or daily data unavailable
- **WHEN** 缺少 BBI 数据或日线数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明数据不足

### Requirement: Three-quarter bearish volume line rule
系统 SHALL 提供四分之三阴量线规则（three_quarter_bearish_volume），当突破（创新高）后出现下跌日且成交量达到突破日成交量的 75% 以上时触发，提示假突破风险。

#### Scenario: Bearish volume line detected
- **WHEN** 最近出现过创新高日，之后某日收阴线（close < open）且成交量 >= 创新高日成交量的 75%
- **THEN** 规则返回 `status: "triggered"`, `level: "danger"`, message 说明出现四分之三阴量线，假突破风险大，次日退出

#### Scenario: After breakout but no bearish volume line
- **WHEN** 最近出现过创新高日，但后续交易日未出现符合条件的大成交量阴线
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明突破有效，继续持有

#### Scenario: No recent breakout high
- **WHEN** 近期无创新高日
- **THEN** 规则返回 `status: "normal"`, `level: "info"`, message 说明暂无突破事件

#### Scenario: Volume data unavailable
- **WHEN** 缺少成交量数据
- **THEN** 规则返回 `status: "unknown"`, `level: "info"`, message 说明量能数据不足
