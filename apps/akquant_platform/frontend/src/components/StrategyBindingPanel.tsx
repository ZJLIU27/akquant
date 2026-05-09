import { useEffect, useMemo, useState } from 'react';
import { api, type AvailableStrategy } from '../api/client';
import { colors, radius } from '../theme/variables';

interface Props {
  symbol: string;
  strategyId: string;
  strategyStage: string;
  strategyTags: string[];
  onReload: () => void;
}

export default function StrategyBindingPanel({
  symbol,
  strategyId,
  strategyStage,
  strategyTags,
  onReload,
}: Props) {
  const [available, setAvailable] = useState<AvailableStrategy[]>([]);
  const [draftStrategy, setDraftStrategy] = useState(strategyId);

  useEffect(() => {
    api.listAvailableStrategies().then(setAvailable).catch(console.error);
  }, []);

  useEffect(() => {
    setDraftStrategy(strategyId);
  }, [strategyId]);

  const selectedStrategy = useMemo(
    () => available.find(s => s.strategy_id === draftStrategy),
    [available, draftStrategy],
  );

  const currentStrategy = available.find(s => s.strategy_id === strategyId);
  const currentStage = currentStrategy?.stages.find(s => s.stage_id === strategyStage);

  const handleSave = async () => {
    try {
      await api.bindStrategy(symbol, { strategy_id: draftStrategy });
      onReload();
    } catch (e) {
      alert(`绑定策略失败: ${e}`);
    }
  };

  const dirty = draftStrategy !== strategyId;

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'end' }}>
        <label style={fieldStyle}>
          <span style={labelStyle}>大策略</span>
          <select value={draftStrategy} onChange={e => setDraftStrategy(e.target.value)} style={inputStyle}>
            <option value="">未绑定</option>
            {available.map(strategy => (
              <option key={strategy.strategy_id} value={strategy.strategy_id}>
                {strategy.title || strategy.strategy_id}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={handleSave}
          disabled={!dirty}
          style={{
            background: dirty ? colors.yellow : colors.borderLight,
            color: dirty ? colors.ink : colors.slate,
            border: 'none',
            borderRadius: radius.sm,
            padding: '9px 18px',
            fontWeight: 600,
            cursor: dirty ? 'pointer' : 'default',
          }}
        >
          保存绑定
        </button>
      </div>

      {strategyId && (
        <div style={{
          marginTop: 12,
          padding: '10px 12px',
          borderRadius: radius.md,
          background: colors.snow,
          color: colors.ink,
          fontSize: 13,
        }}>
          <span style={{ color: colors.slate }}>当前算法阶段：</span>
          <strong>{currentStage?.title || strategyStage || '待判断'}</strong>
          {currentStage?.description && (
            <span style={{ color: colors.slate }}> · {currentStage.description}</span>
          )}
        </div>
      )}

      {strategyTags.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          {strategyTags.map(tag => (
            <span key={tag} style={{
              fontSize: 12,
              padding: '3px 8px',
              borderRadius: radius.sm,
              background: colors.snow,
              color: colors.slate,
            }}>
              {tag}
            </span>
          ))}
        </div>
      )}

      {selectedStrategy && draftStrategy !== strategyId && (
        <div style={{ marginTop: 12, color: colors.slate, fontSize: 13 }}>
          保存后系统会按该策略的算法自动判断持仓阶段。
        </div>
      )}
    </div>
  );
}

const fieldStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
};

const labelStyle: React.CSSProperties = {
  color: colors.slate,
  fontSize: 12,
};

const inputStyle: React.CSSProperties = {
  border: `1px solid ${colors.borderLight}`,
  borderRadius: radius.sm,
  color: colors.ink,
  fontSize: 13,
  padding: '8px 10px',
};
