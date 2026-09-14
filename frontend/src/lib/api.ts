/**
 * The only place the frontend knows a backend exists.
 *
 * Every figure the interface renders was derived by the server from the
 * invoice and payment ledger. Nothing here adds money up, formats a currency,
 * or invents a record — if the server did not say it, the page does not show
 * it. There is deliberately no mock mode: a demo that can quietly fall back to
 * fabricated data is a demo you cannot trust on camera.
 */

import type {
  AgentStatus,
  ApiError,
  ChatResponse,
  Client,
  ClientBalance,
  ClientBreakdown,
  CurrencyTotal,
  Invoice,
  MonthlySeries,
  Overview,
  ParsedAmount,
  Payment,
  Reminder,
  Summary,
} from '../types';

/** Empty in development: Vite proxies /api to FastAPI on the same origin. */
export const API_BASE: string = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

/**
 * This browser's demo sandbox: a private copy of the sample ledger on the
 * server. Kept in localStorage so a refresh returns to the same copy — a
 * payment recorded before the refresh is still there after it — while other
 * browsers get their own. The server creates the copy the first time it sees
 * the id, so a wiped server simply hands this id a fresh one.
 */
const SANDBOX_KEY = 'ff.sandbox';
let memorySandbox: string | null = null;

function newSandboxId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return 'sbx-' + Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

export function sandboxId(): string {
  try {
    const stored = localStorage.getItem(SANDBOX_KEY);
    if (stored && /^sbx-[0-9a-f]{32}$/.test(stored)) return stored;
    const created = newSandboxId();
    localStorage.setItem(SANDBOX_KEY, created);
    return created;
  } catch {
    // Storage blocked (private mode on some browsers): one copy per page load.
    memorySandbox ??= newSandboxId();
    return memorySandbox;
  }
}

/** A plain link cannot send a header, so document URLs name the sandbox in the query. */
function withSandbox(path: string): string {
  return `${API_BASE}${path}${path.includes('?') ? '&' : '?'}workspace=${sandboxId()}`;
}

function query(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') q.set(key, String(value));
  }
  const text = q.toString();
  return text ? `?${text}` : '';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-FF-Workspace': sandboxId(),
        ...(options.headers || {}),
      },
      cache: 'no-store',
    });
  } catch {
    const failure: ApiError = {
      status: 0,
      error: 'unreachable',
      detail: 'Could not reach the FreelanceFlow API. Is the backend running on port 8000?',
    };
    throw failure;
  }

  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // The server sends one shape for every failure: {error, detail[, result]}.
    // Its wording is surfaced verbatim — the tools phrase refusals carefully.
    const failure: ApiError = {
      status: res.status,
      error: body?.error ?? 'error',
      detail: body?.detail ?? `The server returned ${res.status}.`,
      result: body?.result,
    };
    throw failure;
  }
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  // --- status -----------------------------------------------------------

  getHealth: () => request<{ status: string }>('/api/health'),

  getAgentStatus: () => request<AgentStatus>('/api/agent/status'),

  // --- clients ----------------------------------------------------------

  getClients: () => request<{ count: number; clients: Client[] }>('/api/clients'),

  /**
   * An existing name is not an error to the server — it returns that client.
   * The form needs to know, so it is surfaced as a 409 carrying the match.
   */
  async postClient(data: {
    name: string;
    email?: string | null;
    phone?: string | null;
    address?: string | null;
  }): Promise<Client> {
    const body = await post<{ status: string; client: Client }>('/api/clients', data);
    if (body.status === 'already_exists') {
      const failure: ApiError = {
        status: 409,
        error: 'already_exists',
        detail: `${body.client.name} is already on file${body.client.email ? ` (${body.client.email})` : ''}.`,
        result: { client: body.client },
      };
      throw failure;
    }
    return body.client;
  },

  getClientDetail: (id: number) =>
    request<{ balance: ClientBalance; invoices: Invoice[]; payments: Payment[] }>(`/api/clients/${id}`),

  async patchClient(id: number, data: { field: string; value: string | null }): Promise<Client> {
    const body = await request<{ status: string; client: Client }>(`/api/clients/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ field: data.field, value: data.value ?? '' }),
    });
    return body.client;
  },

  // --- invoices ---------------------------------------------------------

  getInvoices: (params: { client_id?: number; status?: string } = {}) =>
    request<{ count: number; invoices: Invoice[] }>(`/api/invoices${query({ ...params, limit: 200 })}`),

  async postInvoice(data: {
    client_id: number;
    project: string;
    amount_minor: number;
    currency?: string;
    issue_date?: string | null;
    due_date?: string | null;
    description?: string | null;
    allow_duplicate?: boolean;
  }): Promise<Invoice> {
    const body = await post<{ status: string; invoice: Invoice }>('/api/invoices', data);
    return body.invoice;
  },

  getInvoiceDetail: (id: number) =>
    request<{ invoice: Invoice; payments: Payment[] }>(`/api/invoices/${id}`),

  invoicePdfUrl: (id: number) => withSandbox(`/api/invoices/${id}/pdf`),

  // --- payments ---------------------------------------------------------

  getPayments: (params: { client_id?: number; start_date?: string; end_date?: string } = {}) =>
    request<{
      count: number;
      payments: Payment[];
      received_total: CurrencyTotal[];
    }>(`/api/payments${query({ ...params, limit: 200 })}`),

  async postPayment(data: {
    invoice_id: number;
    amount_minor: number;
    payment_date?: string | null;
    method?: string | null;
    reference?: string | null;
    allow_duplicate?: boolean;
  }): Promise<{ payment: Payment; invoice: Invoice }> {
    const body = await post<{ status: string; payment: Payment; invoice: Invoice }>('/api/payments', data);
    return { payment: body.payment, invoice: body.invoice };
  },

  /** Opening this issues the receipt if it does not exist yet — one number for life. */
  receiptPdfUrl: (paymentId: number) => withSandbox(`/api/payments/${paymentId}/receipt`),

  // --- reminders --------------------------------------------------------

  getReminders: (params: { status?: string; client_id?: number } = {}) =>
    request<{ count: number; reminders: Reminder[] }>(`/api/reminders${query(params)}`),

  /** `created` is false when a live reminder already existed for the invoice. */
  async postReminder(data: { invoice_id: number; force?: boolean }): Promise<{ reminder: Reminder; created: boolean }> {
    const body = await post<{ status: string; reminder: Reminder }>('/api/reminders', {
      invoice_id: data.invoice_id,
      force: data.force ?? false,
    });
    return { reminder: body.reminder, created: body.status === 'prepared' };
  },

  async approveReminder(id: number): Promise<Reminder> {
    return (await post<{ reminder: Reminder }>(`/api/reminders/${id}/approve`)).reminder;
  },

  /** Kept on record as CANCELLED, never deleted. */
  async discardReminder(id: number): Promise<Reminder> {
    return (await post<{ reminder: Reminder }>(`/api/reminders/${id}/cancel`)).reminder;
  },

  // --- reports ----------------------------------------------------------

  getOverview: () => request<Overview>('/api/reports/overview'),

  getReportsSummary: (startDate?: string, endDate?: string) =>
    request<Summary>(`/api/reports/summary${query({ start_date: startDate, end_date: endDate })}`),

  getMonthly: (months = 6) => request<MonthlySeries>(`/api/reports/monthly${query({ months })}`),

  getClientBreakdown: (startDate?: string, endDate?: string) =>
    request<ClientBreakdown>(`/api/reports/clients${query({ start_date: startDate, end_date: endDate })}`),

  getReportsOverdue: () =>
    request<{ count: number; invoices: Invoice[]; overdue_total: CurrencyTotal[] }>('/api/reports/overdue'),

  getReportsOutstanding: () =>
    request<{ count: number; invoices: Invoice[]; outstanding_total: CurrencyTotal[] }>('/api/reports/outstanding'),

  // --- amounts ----------------------------------------------------------

  /** The same parser the agent uses. The browser never converts "40k" itself. */
  parseAmount: (text: string, default_currency = 'INR') =>
    post<ParsedAmount>('/api/amounts/parse', { text, default_currency }),

  // --- the agent --------------------------------------------------------

  /**
   * One turn. Pass null to start a conversation; the server issues the
   * session id, and only server-issued ids continue a conversation.
   */
  postChat: (message: string, sessionId: string | null) =>
    post<ChatResponse>('/api/chat', { message, session_id: sessionId }),

  resetChat: (sessionId: string) =>
    request<void>(`/api/chat/${sessionId}`, { method: 'DELETE' }),

  // --- demo sandbox -----------------------------------------------------

  /** Restore this browser's copy of the sample ledger. Nobody else's is touched. */
  resetSandbox: () =>
    post<{ status: string; client_count: number; invoice_count: number; payment_count: number }>(
      '/api/sandbox/reset',
    ),
};

/** Render a per-currency total list. Empty means nothing is owed. */
export function totalText(totals: CurrencyTotal[] | undefined, zero = '₹0.00'): string {
  if (!totals || totals.length === 0) return zero;
  return totals.map((t) => t.total_display).join('  ·  ');
}

/** The minor-unit value in one currency, for comparisons only — never for display. */
export function totalMinor(totals: CurrencyTotal[] | undefined, currency = 'INR'): number {
  return totals?.find((t) => t.currency === currency)?.total_minor ?? 0;
}
