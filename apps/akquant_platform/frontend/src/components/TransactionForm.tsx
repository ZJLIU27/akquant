import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { colors, radius, shadow } from '../theme/variables';
import StockSearch from './StockSearch';

interface Props {
  onClose: () => void;
  onSaved: () => void;
  initialSymbol?: string;
  initialSide?: 'buy' | 'sell';
}

export default function TransactionForm({ onClose, onSaved, initialSymbol, initialSide }: Props) {
  const [symbol, setSymbol] = useState(initialSymbol || '');
  const [name, setName] = useState('');
  const [side, setSide] = useState<'buy' | 'sell'>(initialSide || 'buy');
  const [stockResolved, setStockResolved] = useState(!!initialSymbol);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [fee, setFee] = useState('0');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [stockError, setStockError] = useState('');

  useEffect(() => {
    if (initialSymbol) setSymbol(initialSymbol);
    if (initialSide) setSide(initialSide);
  }, [initialSymbol, initialSide]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (side === 'buy' && !initialSymbol && !stockResolved) {
      setStockError('请从下拉列表中选择股票');
      return;
    }
    setStockError('');
    setSaving(true);
    try {
      await api.addTransaction(symbol, {
        side,
        trade_date: date,
        quantity: parseInt(quantity),
        price: parseFloat(price),
        fee: parseFloat(fee) || 0,
        name: side === 'buy' ? name : undefined,
        notes,
      });
      onSaved();
      onClose();
    } catch (err) {
      alert(`提交失败: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: colors.white, borderRadius: radius.lg, padding: 32,
        width: 480, boxShadow: shadow.medium,
      }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 24, color: colors.ink }}>
          新增交易
        </h3>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            {(['buy', 'sell'] as const).map(s => (
              <button
                key={s}
                type="button"
                onClick={() => setSide(s)}
                style={{
                  flex: 1, padding: '10px 0', border: 'none', borderRadius: radius.sm,
                  fontWeight: 600, fontSize: 14, cursor: 'pointer',
                  background: side === s ? (s === 'buy' ? colors.green : colors.red) : colors.snow,
                  color: side === s ? colors.white : colors.slate,
                }}
              >
                {s === 'buy' ? '买入' : '卖出'}
              </button>
            ))}
          </div>

          <Row label="股票">
            {initialSymbol ? (
              <input value={`${initialSymbol} ${name || ''}`.trim()} disabled style={{ ...inputStyle, background: colors.snow }} />
            ) : (
              <>
                <StockSearch
                  onSelect={(sym, nm) => { setSymbol(sym); setName(nm); setStockResolved(true); setStockError(''); }}
                  onClear={() => { setSymbol(''); setName(''); setStockResolved(false); }}
                />
                {stockError && (
                  <span style={{ color: colors.red, fontSize: 12, marginTop: 4, display: 'block' }}>{stockError}</span>
                )}
              </>
            )}
          </Row>
          <Row label="交易日期">
            <input type="date" value={date} onChange={e => setDate(e.target.value)} required style={inputStyle} />
          </Row>
          <div style={{ display: 'flex', gap: 12 }}>
            <Row label="数量">
              <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)} required style={inputStyle} />
            </Row>
            <Row label="价格">
              <input type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)} required style={inputStyle} />
            </Row>
            <Row label="手续费">
              <input type="number" step="0.01" value={fee} onChange={e => setFee(e.target.value)} style={inputStyle} />
            </Row>
          </div>
          <Row label="备注">
            <input value={notes} onChange={e => setNotes(e.target.value)} style={inputStyle} />
          </Row>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
            <button type="button" onClick={onClose} style={{ ...btnBase, background: colors.snow, color: colors.slate }}>
              取消
            </button>
            <button type="submit" disabled={saving} style={{
              ...btnBase, background: colors.yellow, color: colors.ink,
              opacity: saving ? 0.6 : 1,
            }}>
              {saving ? '提交中...' : '确认'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.slate, marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  border: `1px solid ${colors.borderLight}`,
  borderRadius: radius.sm,
  fontSize: 14,
  color: colors.ink,
};

const btnBase: React.CSSProperties = {
  border: 'none',
  borderRadius: radius.sm,
  padding: '10px 24px',
  fontWeight: 600,
  fontSize: 14,
  cursor: 'pointer',
};
