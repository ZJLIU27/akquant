import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type PositionDetail, type IntradayResponse, type DailyResponse } from '../api/client';
import { colors, radius, shadow } from '../theme/variables';
import IntradayChart from '../components/IntradayChart';
import DailyChart from '../components/DailyChart';
import TransactionList from '../components/TransactionList';
import TransactionForm from '../components/TransactionForm';
import RulePanel from '../components/RulePanel';
import StrategyBindingPanel from '../components/StrategyBindingPanel';

const pageStyle: React.CSSProperties = {
  maxWidth: 1200,
  margin: '0 auto',
  padding: '24px 32px',
};

const cardStyle: React.CSSProperties = {
  background: colors.white,
  borderRadius: radius.lg,
  boxShadow: shadow.subtle,
  padding: 24,
  marginBottom: 24,
};

const backStyle: React.CSSProperties = {
  color: colors.slate,
  fontSize: 14,
  cursor: 'pointer',
  marginBottom: 16,
  display: 'inline-block',
};

const metricRow: React.CSSProperties = {
  display: 'flex',
  gap: 32,
  flexWrap: 'wrap',
};

const metricItem: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
};

function fmt(n: number | null, d = 2): string {
  if (n == null) return '-';
  return n.toFixed(d);
}

function pnlColor(val: number): string {
  return val > 0 ? colors.green : val < 0 ? colors.red : colors.slate;
}

export default function PositionDetailPage() {
  const { positionId } = useParams<{ positionId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<PositionDetail | null>(null);
  const [intraday, setIntraday] = useState<IntradayResponse | null>(null);
  const [daily, setDaily] = useState<DailyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showIntraday, setShowIntraday] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    if (!positionId) return;
    try {
      const [d, i, day] = await Promise.all([
        api.getPosition(positionId),
        api.getIntraday(positionId),
        api.getDaily(positionId),
      ]);
      setDetail(d);
      setIntraday(i);
      setDaily(day);
    } catch (e) {
      console.error('Failed to load position:', e);
    } finally {
      setLoading(false);
    }
  }, [positionId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={pageStyle}><p style={{ color: colors.slate }}>加载中...</p></div>;
  if (!detail) return <div style={pageStyle}><p style={{ color: colors.red }}>持仓不存在</p></div>;

  const { summary, position, rule_results } = detail;

  return (
    <div style={pageStyle}>
      <div style={backStyle} onClick={() => navigate('/')}>
        &larr; 返回持仓列表
      </div>

      {/* Summary Card */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: colors.ink }}>
              {summary.symbol} {summary.name}
            </h2>
            <span style={{ fontSize: 12, color: colors.slate }}>
              Position ID: {position.id} · 价格来源: {summary.price_source === 'intraday' ? '分时' : summary.price_source === 'daily_fallback' ? '日线回退' : '缺失'}
            </span>
          </div>
          <span style={{
            padding: '4px 12px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 600,
            color: colors.white,
            background: summary.status === 'open' ? colors.green : summary.status === 'closed' ? colors.slate : colors.red,
          }}>
            {summary.status === 'open' ? '持仓中' : summary.status === 'closed' ? '已清仓' : '异常'}
          </span>
        </div>
        <div style={metricRow}>
          <Metric label="持仓数量" value={String(summary.remaining_quantity)} />
          <Metric label="成本价" value={fmt(summary.avg_cost, 4)} />
          <Metric label="最新价" value={fmt(summary.latest_price)} />
          <Metric label="市值" value={fmt(summary.market_value)} />
          <Metric label="已实现盈亏" value={fmt(summary.realized_pnl)} color={pnlColor(summary.realized_pnl)} />
          <Metric label="未实现盈亏" value={fmt(summary.unrealized_pnl)} color={pnlColor(summary.unrealized_pnl)} />
          <Metric label="占比" value={`${(summary.position_weight * 100).toFixed(1)}%`} />
        </div>
      </div>

      {/* Rules */}
      <div style={cardStyle}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: colors.ink }}>有效持仓规则</h3>
        <RulePanel
          symbol={position.id}
          rules={detail.effective_rules}
          ruleResults={rule_results}
          onReload={load}
        />
      </div>

      {/* Intraday Chart */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: colors.ink }}>当日分时</h3>
          <button
            type="button"
            onClick={() => setShowIntraday(prev => !prev)}
            style={{
              border: `1px solid ${colors.borderLight}`,
              borderRadius: radius.sm,
              background: colors.white,
              color: colors.ink,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              padding: '6px 12px',
            }}
          >
            {showIntraday ? '收起' : '展开'}
          </button>
        </div>
        {showIntraday && (
          <div style={{ marginTop: 16 }}>
            <IntradayChart data={intraday} avgCost={summary.avg_cost} />
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: colors.ink }}>日线与指标</h3>
        <DailyChart symbol={position.symbol} data={daily} avgCost={summary.avg_cost} transactions={position.transactions} />
      </div>

      {/* Transactions */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: colors.ink }}>交易流水</h3>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            style={{
              border: 'none',
              borderRadius: radius.sm,
              background: colors.yellow,
              color: colors.ink,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              padding: '6px 12px',
            }}
          >
            新增操作
          </button>
        </div>
        <TransactionList transactions={position.transactions} symbol={position.id} onReload={load} />
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: colors.ink }}>策略绑定</h3>
        <StrategyBindingPanel
          symbol={position.id}
          strategyId={position.strategy_id}
          strategyStage={position.strategy_stage}
          strategyTags={position.strategy_tags}
          onReload={load}
        />
      </div>

      {showForm && (
        <TransactionForm
          onClose={() => setShowForm(false)}
          onSaved={load}
          initialSymbol={position.symbol}
          initialName={position.name}
          positionId={position.id}
        />
      )}
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={metricItem}>
      <span style={{ fontSize: 12, color: colors.slate, marginBottom: 4 }}>{label}</span>
      <span style={{ fontSize: 18, fontWeight: 600, color: color || colors.ink }}>{value}</span>
    </div>
  );
}
