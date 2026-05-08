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
  symbol: string;
  name: string;
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
  enabled: boolean;
  params: Record<string, unknown>;
}

export interface RuleResult {
  rule_id: string;
  script_id: string;
  status: 'normal' | 'triggered' | 'unknown' | 'error';
  level: 'info' | 'warning' | 'danger';
  message: string;
}

export interface PositionDetail {
  position: {
    id: string;
    symbol: string;
    name: string;
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
  yellow_line: number | null;
  white_line: number | null;
  single_pin_short: number | null;
  single_pin_mid: number | null;
  single_pin_mid_long: number | null;
  single_pin_long: number | null;
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

// --- API functions ---

export const api = {
  health: () => request<{ status: string }>('/health'),

  listPositions: () => request<PositionListResponse>('/positions'),

  getPosition: (symbol: string) =>
    request<PositionDetail>(`/positions/${symbol}`),

  getIntraday: (symbol: string) =>
    request<IntradayResponse>(`/positions/${symbol}/intraday`),

  getDaily: (symbol: string) =>
    request<DailyResponse>(`/positions/${symbol}/daily`),

  addTransaction: (symbol: string, txn: Record<string, unknown>) =>
    request<Transaction>(`/positions/${symbol}/transactions`, {
      method: 'POST',
      body: JSON.stringify(txn),
    }),

  editTransaction: (symbol: string, txnId: string, updates: Record<string, unknown>) =>
    request<Transaction>(`/positions/${symbol}/transactions/${txnId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  voidTransaction: (symbol: string, txnId: string, reason?: string) =>
    request<Transaction>(`/positions/${symbol}/transactions/${txnId}/void`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    }),

  addRule: (symbol: string, rule: { category: string; script_id: string; params?: Record<string, unknown> }) =>
    request<PositionRule>(`/positions/${symbol}/rules`, {
      method: 'POST',
      body: JSON.stringify(rule),
    }),

  deleteRule: (symbol: string, ruleId: string) =>
    request<{ ok: boolean }>(`/positions/${symbol}/rules/${ruleId}`, {
      method: 'DELETE',
    }),

  listAvailableRules: () =>
    request<AvailableRule[]>('/rules/available'),

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
};
