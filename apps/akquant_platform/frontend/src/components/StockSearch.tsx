import { useState, useEffect, useRef, useCallback } from 'react';
import { api, type StockSearchResult } from '../api/client';
import { colors, radius, shadow } from '../theme/variables';

interface Props {
  onSelect: (symbol: string, name: string) => void;
  onClear: () => void;
}

export default function StockSearch({ onSelect, onClear }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const [selected, setSelected] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    setLoading(true);
    try {
      const data = await api.searchStocks(q.trim());
      setResults(data);
      setShowDropdown(data.length > 0);
      setHighlightIndex(-1);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!query.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    timerRef.current = setTimeout(() => search(query), 300);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query, search]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (item: StockSearchResult) => {
    setQuery(`${item.symbol} ${item.name}`);
    setSelected(true);
    setShowDropdown(false);
    onSelect(item.symbol, item.name);
  };

  const handleInputChange = (value: string) => {
    setQuery(value);
    if (selected) {
      setSelected(false);
      onClear();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown || results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIndex(i => (i + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIndex(i => (i - 1 + results.length) % results.length);
    } else if (e.key === 'Enter' && highlightIndex >= 0) {
      e.preventDefault();
      handleSelect(results[highlightIndex]);
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <div style={{ position: 'relative' }}>
        <input
          value={query}
          onChange={e => handleInputChange(e.target.value)}
          onFocus={() => { if (results.length > 0 && query.trim()) setShowDropdown(true); }}
          onKeyDown={handleKeyDown}
          placeholder="输入股票代码或名称搜索..."
          style={{
            width: '100%',
            padding: '8px 12px',
            paddingRight: loading ? 32 : 12,
            border: `1px solid ${selected ? colors.green : colors.borderLight}`,
            borderRadius: radius.sm,
            fontSize: 14,
            color: colors.ink,
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        {loading && (
          <span style={{
            position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, color: colors.slate,
          }}>
            ...
          </span>
        )}
      </div>
      {showDropdown && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0,
          background: colors.white,
          border: `1px solid ${colors.borderLight}`,
          borderRadius: radius.sm,
          boxShadow: shadow.medium,
          zIndex: 100,
          maxHeight: 240,
          overflowY: 'auto',
          marginTop: 2,
        }}>
          {results.map((r, i) => (
            <div
              key={r.symbol}
              onMouseDown={() => handleSelect(r)}
              onMouseEnter={() => setHighlightIndex(i)}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                background: i === highlightIndex ? colors.snow : 'transparent',
                fontSize: 14,
              }}
            >
              <span style={{ fontWeight: 600, color: colors.ink }}>{r.symbol}</span>
              <span style={{ marginLeft: 12, color: colors.slate }}>{r.name}</span>
              <span style={{ float: 'right', fontSize: 12, color: colors.muted }}>{r.market}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
