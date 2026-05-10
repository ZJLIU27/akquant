/** API client for the AKQuant platform backend. */

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail);
  }
  return res.json();
}

// --- Types ---

export interface PositionSummary {
  id: string;
  symbol: string;
  name: string;
  strategy_id: string;
  strategy_title: string;
  strategy_stage: string;
  strategy_tags: string[];
  rule_count: number;
  risk_rule_count: number;
  alert_rule_count: number;
  rule_titles: string[];
  status: 'open' | 'closed' | 'invalid';
  remaining_quantity: number;
  avg_cost: number;
  cost_amount: number;
  realized_pnl: number;
  unrealized_pnl: number;
  latest_price: number | null;
  price_source: 'intraday' | 'daily_fallback' | 'missing';
  market_value: number;
  position_weight: number;
  notes: string;
}

export interface PositionListResponse {
  positions: PositionSummary[];
  total_market_value: number;
}

export interface Transaction {
  id: string;
  side: 'buy' | 'sell';
  trade_date: string;
  quantity: number;
  price: number;
  fee: number;
  source: string;
  tags: string[];
  notes: string;
  created_at: string;
  updated_at: string;
  revision: number;
  voided: boolean;
  voided_at: string | null;
  void_reason: string | null;
}

export interface PositionRule {
  id: string;
  category: 'risk' | 'alert';
  type: 'script';
  script_id: string;
  strategy_id: string;
  enabled: boolean;
  params: Record<string, unknown>;
}

export interface RuleResult {
  rule_id: string;
  script_id: string;
  status: 'normal' | 'triggered' | 'completed' | 'unknown' | 'error';
  level: 'info' | 'warning' | 'danger';
  message: string;
}

export interface PositionDetail {
  position: {
    id: string;
    symbol: string;
    name: string;
    strategy_id: string;
    strategy_stage: string;
    strategy_tags: string[];
    strategy_note_paths: string[];
    notes: string;
    rules: PositionRule[];
    transactions: Transaction[];
    audit_log: Array<{
      id: string;
      action: string;
      transaction_id: string | null;
      changed_at: string;
      before: Record<string, unknown> | null;
      after: Record<string, unknown> | null;
    }>;
  };
  summary: PositionSummary;
  effective_rules: PositionRule[];
  rule_results: RuleResult[];
}

export interface AvailableRule {
  script_id: string;
  title: string;
  params_schema: Array<{
    name: string;
    type: string;
    required: boolean;
    label: string;
    default?: unknown;
    options?: string[];
  }>;
}

export interface AvailableStrategy {
  strategy_id: string;
  title: string;
  tags: string[];
  note_paths: string[];
  stages: Array<{
    stage_id: string;
    title: string;
    description: string;
    rules: Array<{
      category: 'risk' | 'alert';
      script_id: string;
      params: Record<string, unknown>;
      enabled: boolean;
    }>;
  }>;
}

export interface IntradayResponse {
  symbol: string;
  data: Array<Record<string, unknown>> | null;
  rows: number;
  status: string;
}

export interface DailyRecord {
  date: string;
  open: number | null;
  close: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  volume_color: string;
  yellow_line: number | null;
  white_line: number | null;
  single_pin_short: number | null;
  single_pin_mid: number | null;
  single_pin_mid_long: number | null;
  single_pin_long: number | null;
  kdj_k: number | null;
  kdj_d: number | null;
  kdj_j: number | null;
  macd_dif: number | null;
  macd_dea: number | null;
  macd: number | null;
  brick: number | null;
  brick_base: number | null;
  brick_delta: number | null;
  brick_color: string;
}

export interface DailyResponse {
  symbol: string;
  data: DailyRecord[] | null;
  rows: number;
  status: string;
}

export interface JobStatus {
  job_id: string;
  job_type: string;
  status: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result: string | null;
}

export interface StockSearchResult {
  symbol: string;
  name: string;
  market: string;
}

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

// --- API functions ---

export const api = {
  health: () => request<{ status: string }>('/health'),

  listPositions: () => request<PositionListResponse>('/positions'),

  getPosition: (positionId: string) =>
    request<PositionDetail>(`/positions/${positionId}`),

  getIntraday: (positionId: string) =>
    request<IntradayResponse>(`/positions/${positionId}/intraday`),

  getDaily: (positionId: string) =>
    request<DailyResponse>(`/positions/${positionId}/daily`),

  addTransaction: (positionRef: string, txn: Record<string, unknown>) =>
    request<Transaction>(`/positions/${positionRef}/transactions`, {
      method: 'POST',
      body: JSON.stringify(txn),
    }),

  editTransaction: (positionId: string, txnId: string, updates: TransactionUpdatePayload) =>
    request<Transaction>(`/positions/${positionId}/transactions/${txnId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  voidTransaction: (positionId: string, txnId: string, reason?: string) =>
    request<Transaction>(`/positions/${positionId}/transactions/${txnId}/void`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    }),

  addRule: (positionId: string, rule: { category: string; script_id: string; params?: Record<string, unknown> }) =>
    request<PositionRule>(`/positions/${positionId}/rules`, {
      method: 'POST',
      body: JSON.stringify(rule),
    }),

  deleteRule: (positionId: string, ruleId: string) =>
    request<{ ok: boolean }>(`/positions/${positionId}/rules/${ruleId}`, {
      method: 'DELETE',
    }),

  listAvailableRules: () =>
    request<AvailableRule[]>('/rules/available'),

  listAvailableStrategies: () =>
    request<AvailableStrategy[]>('/strategies/available'),

  bindStrategy: (positionId: string, binding: { strategy_id: string }) =>
    request<PositionDetail['position']>(`/positions/${positionId}/strategy`, {
      method: 'PATCH',
      body: JSON.stringify(binding),
    }),

  validatePositions: () =>
    request<{ valid: boolean; errors: string[] }>('/positions/validate', {
      method: 'POST',
    }),

  triggerIntradayUpdate: (force?: boolean) =>
    request<{ job_id: string | null; status: string }>('/data/update-intraday', {
      method: 'POST',
      body: JSON.stringify({ force: force || false }),
    }),

  triggerDailyUpdate: (symbols?: string[]) =>
    request<{ job_id: string | null; status: string }>('/data/update-daily', {
      method: 'POST',
      body: JSON.stringify({ symbols }),
    }),

  getDataStatus: () =>
    request<{ positions: PositionSummary[]; total_market_value: number }>('/data/status'),

  getJob: (jobId: string) =>
    request<JobStatus>(`/jobs/${jobId}`),

  searchStocks: (q: string, limit = 10) =>
    request<StockSearchResult[]>(`/stocks/search?q=${encodeURIComponent(q)}&limit=${limit}`),
};
