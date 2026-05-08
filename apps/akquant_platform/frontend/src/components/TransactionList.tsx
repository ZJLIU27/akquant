import { useState } from 'react';
import { api, type Transaction } from '../api/client';
import { colors, radius } from '../theme/variables';

interface Props {
  transactions: Transaction[];
  symbol: string;
  onReload: () => void;
}

interface Draft {
  side: 'buy' | 'sell';
  trade_date: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  tagsText: string;
  notes: string;
}

function txnToDraft(txn: Transaction): Draft {
  return {
    side: txn.side,
    trade_date: txn.trade_date,
    quantity: String(txn.quantity),
    price: String(txn.price),
    fee: String(txn.fee),
    source: txn.source,
    tagsText: txn.tags.join(', '),
    notes: txn.notes,
  };
}

function parseApiError(e: unknown): string {
  if (e instanceof Error) {
    try {
      const parsed = JSON.parse(e.message);
      if (parsed.detail) return String(parsed.detail);
    } catch { /* not JSON */ }
    return e.message;
  }
  return String(e);
}

export default function TransactionList({ transactions, symbol, onReload }: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({
    side: 'buy', trade_date: '', quantity: '', price: '', fee: '0',
    source: 'manual', tagsText: '', notes: '',
  });

  const handleVoid = async (txnId: string) => {
    const reason = prompt('作废原因:');
    if (reason == null) return;
    try {
      await api.voidTransaction(symbol, txnId, reason);
      onReload();
    } catch (e) {
      alert(`作废失败: ${parseApiError(e)}`);
    }
  };

  const startEdit = (txn: Transaction) => {
    setEditing(txn.id);
    setDraft(txnToDraft(txn));
  };

  const saveEdit = async (txnId: string) => {
    try {
      await api.editTransaction(symbol, txnId, {
        side: draft.side,
        trade_date: draft.trade_date,
        quantity: parseInt(draft.quantity, 10),
        price: parseFloat(draft.price),
        fee: parseFloat(draft.fee) || 0,
        source: draft.source || 'manual',
        tags: draft.tagsText.split(',').map(s => s.trim()).filter(Boolean),
        notes: draft.notes,
      });
      setEditing(null);
      onReload();
    } catch (e) {
      alert(`编辑失败: ${parseApiError(e)}`);
    }
  };

  if (transactions.length === 0) {
    return <p style={{ color: colors.slate }}>暂无交易</p>;
  }

  const sorted = [...transactions].sort((a, b) =>
    b.trade_date.localeCompare(a.trade_date) || b.created_at.localeCompare(a.created_at)
  );

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
      <thead>
        <tr>
          {['日期', '方向', '数量', '价格', '手续费', '来源', '标签', '备注', '版本', '操作'].map(h => (
            <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: colors.slate, borderBottom: `1px solid ${colors.borderLight}`, fontSize: 12 }}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map(txn => (
          <tr key={txn.id} style={{ opacity: txn.voided ? 0.4 : 1 }}>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input type="date" value={draft.trade_date}
                  onChange={e => setDraft(d => ({ ...d, trade_date: e.target.value }))}
                  style={inputStyle} />
              ) : txn.trade_date}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['buy', 'sell'] as const).map(s => (
                    <button key={s} type="button"
                      onClick={() => setDraft(d => ({ ...d, side: s }))}
                      style={{
                        border: 'none', borderRadius: 4, padding: '2px 10px', fontSize: 12,
                        fontWeight: 600, cursor: 'pointer',
                        background: draft.side === s ? (s === 'buy' ? colors.green : colors.red) : colors.snow,
                        color: draft.side === s ? colors.white : colors.slate,
                      }}>
                      {s === 'buy' ? '买入' : '卖出'}
                    </button>
                  ))}
                </div>
              ) : (
                <span style={{
                  color: txn.side === 'buy' ? colors.green : colors.red,
                  fontWeight: 600,
                }}>
                  {txn.side === 'buy' ? '买入' : '卖出'}
                </span>
              )}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={draft.quantity} onChange={e => setDraft(d => ({ ...d, quantity: e.target.value }))}
                  style={inputStyle} type="number" />
              ) : txn.quantity}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={draft.price} onChange={e => setDraft(d => ({ ...d, price: e.target.value }))}
                  style={inputStyle} type="number" step="0.01" />
              ) : txn.price.toFixed(2)}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={draft.fee} onChange={e => setDraft(d => ({ ...d, fee: e.target.value }))}
                  style={inputStyle} type="number" step="0.01" />
              ) : txn.fee.toFixed(2)}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={draft.source} onChange={e => setDraft(d => ({ ...d, source: e.target.value }))}
                  style={inputStyle} />
              ) : txn.source}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={draft.tagsText} onChange={e => setDraft(d => ({ ...d, tagsText: e.target.value }))}
                  style={inputStyle} placeholder="逗号分隔" />
              ) : txn.tags.join(', ')}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={draft.notes} onChange={e => setDraft(d => ({ ...d, notes: e.target.value }))}
                  style={inputStyle} />
              ) : txn.notes}
            </td>
            <td style={cellStyle}>v{txn.revision}</td>
            <td style={cellStyle}>
              {txn.voided ? (
                <span style={{ color: colors.slate, fontSize: 12 }}>已作废: {txn.void_reason}</span>
              ) : editing === txn.id ? (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => saveEdit(txn.id)} style={smallBtn(colors.yellow)}>保存</button>
                  <button onClick={() => setEditing(null)} style={smallBtn(colors.slate)}>取消</button>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => startEdit(txn)} style={smallBtn(colors.focusBlue)}>编辑</button>
                  <button onClick={() => handleVoid(txn.id)} style={smallBtn(colors.red)}>作废</button>
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const cellStyle: React.CSSProperties = {
  padding: '8px 12px',
  borderBottom: `1px solid ${colors.borderLight}`,
  color: colors.ink,
};

const inputStyle: React.CSSProperties = {
  width: 80,
  padding: '2px 6px',
  border: `1px solid ${colors.borderLight}`,
  borderRadius: radius.sm,
  fontSize: 13,
};

function smallBtn(bg: string): React.CSSProperties {
  return {
    background: bg,
    color: bg === colors.yellow || bg === colors.focusBlue ? colors.ink : colors.white,
    border: 'none',
    borderRadius: 4,
    padding: '2px 10px',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  };
}
