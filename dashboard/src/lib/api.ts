/**
 * API client for ermis backend.
 * Token lives in localStorage under 'mk_token'.
 */

const BASE = '';

function getToken(): string | null {
  return localStorage.getItem('mk_token');
}

function headers(extra: Record<string, string> = {}): HeadersInit {
  const token = getToken();
  const h: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
  return h;
}

async function req<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: headers(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...opts,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────
  register: (email: string, password: string, display_name?: string) =>
    req<{ id: string }>('POST', '/auth/register', { email, password, display_name }),

  login: (email: string, password: string) =>
    req<{ token: string; user: User }>('POST', '/auth/login', { email, password }),

  logout: () => req<{ logged_out: boolean }>('POST', '/auth/logout', { token: getToken() }),

  me: () => req<User>('GET', '/me'),

  // ── Strategies ────────────────────────────────────────────────────
  listStrategies: (params?: { state?: string; market?: string }) => {
    const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : '';
    return req<Strategy[]>('GET', `/strategies${qs ? '?' + qs : ''}`);
  },

  getStrategy: (id: string) => req<Strategy>('GET', `/strategies/${id}`),

  createStrategy: (data: Partial<Strategy>) => req<Strategy>('POST', '/strategies', data),

  updateStrategy: (id: string, data: Partial<Strategy>) =>
    req<Strategy>('PATCH', `/strategies/${id}`, data),

  deleteStrategy: (id: string) => req<{ deleted: boolean }>('DELETE', `/strategies/${id}`),

  transitionStrategy: (
    id: string,
    target_state: string,
    opts?: { reason?: string; confirm_live?: boolean; confirmation_string?: string },
  ) => req<Strategy>('POST', `/strategies/${id}/transition`, { target_state, ...opts }),

  // ── Signals ──────────────────────────────────────────────────────
  listSignals: (params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = params
      ? new URLSearchParams(
          Object.fromEntries(
            Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][],
          ),
        ).toString()
      : '';
    return req<Signal[]>('GET', `/signals${qs ? '?' + qs : ''}`);
  },

  createSignal: (data: Partial<Signal>) => req<Signal>('POST', '/signals', data),

  getSignal: (id: string) => req<Signal>('GET', `/signals/${id}`),

  updateSignalStatus: (id: string, status: string) =>
    req<Signal>('PATCH', `/signals/${id}/status`, { signal_status: status }),

  // ── Followups ─────────────────────────────────────────────────────
  listFollowups: (signalId: string) =>
    req<Followup[]>('GET', `/followups?signal_id=${signalId}`),

  createFollowup: (data: { signal_id: string; event_type: string; detail?: Record<string, unknown> }) =>
    req<Followup>('POST', '/followups', data),

  // ── Automation ────────────────────────────────────────────────────
  listAutomationRules: (params?: { strategy_id?: string; trigger?: string }) => {
    const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : '';
    return req<AutomationRule[]>('GET', `/automation/rules${qs ? '?' + qs : ''}`);
  },

  createAutomationRule: (data: Partial<AutomationRule>) =>
    req<AutomationRule>('POST', '/automation/rules', data),

  updateAutomationRule: (id: string, data: Partial<AutomationRule>) =>
    req<AutomationRule>('PATCH', `/automation/rules/${id}`, data),

  deleteAutomationRule: (id: string) =>
    req<{ deleted: boolean }>('DELETE', `/automation/rules/${id}`),

  // ── Connections ───────────────────────────────────────────────────
  listConnections: (params?: { venue?: string }) => {
    const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : '';
    return req<Connection[]>('GET', `/connections${qs ? '?' + qs : ''}`);
  },

  createConnection: (data: Partial<Connection>) =>
    req<Connection>('POST', '/connections', data),

  testConnection: (id: string) =>
    req<{ success: boolean; message: string }>('POST', `/connections/${id}/test`),

  deleteConnection: (id: string) =>
    req<{ deleted: boolean }>('DELETE', `/connections/${id}`),

  // ── Publishing ───────────────────────────────────────────────────
  getPublishingConfig: () => req<PublishingConfig>('GET', '/publishing/config'),
  updatePublishingConfig: (data: Partial<PublishingConfig>) =>
    req<PublishingConfig>('PUT', '/publishing/config', data),
  publishTelegram: (signalId?: string, template?: string) =>
    req<{ published: boolean; message_id?: string }>('POST', '/publishing/telegram', {
      signal_id: signalId, template,
    }),
  publishSquare: (signalId?: string, template?: string) =>
    req<{ published: boolean; post_id?: string }>('POST', '/publishing/square', {
      signal_id: signalId, template,
    }),
  listPublications: (limit = 50) =>
    req<Publication[]>('GET', `/publishing/publications?limit=${limit}`),

  // ── Health ────────────────────────────────────────────────────────
  health: () => req<HealthStatus>('GET', '/health/system'),
};

// ── Types ──────────────────────────────────────────────────────────────────────

export type LifecycleState =
  | 'DRAFT' | 'PBT' | 'KTEST' | 'PAPER' | 'TESTNET'
  | 'LIVE_ELIGIBLE' | 'LIVE' | 'PAUSED' | 'STOPPED' | 'KILLED';

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  is_admin?: boolean;
}

export interface Strategy {
  id: string;
  user_id: string;
  name: string;
  description: string;
  version: number;
  lifecycle_state: string;
  execution_mode: string;
  execution_venue: string;
  market: string;
  timeframe: string;
  entry_config: Record<string, unknown>;
  exit_config: Record<string, unknown>;
  risk_config: Record<string, unknown>;
  template_name: string | null;
  template_params: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Signal {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  status: string;
  strategy_name: string;
  strategy_id: string | null;
  user_id: string;
  entry_price: string | null;
  tp1: string | null;
  tp2: string | null;
  stop_loss: string | null;
  mode: string;
  reason: string[];
  created_at: string;
  updated_at: string;
}

export interface Followup {
  id: string;
  signal_id: string;
  event_type: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRule {
  id: string;
  name: string;
  trigger: string;
  conditions: AutomationCondition[];
  actions: AutomationAction[];
  enabled: boolean;
  created_at: string;
}

export interface AutomationCondition {
  field: string;
  operator: string;
  value: unknown;
}

export interface AutomationAction {
  type: string;
  params: Record<string, unknown>;
}

export interface Connection {
  id: string;
  venue: string;
  label: string;
  status: string;
  created_at: string;
}

export interface PublishingConfig {
  telegram_enabled: boolean;
  square_enabled: boolean;
  square_limit_daily: number;
}

export interface Publication {
  id: string;
  signal_id: string;
  channel: string;
  template: string;
  post_id: string | null;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  services: Record<string, { status: string; detail?: string }>;
}
