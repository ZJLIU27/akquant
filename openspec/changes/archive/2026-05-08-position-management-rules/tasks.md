## 1. 指标计算层

- [x] 1.1 创建 `apps/akquant_platform/backend/app/positions/indicators.py`，实现 BBI 计算（(MA3+MA6+MA12+MA24)/4）
- [x] 1.2 实现 MA 均线计算函数，支持任意周期（用于黄线、白线）
- [x] 1.3 实现量比计算（当日量 / 20日均量）和 N 型结构局部低点检测
- [x] 1.4 在 `service.py` 的 `get_position_detail()` 中调用指标计算，将 `daily_df` 和 `indicators` 注入 market 字典
- [x] 1.5 为指标计算编写单元测试（正常计算、数据不足、边界情况）

## 2. 止损规则组

- [x] 2.1 实现 `workspace/position_rules/bbi_break_stop_loss.py` — BBI 破止损（连续两天收盘破 BBI）
- [x] 2.2 实现 `workspace/position_rules/yellow_line_break.py` — 黄线破止损（含浮盈宽限逻辑）
- [x] 2.3 实现 `workspace/position_rules/n_structure_break.py` — N 型结构破止损
- [x] 2.4 实现 `workspace/position_rules/sideways_three_days.py` — 横盘三天止损（买入后三天无涨跌）
- [x] 2.5 在 `workspace/registry.yaml` 注册 4 条止损规则

## 3. 止盈规则组

- [x] 3.1 实现 `workspace/position_rules/take_profit_release.py` — 止盈放飞（BBI 上方两根中大阳线）
- [x] 3.2 实现 `workspace/position_rules/three_quarter_bearish_volume.py` — 四分之三阴量线（假突破检测）
- [x] 3.3 在 `workspace/registry.yaml` 注册 2 条止盈规则

## 4. 卖出信号规则

- [x] 4.1 实现 `workspace/position_rules/s1_sell_signal.py` — S1 放量大阴线见顶信号
- [x] 4.2 实现 `workspace/position_rules/support_line_monitor.py` — 支撑线综合监控（白线/黄线/BBI）
- [x] 4.3 在 `workspace/registry.yaml` 注册 2 条卖出信号规则

## 5. 注册表参数类型扩展

- [x] 5.1 扩展 `registry.yaml` 的 `params_schema` 支持 `string`、`boolean`、`select` 类型
- [x] 5.2 前端 `RulePanel` 支持新参数类型渲染（text input、toggle switch、dropdown）

## 6. 测试

- [x] 6.1 为所有 8 条规则编写单元测试（触发/正常/边界/数据缺失场景）
- [x] 6.2 为 `service.py` 中 market 字典扩展编写集成测试
- [x] 6.3 端到端测试：添加规则到持仓 → 评估 → 验证 RuleResult 正确性
