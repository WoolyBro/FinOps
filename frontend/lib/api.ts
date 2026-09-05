/**
 * The only place the frontend knows a backend exists.
 *
 * The browser talks to FastAPI, never to Strands. Every figure rendered here
 * was derived server-side from the invoice and payment ledger -- the UI does no
 * money arithmetic of its own, so it cannot disagree with the documents.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      0,
      "unreachable",
      `Could not reach the API at ${API_BASE}. Is the backend running?`,
    );
  }

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.error ?? "error",
      body?.detail ?? response.statusText,
    );
  }
  return body as T;
}

// --- shapes the API returns -------------------------------------------------

export type CurrencyTotal = {
  currency: string;
  total_minor: number;
  total_display: string;
};

export type Invoice = {
  invoice_id: number;
  invoice_number: string;
  client_id: number;
  client_name: string;
  project: string;
  description: string | null;
  currency: string;
  amount_minor: number;
  amount_paid_minor: number;
  outstanding_minor: number;
  amount_display: string;
  amount_paid_display: string;
  outstanding_display: string;
  issue_date: string;
  due_date: string | null;
  invoice_status: "UNPAID" | "PARTIALLY_PAID" | "PAID" | "CANCELLED";
  is_overdue: boolean;
  days_overdue: number;
  pdf_path: string | null;
};

export type Payment = {
  payment_id: number;
  invoice_id: number;
  invoice_number: string;
  client_id: number;
  client_name: string;
  project: string;
  amount_display: string;
  amount_minor: number;
  payment_date: string;
  method: string | null;
  reference: string | null;
  receipt_number: string | null;
  outstanding_after_display: string;
};

export type Client = {
  client_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  created_at: string;
};

export type ClientBalance = {
  client_id: number;
  client_name: string;
  invoice_count: number;
  invoice_counts_by_status: Record<string, number>;
  invoiced_total: CurrencyTotal[];
  paid_total: CurrencyTotal[];
  outstanding_total: CurrencyTotal[];
  overdue_total: CurrencyTotal[];
};

export type Summary = {
  period_start: string;
  period_end: string;
  received_total: CurrencyTotal[];
  outstanding_total: CurrencyTotal[];
  overdue_total: CurrencyTotal[];
  invoices_issued_in_period: number;
  invoice_counts_in_period: Record<string, number>;
};

export type AgentStatus = {
  available: boolean;
  provider: string | null;
  model_id: string | null;
  detail: string | null;
  active_sessions: number;
};

export type ToolCall = {
  tool: string;
  arguments: Record<string, unknown>;
  status: string | null;
  error: string | null;
  duration_seconds: number | null;
};

export type ChatResponse = {
  session_id: string;
  reply: string;
  tool_calls: ToolCall[];
  turn: number;
  elapsed_seconds: number;
};

// --- endpoints --------------------------------------------------------------

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  agentStatus: () => request<AgentStatus>("/api/agent/status"),

  chat: (message: string, sessionId: string | null) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),

  clients: () =>
    request<{ count: number; clients: Client[] }>("/api/clients"),

  client: (id: number) =>
    request<{
      balance: ClientBalance;
      invoices: Invoice[];
      payments: Payment[];
    }>(`/api/clients/${id}`),

  invoices: () =>
    request<{ count: number; invoices: Invoice[] }>("/api/invoices"),

  payments: () =>
    request<{ count: number; payments: Payment[] }>("/api/payments"),

  summary: () => request<Summary>("/api/reports/summary"),

  overdue: () =>
    request<{ count: number; invoices: Invoice[]; overdue_total: CurrencyTotal[] }>(
      "/api/reports/overdue",
    ),

  outstanding: () =>
    request<{
      count: number;
      invoices: Invoice[];
      outstanding_total: CurrencyTotal[];
    }>("/api/reports/outstanding"),

  invoicePdfUrl: (id: number) => `${API_BASE}/api/invoices/${id}/pdf`,
  receiptPdfUrl: (paymentId: number) =>
    `${API_BASE}/api/payments/${paymentId}/receipt`,
};

/** A currency total list rendered for a stat tile. Empty means nothing owed. */
export function totalsText(totals: CurrencyTotal[], zero = "—"): string {
  if (!totals || totals.length === 0) return zero;
  return totals.map((t) => t.total_display).join("  ·  ");
}
