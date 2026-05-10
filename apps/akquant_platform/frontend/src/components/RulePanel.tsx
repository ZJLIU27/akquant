import { useState, useEffect } from 'react';
import { api, type PositionRule, type RuleResult, type AvailableRule } from '../api/client';
import { colors, radius } from '../theme/variables';

interface Props {
  symbol: string;
  rules: PositionRule[];
  ruleResults: RuleResult[];
  onReload: () => void;
}

export default function RulePanel({ symbol, rules, ruleResults, onReload }: Props) {
  const [available, setAvailable] = useState<AvailableRule[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [selectedScript, setSelectedScript] = useState('');
  const [category, setCategory] = useState<'risk' | 'alert'>('risk');
  const [params, setParams] = useState<Record<string, string>>({});

  useEffect(() => {
    api.listAvailableRules().then(setAvailable).catch(console.error);
  }, []);

  const selectedRule = available.find(r => r.script_id === selectedScript);

  const handleAdd = async () => {
    if (!selectedScript) return;
    try {
      const parsedParams: Record<string, unknown> = {};
      const schemaMap: Record<string, any> = {};
      for (const s of (selectedRule?.params_schema || [])) {
        schemaMap[s.name] = s;
      }
      for (const [k, v] of Object.entries(params)) {
        const schema = schemaMap[k];
        if (schema?.type === 'boolean') {
          parsedParams[k] = v === 'true';
        } else if (schema?.type === 'string' || schema?.type === 'select') {
          parsedParams[k] = v;
        } else {
          parsedParams[k] = isNaN(Number(v)) ? v : Number(v);
        }
      }
      await api.addRule(symbol, { category, script_id: selectedScript, params: parsedParams });
      setShowAdd(false);
      setSelectedScript('');
      setParams({});
      onReload();
    } catch (e) {
      alert(`添加规则失败: ${e}`);
    }
  };

  const handleDelete = async (ruleId: string) => {
    if (!confirm('确认删除此规则?')) return;
    try {
      await api.deleteRule(symbol, ruleId);
      onReload();
    } catch (e) {
      alert(`删除失败: ${e}`);
    }
  };

  const levelColor = (level: string) => {
    if (level === 'danger') return colors.red;
    if (level === 'warning') return colors.yellow;
    return colors.green;
  };

  const statusLabel = (status: RuleResult['status']) => {
    if (status === 'completed') return '已完成';
    if (status === 'triggered') return '需处理';
    if (status === 'unknown') return '待评估';
    if (status === 'error') return '异常';
    return '正常';
  };

  const statusColor = (result: RuleResult) => {
    if (result.status === 'completed') return colors.green;
    if (result.status === 'error' || result.level === 'danger') return colors.red;
    if (result.status === 'triggered' || result.level === 'warning') return colors.activeYellow;
    return colors.green;
  };

  return (
    <div>
      {rules.length === 0 && !showAdd && (
        <p style={{ color: colors.slate, marginBottom: 12 }}>暂无规则</p>
      )}

      {rules.map(rule => {
        const result = ruleResults.find(r => r.rule_id === rule.id);
        const fromStrategy = Boolean(rule.strategy_id);
        return (
          <div key={rule.id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', marginBottom: 8,
            background: colors.snow, borderRadius: radius.md,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{
                padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                background: rule.category === 'risk' ? colors.red + '20' : colors.yellow + '20',
                color: rule.category === 'risk' ? colors.red : colors.activeYellow,
              }}>
                {rule.category === 'risk' ? '风控' : '提醒'}
              </span>
              <span style={{ fontWeight: 500, color: colors.ink }}>{rule.script_id}</span>
              {fromStrategy && <span style={{ fontSize: 12, color: colors.slate }}>策略规则</span>}
              {!rule.enabled && <span style={{ fontSize: 12, color: colors.slate }}>(已禁用)</span>}
            </div>
            {result && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, marginLeft: 24 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: levelColor(result.level),
                }} />
                <span style={{
                  padding: '2px 7px',
                  borderRadius: 4,
                  fontSize: 11,
                  fontWeight: 600,
                  color: statusColor(result),
                  background: `${statusColor(result)}20`,
                  whiteSpace: 'nowrap',
                }}>
                  {statusLabel(result.status)}
                </span>
                <span style={{ fontSize: 13, color: colors.ink }}>{result.message}</span>
              </div>
            )}
            {fromStrategy ? (
              <span style={{ color: colors.slate, fontSize: 12 }}>随阶段绑定</span>
            ) : (
              <button
                onClick={() => handleDelete(rule.id)}
                style={{ background: 'none', border: 'none', color: colors.slate, cursor: 'pointer', fontSize: 12 }}
              >
                删除
              </button>
            )}
          </div>
        );
      })}

      {showAdd ? (
        <div style={{ marginTop: 16, padding: 16, background: colors.snow, borderRadius: radius.md }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            {(['risk', 'alert'] as const).map(c => (
              <button key={c} type="button" onClick={() => setCategory(c)} style={{
                flex: 1, padding: '8px 0', border: 'none', borderRadius: radius.sm,
                fontWeight: 600, fontSize: 13, cursor: 'pointer',
                background: category === c ? colors.yellow : colors.borderLight,
                color: category === c ? colors.ink : colors.slate,
              }}>
                {c === 'risk' ? '风控' : '提醒'}
              </button>
            ))}
          </div>
          <select
            value={selectedScript}
            onChange={e => { setSelectedScript(e.target.value); setParams({}); }}
            style={{ width: '100%', padding: '8px 12px', borderRadius: radius.sm, border: `1px solid ${colors.borderLight}`, marginBottom: 12, fontSize: 13 }}
          >
            <option value="">选择规则...</option>
            {available.map(r => (
              <option key={r.script_id} value={r.script_id}>{r.title || r.script_id}</option>
            ))}
          </select>
          {selectedRule?.params_schema.map(p => (
            <div key={p.name} style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 12, color: colors.slate, display: 'block', marginBottom: 2 }}>{p.label || p.name}</label>
              {p.type === 'boolean' ? (
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={params[p.name] === 'true'}
                    onChange={e => setParams(prev => ({ ...prev, [p.name]: String(e.target.checked) }))}
                    style={{ width: 16, height: 16 }}
                  />
                  <span style={{ fontSize: 13, color: colors.ink }}>{p.label || p.name}</span>
                </label>
              ) : p.type === 'select' && p.options ? (
                <select
                  value={params[p.name] || ''}
                  onChange={e => setParams(prev => ({ ...prev, [p.name]: e.target.value }))}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: radius.sm, border: `1px solid ${colors.borderLight}`, fontSize: 13 }}
                >
                  <option value="">请选择...</option>
                  {p.options.map((opt: string) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : p.type === 'string' ? (
                <input
                  type="text"
                  value={params[p.name] || ''}
                  onChange={e => setParams(prev => ({ ...prev, [p.name]: e.target.value }))}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: radius.sm, border: `1px solid ${colors.borderLight}`, fontSize: 13 }}
                />
              ) : (
                <input
                  type="number"
                  step="any"
                  value={params[p.name] || ''}
                  onChange={e => setParams(prev => ({ ...prev, [p.name]: e.target.value }))}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: radius.sm, border: `1px solid ${colors.borderLight}`, fontSize: 13 }}
                />
              )}
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <button onClick={() => setShowAdd(false)} style={smallBtn(colors.slate, colors.white)}>取消</button>
            <button onClick={handleAdd} style={smallBtn(colors.yellow, colors.ink)}>添加</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setShowAdd(true)} style={{
          background: 'none', border: `1px dashed ${colors.borderLight}`, borderRadius: radius.sm,
          padding: '8px 16px', color: colors.slate, cursor: 'pointer', marginTop: 8, fontSize: 13,
        }}>
          + 添加规则
        </button>
      )}
    </div>
  );
}

function smallBtn(bg: string, fg: string): React.CSSProperties {
  return {
    background: bg, color: fg, border: 'none', borderRadius: radius.sm,
    padding: '6px 16px', fontWeight: 600, fontSize: 13, cursor: 'pointer',
  };
}
