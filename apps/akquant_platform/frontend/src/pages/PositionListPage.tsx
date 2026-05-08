import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type PositionSummary } from '../api/client';
import { colors, radius, shadow } from '../theme/variables';
import TransactionForm from '../components/TransactionForm';

const pageStyle: React.CSSProperties = {
  maxWidth: 1200,
  margin: '0 auto',
  padding: '24px 32px',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 24,
};

const tableContainer: React.CSSProperties = {
  background: colors.white,
  borderRadius: radius.lg,
  boxShadow: shadow.subtle,
  overflow: 'hidden',
};

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 14,
};

const thStyle: React.CSSProperties = {
  padding: '12px 16px',
  textAlign: 'left',
  fontWeight: 600,
  color: colors.slate,
  borderBottom: `1px solid ${colors.borderLight}`,
  fontSize: 12,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};

const tdStyle: React.CSSProperties = {
  padding: '12px 16px',
  borderBottom: `1px solid ${colors.borderLight}`,
  color: colors.primaryText,
};

const btnStyle: React.CSSProperties = {
  background: colors.yellow,
  color: colors.ink,
  border: 'none',
  borderRadius: radius.sm,
  padding: '8px 20px',
  fontWeight: 600,
  fontSize: 14,
  cursor: 'pointer',
  transition: 'background 0.2s',
};

function fmt(n: number | null, decimals = 2): string {
  if (n == null) return '-';
  return n.toFixed(decimals);
}

function pnlColor(val: number): string {
  return val > 0 ? colors.green : val < 0 ? colors.red : colors.slate;
}

export default function PositionListPage() {
  const navigate = useNavigate();
  const [positions, setPositions] = useState<PositionSummary[]>([]);
  const [totalMv, setTotalMv] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.listPositions();
      setPositions(res.positions);
      setTotalMv(res.total_market_value);
    } catch (e) {
      console.error('Failed to load positions:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = async () => {
    try {
      await api.triggerIntradayUpdate(true);
      setTimeout(load, 3000);
    } catch (e) {
      console.error('Refresh failed:', e);
    }
  };

  return (
    <div style={pageStyle}>
      <div style={headerStyle}>
        <h2 style={{ fontSize: 24, fontWeight: 700, color: colors.ink }}>
          持仓管理
          <span style={{ fontSize: 14, fontWeight: 400, color: colors.slate, marginLeft: 12 }}>
            总市值 {fmt(totalMv)}
          </span>
        </h2>
        <div style={{ display: 'flex', gap: 12 }}>
          <button style={btnStyle} onClick={handleRefresh}>刷新分时</button>
          <button style={btnStyle} onClick={() => setShowForm(true)}>新增交易</button>
        </div>
      </div>

      <div style={tableContainer}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>代码</th>
              <th style={thStyle}>名称</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>持仓</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>成本价</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>最新价</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>市值</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>已实现</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>未实现</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>占比</th>
              <th style={thStyle}>状态</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} style={{ ...tdStyle, textAlign: 'center', color: colors.slate }}>加载中...</td></tr>
            ) : positions.length === 0 ? (
              <tr><td colSpan={10} style={{ ...tdStyle, textAlign: 'center', color: colors.slate }}>暂无持仓</td></tr>
            ) : (
              positions.map((p) => {
                return (
                  <tr
                    key={p.symbol}
                    onClick={() => navigate(`/positions/${p.symbol}`)}
                    style={{ cursor: 'pointer', transition: 'background 0.15s' }}
                    onMouseEnter={e => (e.currentTarget.style.background = colors.snow)}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                  >
                    <td style={{ ...tdStyle, fontWeight: 600 }}>{p.symbol}</td>
                    <td style={tdStyle}>{p.name}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{p.remaining_quantity}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{fmt(p.avg_cost, 4)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      <span style={{ color: p.price_source === 'missing' ? colors.slate : colors.ink }}>
                        {fmt(p.latest_price)}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{fmt(p.market_value)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: pnlColor(p.realized_pnl) }}>
                      {fmt(p.realized_pnl)}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: pnlColor(p.unrealized_pnl) }}>
                      {fmt(p.unrealized_pnl)}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      {(p.position_weight * 100).toFixed(1)}%
                    </td>
                    <td style={tdStyle}>
                      <StatusBadge status={p.status} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <TransactionForm
          onClose={() => setShowForm(false)}
          onSaved={load}
        />
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const bg = status === 'open' ? colors.green :
             status === 'closed' ? colors.slate :
             colors.red;
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 12,
      fontWeight: 600,
      color: colors.white,
      background: bg,
    }}>
      {status === 'open' ? '持仓' : status === 'closed' ? '已清' : '异常'}
    </span>
  );
}
