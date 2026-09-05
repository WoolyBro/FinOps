"use client";

import { ApiError, type Invoice } from "@/lib/api";

export function StatusBadge({ invoice }: { invoice: Invoice }) {
  return (
    <span className={`badge ${invoice.invoice_status}`}>
      {invoice.invoice_status.replace("_", " ")}
    </span>
  );
}

export function OverdueBadge({ invoice }: { invoice: Invoice }) {
  if (!invoice.is_overdue) return null;
  const days = invoice.days_overdue;
  return (
    <span className="badge overdue" style={{ marginLeft: 6 }}>
      {days} {days === 1 ? "day" : "days"} late
    </span>
  );
}

/** One place to render a failed fetch, so no page invents a fallback figure. */
export function LoadError({ error }: { error: ApiError | Error }) {
  const isApi = error instanceof ApiError;
  return (
    <div className="notice error">
      <h3>
        {isApi && error.code === "unreachable"
          ? "Cannot reach the API"
          : "Could not load this data"}
      </h3>
      <div>{error.message}</div>
      {isApi && error.code === "unreachable" ? (
        <pre>uvicorn app.api.main:app --reload --port 8000</pre>
      ) : null}
    </div>
  );
}

export function Loading({ what }: { what: string }) {
  return <div className="empty">Loading {what}…</div>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
