"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  api,
  totalsText,
  type CurrencyTotal,
  type Invoice,
} from "@/lib/api";
import { Empty, LoadError, Loading, formatDate } from "@/components/common";
import { RecordPaymentForm } from "@/components/forms";

/**
 * Collections, not a filtered invoice list.
 *
 * The ordering is the point: most overdue first, because that is the order a
 * freelancer chases in. Each row offers the two things you actually do next —
 * draft a reminder, or record the money that just arrived.
 */
export default function OverduePage() {
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [total, setTotal] = useState<CurrencyTotal[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [paying, setPaying] = useState<Invoice | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .overdue()
      .then((body) => {
        setInvoices(body.invoices);
        setTotal(body.overdue_total);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, []);

  useEffect(load, [load]);

  function flash(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3200);
  }

  async function draftReminder(invoice: Invoice) {
    setBusyId(invoice.invoice_id);
    try {
      const result = await api.createReminder(invoice.invoice_id);
      flash(
        result.status === "already_exists"
          ? `${invoice.invoice_number} already has a reminder drafted`
          : `Reminder drafted for ${invoice.client_name}`,
      );
    } catch (err) {
      flash((err as ApiError).message);
    } finally {
      setBusyId(null);
    }
  }

  const worst = invoices?.[0];

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Overdue</h1>
          <p className="page-sub">
            Past their due date with money still owed, most overdue first.
            Nothing here is stored — it is worked out from due dates and the
            payment ledger each time you look.
          </p>
        </div>
        <div className="actions">
          <Link className="btn" href="/reminders">
            View reminders
          </Link>
        </div>
      </div>

      {error ? <LoadError error={error} /> : null}

      <div className="stat-row">
        <div className="stat">
          <div className="label">Total overdue</div>
          <div className="value overdue">{totalsText(total, "₹0.00")}</div>
        </div>
        <div className="stat">
          <div className="label">Invoices late</div>
          <div className="value">{invoices?.length ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Longest overdue</div>
          <div className="value">
            {worst ? `${worst.days_overdue} days` : "—"}
          </div>
          {worst ? <div className="note">{worst.client_name}</div> : null}
        </div>
      </div>

      <div className="panel">
        {invoices === null && !error ? (
          <Loading what="overdue invoices" />
        ) : (invoices ?? []).length === 0 ? (
          <Empty>
            <strong>Nothing is overdue</strong>
            Every invoice with a due date has either been paid or is still
            within terms.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="num">Late by</th>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th className="num">Outstanding</th>
                  <th>Due</th>
                  <th className="num">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(invoices ?? []).map((invoice) => (
                  <tr key={invoice.invoice_id}>
                    <td className="num">
                      <span className="badge overdue" style={{ marginLeft: 0 }}>
                        {invoice.days_overdue}d
                      </span>
                    </td>
                    <td className="mono">
                      <Link className="link" href={`/invoices/${invoice.invoice_id}`}>
                        {invoice.invoice_number}
                      </Link>
                    </td>
                    <td>
                      <div className="cell-stack">
                        <span className="lead">{invoice.client_name}</span>
                        <span className="sub">{invoice.project}</span>
                      </div>
                    </td>
                    <td className="num strong">{invoice.outstanding_display}</td>
                    <td className="muted">{formatDate(invoice.due_date)}</td>
                    <td className="num">
                      <div className="row-actions">
                        <button
                          className="btn"
                          onClick={() => draftReminder(invoice)}
                          disabled={busyId === invoice.invoice_id}
                        >
                          {busyId === invoice.invoice_id
                            ? "Drafting…"
                            : "Draft reminder"}
                        </button>
                        <button
                          className="btn primary"
                          onClick={() => setPaying(invoice)}
                        >
                          Record payment
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {paying ? (
        <RecordPaymentForm
          invoice={paying}
          onClose={() => setPaying(null)}
          onDone={() => {
            load();
            flash("Payment recorded — balance updated");
          }}
        />
      ) : null}

      {toast ? <div className="toast">{toast}</div> : null}
    </>
  );
}
