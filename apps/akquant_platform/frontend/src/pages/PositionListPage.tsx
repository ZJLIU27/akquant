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

export default function PositionListPage() {
  const navigate = useNavigate();
  const [positions, setPositions] = useState<PositionSummary[]>([]);
  const [totalMv, setTotalMv] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);

  const showToast = (msg: string, type: 'ok' | 'err') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

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

  const pollJob = async (jobId: string, attempts = 30): Promise<string> => {
    for (let i = 0; i < attempts; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const job = await api.getJob(jobId);
      if (job.status === 'success') return 'success';
      if (job.status === 'failed') throw new Error(job.error || '任务失败');
    }
    throw new Error('任务超时');
  };

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const res = await api.triggerIntradayUpdate(true);
      if (res.status === 'already_running') {
        showToast('已有刷新任务运行中，请稍候', 'err');
        return;
      }
      if (res.status === 'no_symbols') {
        showToast('没有需要刷新的持仓', 'err');
        return;
      }
      if (res.status === 'all_cached') {
        showToast('分时数据已是最新', 'ok');
        return;
      }
      if (res.job_id) {
        await pollJob(res.job_id);
        showToast('分时数据刷新完成', 'ok');
        await load();
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : '刷新失败', 'err');
    } finally {
      setRefreshing(false);
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
          <button
            style={{ ...btnStyle, opacity: refreshing ? 0.6 : 1, cursor: refreshing ? 'not-allowed' : 'pointer' }}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? '刷新中...' : '刷新分时'}
          </button>
          <button style={btnStyle} onClick={() => setShowForm(true)}>新增交易</button>
        </div>
      </div>

      <div style={tableContainer}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>代码</th>
              <th style={thStyle}>名称</th>
              <th style={thStyle}>持仓策略</th>
              <th style={thStyle}>持仓规则</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>持仓</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>成本价</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>最新价</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>市值</th>
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
                    key={p.id}
                    onClick={() => navigate(`/positions/${p.id}`)}
                    style={{ cursor: 'pointer', transition: 'background 0.15s' }}
                    onMouseEnter={e => (e.currentTarget.style.background = colors.snow)}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                    <td style={{ ...tdStyle, fontWeight: 600 }}>{p.symbol}</td>
                    <td style={tdStyle}>{p.name}</td>
                    <td style={tdStyle}>
                      <StrategySummary position={p} />
                    </td>
                    <td style={tdStyle}>
                      <RuleSummary position={p} />
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{p.remaining_quantity}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{fmt(p.avg_cost, 4)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      <span style={{ color: p.price_source === 'missing' ? colors.slate : colors.ink }}>
                        {fmt(p.latest_price)}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{fmt(p.market_value)}</td>
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

      {toast && (
        <div style={{
          position: 'fixed',
          top: 20,
          right: 20,
          padding: '12px 24px',
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 600,
          color: colors.white,
          background: toast.type === 'ok' ? colors.green : colors.red,
          boxShadow: shadow.medium,
          zIndex: 9999,
          transition: 'opacity 0.3s',
        }}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function StrategySummary({ position }: { position: PositionSummary }) {
  if (!position.strategy_id) {
    return <span style={{ color: colors.slate }}>未绑定</span>;
  }

  return (
    <span style={{ fontWeight: 600, color: colors.ink }}>
      {position.strategy_title || position.strategy_id}
    </span>
  );
}

function RuleSummary({ position }: { position: PositionSummary }) {
  if (position.rule_count === 0) {
    return <span style={{ color: colors.slate }}>暂无规则</span>;
  }

  const titles = position.rule_titles.slice(0, 2);
  const extra = Math.max(0, position.rule_count - titles.length);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
      {titles.map(title => (
        <span
          key={title}
          style={{
            padding: '2px 6px',
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 600,
            color: colors.ink,
            background: colors.borderLight,
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </span>
      ))}
      {extra > 0 && <span style={{ color: colors.slate, fontSize: 12 }}>+{extra}</span>}
      <span style={{ color: colors.slate, fontSize: 12 }}>
        风控{position.risk_rule_count} / 提醒{position.alert_rule_count}
      </span>
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
