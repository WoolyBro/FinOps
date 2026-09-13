export type CurrencyTotal = {
  currency: string;
  total_minor: number;
  total_display: string;
};

export type InvoiceStatus = "UNPAID" | "PARTIALLY_PAID" | "PAID" | "CANCELLED";

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
  invoice_status: InvoiceStatus;
  is_overdue: boolean;
  days_overdue: number;
  pdf_available: boolean;
};

export type Payment = {
  payment_id: number;
  invoice_id: number;
  invoice_number: string;
  client_id: number;
  client_name: string;
  project: string;
  amount_minor: number;
  amount_display: string;
  payment_date: string;
  method: string | null;
  reference: string | null;
  /** Null until a receipt is issued; opening the receipt issues it. */
  receipt_number: string | null;
  receipt_available: boolean;
  outstanding_after_display: string;
  /** The invoice total and paid-to-date as they stood after this payment. */
  invoice_amount_display: string;
  paid_to_date_display: string;
  invoice_status: InvoiceStatus;
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

export type OldestOverdue = {
  invoice_id: number;
  invoice_number: string;
  client_id: number;
  client_name: string;
  days_overdue: number;
};

export type Summary = {
  period_start: string;
  period_end: string;
  received_total: CurrencyTotal[];
  invoiced_total: CurrencyTotal[];
  outstanding_total: CurrencyTotal[];
  overdue_total: CurrencyTotal[];
  /** Live (non-cancelled) invoices issued in the period. */
  invoices_issued_in_period: number;
  /** UNPAID / PARTIALLY_PAID / PAID — a true partition of the above. */
  invoice_counts_in_period: Record<string, number>;
  cancelled_in_period: number;
  /** Of the invoices issued in the period, how many are late today. A qualifier, not a status. */
  overdue_in_period: number;
  payments_in_period: number;
  open_invoice_count: number;
  overdue_invoice_count: number;
  oldest_overdue: OldestOverdue | null;
};

export type ActivityEvent = {
  kind: 'invoice' | 'payment';
  date: string;
  created_at: string | null;
  invoice_id: number;
  invoice_number: string;
  client_id: number;
  client_name: string;
  amount_display: string;
  payment_id: number | null;
};

export type Overview = {
  as_of: string;
  currency: string;
  outstanding_total: CurrencyTotal[];
  overdue_total: CurrencyTotal[];
  open_invoice_count: number;
  overdue_invoice_count: number;
  oldest_overdue: OldestOverdue | null;
  client_count: number;
  clients_with_balance: number;
  average_days_to_payment: number | null;
  settled_invoice_count: number;
  month: {
    name: string;
    start: string;
    end: string;
    invoiced_total: CurrencyTotal[];
    received_total: CurrencyTotal[];
    invoices_issued: number;
    payments_received: number;
    collection_rate_percent: number | null;
  };
  needs_attention: Invoice[];
  recent_activity: ActivityEvent[];
};

export type MonthPoint = {
  month: string;
  label: string;
  name: string;
  invoiced_minor: number;
  received_minor: number;
  invoiced_display: string;
  received_display: string;
  invoice_count: number;
  payment_count: number;
};

export type MonthlySeries = {
  currency: string;
  period_start: string;
  period_end: string;
  months: MonthPoint[];
  scale_max_minor: number;
  ticks: { minor: number; display: string }[];
  other_currencies: string[];
};

export type ClientBreakdownRow = {
  client_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  invoice_count: number;
  paid_invoice_count: number;
  open_invoice_count: number;
  overdue_invoice_count: number;
  invoiced_total: CurrencyTotal[];
  received_total: CurrencyTotal[];
  outstanding_total: CurrencyTotal[];
  overdue_total: CurrencyTotal[];
};

export type ClientBreakdown = {
  period_start: string | null;
  period_end: string | null;
  count: number;
  clients: ClientBreakdownRow[];
};

export type ReminderStatus = "DRAFT" | "APPROVED" | "SENT" | "CANCELLED";

export type Reminder = {
  reminder_id: number;
  invoice_id: number;
  invoice_number: string;
  client_id: number;
  client_name: string;
  client_email: string | null;
  project: string;
  channel: string;
  message: string;
  reminder_status: ReminderStatus;
  created_at: string;
  sent_at: string | null;
  /** The invoice's balance today — the message is a snapshot from drafting. */
  current_outstanding_display?: string | null;
  current_outstanding_minor?: number | null;
  /** A payment landed after drafting, so the amount in the message is wrong. */
  balance_changed?: boolean;
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
  /** The tool's own status field ("found", "recorded", "error", …). */
  status: string | null;
  /** Set only when the tool raised, rather than returning a refusal. */
  error: string | null;
  duration_seconds: number | null;
};

/** Built by the server from the tool's result — never from the model's reply. */
export type ChatResultCard =
  | { type: 'payment'; payment: Payment; invoice: Invoice }
  | { type: 'invoice'; invoice: Invoice }
  | { type: 'reminder'; reminder: Reminder };

export type ChatResponse = {
  session_id: string;
  reply: string;
  tool_calls: ToolCall[];
  turn: number;
  elapsed_seconds: number;
  result_card: ChatResultCard | null;
};

export type ParsedAmount = {
  amount_minor: number;
  currency: string;
  amount_display: string;
};

export type ApiError = {
  error: string;
  detail: string;
  status?: number;
  /** For a 409, the tool's full result — e.g. the existing record it matched. */
  result?: Record<string, any>;
};

export type ToastMessage = {
  id: string;
  text: string;
};
