# 持仓交易编辑能力调整指南

本文给后续 SubAgent 使用，目标是扩展持仓详情页里的交易流水编辑能力。当前用户反馈的核心问题是：

1. 交易无法删除，尝试删除时系统提示 error。
2. 交易方向无法从买入改成卖出，或从卖出改成买入。
3. 交易手续费无法编辑。

本次实现目标不是引入复杂账户体系，而是让已经录入的交易流水在输错时可以自由修正，同时保留审计记录。

## 1. 当前实现现状

后端已有基础能力：

- `apps/akquant_platform/backend/app/positions/models.py`
  - `Transaction` 已包含 `side`、`trade_date`、`quantity`、`price`、`fee`、`source`、`tags`、`notes`、`voided`、`void_reason` 等字段。
- `apps/akquant_platform/backend/app/positions/repository.py`
  - `edit_transaction()` 的 `editable_fields` 已包含 `price`、`quantity`、`fee`、`trade_date`、`side`、`notes`、`tags`、`source`。
  - `void_transaction()` 已支持软删除，即设置 `voided=True`，并写 audit log。
- `apps/akquant_platform/backend/app/positions/routes.py`
  - `PATCH /api/positions/{symbol}/transactions/{transaction_id}` 调用 `edit_transaction()`。
  - `POST /api/positions/{symbol}/transactions/{transaction_id}/void` 调用 `void_transaction()`。
- `apps/akquant_platform/frontend/src/api/client.ts`
  - 已有 `editTransaction()` 和 `voidTransaction()`。

前端限制较明显：

- `apps/akquant_platform/frontend/src/components/TransactionList.tsx`
  - 目前 inline edit 只维护 `editPrice`、`editQty`。
  - 保存时只提交 `price` 和 `quantity`。
  - `fee` 只展示，不可编辑。
  - `side` 只展示，不可编辑。
  - “删除”按钮实际调用 `voidTransaction()`，语义是作废，不是物理删除。
- `apps/akquant_platform/frontend/src/components/TransactionForm.tsx`
  - 只用于新增交易，不适合直接复用为完整编辑弹窗，除非先抽象出 create/edit 两种模式。

重要语义：

- 当前 spec 里交易删除优先采用软删除，即 `voided: true`，不物理移除 YAML 里的 transaction。
- `calculate_position()` 会忽略 `voided` 交易。
- 如果编辑后的流水导致卖出数量超过当时剩余持仓，`calculate_position()` 会把 position 标为 `invalid`。

## 2. 目标行为

### 2.1 编辑交易

用户点击某笔交易的“编辑”后，应能修改完整交易详情：

- `side`: `buy` / `sell`
- `trade_date`
- `quantity`
- `price`
- `fee`
- `source`
- `tags`
- `notes`

保存后：

- 后端更新交易。
- `updated_at` 刷新。
- `revision` 递增。
- `audit_log` 记录改动前后的字段。
- 页面重新加载持仓详情、汇总指标、图表成本线和规则结果。

### 2.2 删除交易

第一阶段不要做物理删除。UI 上可以显示“删除”，但后端仍应调用 `voidTransaction()`，语义说明为“作废此交易”。

作废后：

- 交易仍保留在列表中，但以禁用/淡化状态展示。
- 交易不再参与持仓计算。
- 交易行展示作废原因。
- 支持用户输入作废原因。

如果当前删除按钮会报错，SubAgent 应优先定位是：

- 前端是否调用了错误 method/path。
- `symbol` 或 `transaction_id` 是否传错。
- 后端返回的错误详情是否只是 404/422 的原始 JSON。
- 作废后的响应是否不能被前端正常解析。

### 2.3 编辑后的校验

保存编辑前后要考虑两层校验：

- 字段级校验：数量和价格必须大于 0，手续费不能小于 0，方向必须是 `buy` 或 `sell`。
- 业务级校验：编辑后如果出现超卖，允许保存但页面应清楚显示 `invalid`，还是直接拒绝保存，需要按下面建议选择。

建议第一阶段采用：

- 字段级错误直接阻止保存。
- 业务级超卖不阻止保存，由现有 `summary.status === "invalid"` 暴露异常状态。
- 但保存后页面要正常刷新，不能因为 invalid 状态崩溃。

这样更符合“录错后自由修正”的目标，也保留用户恢复数据的空间。

## 3. 建议实现方案

### 3.1 前端改动

优先改 `TransactionList.tsx`，把当前只编辑数量/价格的 inline 状态改成完整编辑状态。

推荐做法：

- 新增一个 `draft` state，类型接近：

```ts
type TransactionDraft = {
  side: 'buy' | 'sell';
  trade_date: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  tagsText: string;
  notes: string;
};
```

- `startEdit(txn)` 时把当前交易完整填入 draft。
- 编辑行内提供控件：
  - `side`: 两个按钮或 select。
  - `trade_date`: date input。
  - `quantity`: number input。
  - `price`: number input。
  - `fee`: number input。
  - `source`: text input。
  - `tagsText`: 逗号分隔文本，保存时转成 `string[]`。
  - `notes`: text input。
- `saveEdit(txn.id)` 时提交完整 payload：

```ts
await api.editTransaction(symbol, txnId, {
  side: draft.side,
  trade_date: draft.trade_date,
  quantity: parseInt(draft.quantity, 10),
  price: parseFloat(draft.price),
  fee: parseFloat(draft.fee) || 0,
  source: draft.source || 'manual',
  tags: draft.tagsText
    .split(',')
    .map(s => s.trim())
    .filter(Boolean),
  notes: draft.notes,
});
```

需要注意：

- 不要对 `voided` 交易显示编辑按钮；作废后的交易只展示状态和原因。
- 删除按钮文案建议改成“作废”或“删除/作废”，避免误导成物理删除。
- error alert 里尽量解析后端 `detail`，不要只显示 `Error: {"detail": ...}`。
- 表格列较多，inline 编辑会挤，可以改成编辑弹窗；如果做弹窗，仍优先只改 `TransactionList.tsx` 或新增局部组件，不要重构整个详情页。

### 3.2 API client 改动

`client.ts` 现有 `editTransaction()` 可以继续使用，但建议补一个明确类型：

```ts
export interface TransactionUpdatePayload {
  side?: 'buy' | 'sell';
  trade_date?: string;
  quantity?: number;
  price?: number;
  fee?: number;
  source?: string;
  tags?: string[];
  notes?: string;
}
```

然后把：

```ts
updates: Record<string, unknown>
```

收窄为：

```ts
updates: TransactionUpdatePayload
```

这不是必须，但能减少前端把错误字段传给后端。

### 3.3 后端改动

后端已经基本支持完整字段编辑，但建议补强以下点：

1. 在 `routes.py` 中为编辑请求定义 Pydantic model，不要直接用裸 `dict[str, Any]`。
2. 在 `repository.edit_transaction()` 中只记录真实变化的字段，未变化字段不要写入 audit。
3. 如果没有任何字段变化，可以直接返回原交易，不递增 `revision`，也不写 audit。
4. `side`、`quantity`、`price`、`fee` 的校验交给 Pydantic model 或 `Transaction` validation，避免非法值写入 YAML。
5. 对 `voided=True` 的交易是否允许再次编辑要明确。建议第一阶段禁止编辑作废交易，返回 400。

建议新增模型，例如放在 `models.py`：

```python
class TransactionUpdate(BaseModel):
    side: Literal["buy", "sell"] | None = None
    trade_date: date | None = None
    quantity: int | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, gt=0)
    fee: float | None = Field(default=None, ge=0)
    source: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
```

路由改成：

```python
@router.patch("/positions/{symbol}/transactions/{transaction_id}")
def edit_transaction(
    symbol: str,
    transaction_id: str,
    updates: TransactionUpdate,
) -> Transaction:
    payload = updates.model_dump(exclude_unset=True)
    result = get_service().edit_transaction(symbol, transaction_id, **payload)
    ...
```

作废交易的路由也可以补一个 request model：

```python
class VoidTransactionRequest(BaseModel):
    reason: str = ""
```

### 3.4 是否增加真正 DELETE 接口

建议第一阶段不增加物理删除接口。原因：

- 现有 spec 和实现都以 audit/void 为主。
- 物理删除会丢历史记录，和“输错后可追溯修正”目标冲突。
- 当前计算逻辑已经支持忽略 `voided` 交易。

如果 UI 必须叫“删除”，实现上仍然调用 void；文案可以提示“删除后将作为作废交易保留审计记录”。

## 4. 测试要求

### 4.1 后端测试

更新或新增：

- `apps/akquant_platform/backend/tests/test_repository.py`
- `apps/akquant_platform/backend/tests/test_service.py`
- 如有路由级测试，再补对应 API 测试。

至少覆盖：

1. 编辑 `fee` 后重新加载 YAML，交易手续费已变化，`revision` 递增，audit 记录 before/after。
2. 编辑 `side` 从 buy 改 sell，字段保存成功。
3. 编辑 `trade_date`、`source`、`tags`、`notes` 均保存成功。
4. 作废交易后 `voided=True`，`void_reason` 保存，持仓计算忽略该交易。
5. 作废交易再次编辑应被拒绝，或明确允许；建议拒绝并测试。
6. 非法输入被拒绝：负手续费、0 数量、非法 side。

运行：

```powershell
python -m pytest apps\akquant_platform\backend\tests -q
```

### 4.2 前端检查

至少运行：

```powershell
cd apps\akquant_platform\frontend
npm run lint
npm run build
```

如果启动本地服务手工验证：

```powershell
scripts\start_dev.bat
```

手工验证路径：

1. 进入某个持仓详情页。
2. 编辑一笔买入交易，把手续费从 0 改为非 0，确认成本价变化。
3. 把交易方向从买入改为卖出，确认保存成功且页面能显示 invalid 或新的持仓结果。
4. 修改交易日期、备注、标签，刷新页面后仍保留。
5. 作废一笔交易，确认列表淡化显示，汇总计算不包含它。

## 5. 非目标范围

本次不要做：

- 现金账户。
- 交易撮合或真实券商同步。
- 物理删除交易。
- 批量编辑交易。
- 跨 symbol 移动交易。
- 重构整个持仓页 UI。
- 把用户真实持仓或规则迁出 `workspace/` 边界。

## 6. 完成标准

后续 Agent 完成后，应能说明：

- 哪些交易字段现在可编辑。
- 删除按钮实际采用作废语义，是否保留审计记录。
- 已补哪些后端测试。
- 前端是否通过 `npm run lint` 和 `npm run build`。
- 是否验证了作废后持仓计算会忽略该交易。
