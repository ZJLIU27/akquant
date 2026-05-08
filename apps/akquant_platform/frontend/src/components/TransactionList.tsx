import { useState } from 'react';
import { api, type Transaction } from '../api/client';
import { colors, radius } from '../theme/variables';

interface Props {
  transactions: Transaction[];
  symbol: string;
  onReload: () => void;
}

export default function TransactionList({ transactions, symbol, onReload }: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState('');
  const [editQty, setEditQty] = useState('');

  const handleVoid = async (txnId: string) => {
    const reason = prompt('作废原因:');
    if (reason == null) return;
    try {
      await api.voidTransaction(symbol, txnId, reason);
      onReload();
    } catch (e) {
      alert(`作废失败: ${e}`);
    }
  };

  const startEdit = (txn: Transaction) => {
    setEditing(txn.id);
    setEditPrice(String(txn.price));
    setEditQty(String(txn.quantity));
  };

  const saveEdit = async (txnId: string) => {
    try {
      await api.editTransaction(symbol, txnId, {
        price: parseFloat(editPrice),
        quantity: parseInt(editQty),
      });
      setEditing(null);
      onReload();
    } catch (e) {
      alert(`编辑失败: ${e}`);
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
            <td style={cellStyle}>{txn.trade_date}</td>
            <td style={cellStyle}>
              <span style={{
                color: txn.side === 'buy' ? colors.green : colors.red,
                fontWeight: 600,
              }}>
                {txn.side === 'buy' ? '买入' : '卖出'}
              </span>
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={editQty} onChange={e => setEditQty(e.target.value)}
                  style={inputStyle} type="number" />
              ) : txn.quantity}
            </td>
            <td style={cellStyle}>
              {editing === txn.id ? (
                <input value={editPrice} onChange={e => setEditPrice(e.target.value)}
                  style={inputStyle} type="number" step="0.01" />
              ) : txn.price.toFixed(2)}
            </td>
            <td style={cellStyle}>{txn.fee.toFixed(2)}</td>
            <td style={cellStyle}>{txn.source}</td>
            <td style={cellStyle}>{txn.tags.join(', ')}</td>
            <td style={cellStyle}>{txn.notes}</td>
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
