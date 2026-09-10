"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ApiError, api, type Invoice, type Payment } from "@/lib/api";
import {
  Empty,
  LoadError,
  Loading,
  OverdueBadge,
  StatusBadge,
  formatDate,
} from "@/components/common";
import { RecordPaymentForm } from "@/components/forms";

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const invoiceId = Number(params.id);

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [paying, setPaying] = useState(false);
  const [reminding, setReminding] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .invoice(invoiceId)
      .then((body) => {
        setInvoice(body.invoice);
        setPayments(body.payments);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, [invoiceId]);

  useEffect(load, [load]);

  function flash(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3200);
  }

  async function draftReminder() {
    setReminding(true);
    try {
      const result = await api.createReminder(invoiceId);
      flash(
        result.status === "already_exists"
          ? "A reminder is already drafted for this invoice"
          : "Reminder drafted — review it under Reminders",
      );
    } catch (err) {
      flash((err as ApiError).message);
    } finally {
      setReminding(false);
    }
  }

  if (error) {
    return (
      <>
        <Link className="back-link" href="/invoices">
          ← Invoices
        </Link>
        <LoadError error={error} />
      </>
    );
  }

  if (!invoice) return <Loading what="this invoice" />;

  const paidPercent =
    invoice.amount_minor > 0
      ? Math.round((invoice.amount_paid_minor / invoice.amount_minor) * 100)
      : 0;

  return (
    <>
      <Link className="back-link" href="/invoices">
        ← Invoices
      </Link>

      <div className="page-head">
        <div>
          <h1 className="page-title">
            {invoice.invoice_number}{" "}
            <StatusBadge invoice={invoice} />
            <OverdueBadge invoice={invoice} />
          </h1>
          <p className="page-sub">
            {invoice.client_name} · {invoice.project}
          </p>
        </div>
        <div className="actions">
          {invoice.outstanding_minor > 0 &&
          invoice.invoice_status !== "CANCELLED" ? (
            <>
              <button className="btn" onClick={draftReminder} disabled={reminding}>
                {reminding ? "Drafting…" : "Draft reminder"}
              </button>
              <button className="btn primary" onClick={() => setPaying(true)}>
                Record payment
              </button>
            </>
          ) : null}
          <a
            className="btn"
            href={api.invoicePdfUrl(invoice.invoice_id)}
            target="_blank"
            rel="noreferrer"
          >
            Download PDF
          </a>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat">
          <div className="label">Invoice total</div>
          <div className="value">{invoice.amount_display}</div>
        </div>
        <div className="stat">
          <div className="label">Paid</div>
          <div className="value">{invoice.amount_paid_display}</div>
          <div className="note">{paidPercent}% of the total</div>
        </div>
        <div className="stat">
          <div className="label">Outstanding</div>
          <div
            className={`value ${invoice.is_overdue ? "overdue" : ""}`}
          >
            {invoice.outstanding_display}
          </div>
          <div className="note">
            {invoice.is_overdue
              ? `${invoice.days_overdue} days past due`
              : invoice.outstanding_minor === 0
                ? "Settled in full"
                : "Not yet due"}
          </div>
        </div>
      </div>

      <div className="progress" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${paidPercent}%` }} />
      </div>

      <div className="detail-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>Payments</h2>
            <span className="hint">
              {payments.length} recorded
            </span>
          </div>
          {payments.length === 0 ? (
            <Empty>
              <strong>Nothing received yet</strong>
              Record a payment and the balance updates here.
            </Empty>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th className="num">Amount</th>
                    <th>Date</th>
                    <th>Method</th>
                    <th className="num">Balance after</th>
                    <th className="num">Receipt</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((payment) => (
                    <tr key={payment.payment_id}>
                      <td className="num strong">{payment.amount_display}</td>
                      <td className="muted">{formatDate(payment.payment_date)}</td>
                      <td className="muted">{payment.method ?? "—"}</td>
                      <td className="num muted">
                        {payment.outstanding_after_display}
                      </td>
                      <td className="num">
                        <a
                          className="btn"
                          href={api.receiptPdfUrl(payment.payment_id)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {payment.receipt_number ?? "Receipt"}
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Details</h2>
          </div>
          <div className="panel-body">
            <dl className="definitions">
              <dt>Client</dt>
              <dd>
                <Link className="link" href={`/clients/${invoice.client_id}`}>
                  {invoice.client_name}
                </Link>
              </dd>

              <dt>Project</dt>
              <dd>{invoice.project}</dd>

              {invoice.description ? (
                <>
                  <dt>Description</dt>
                  <dd>{invoice.description}</dd>
                </>
              ) : null}

              <dt>Issued</dt>
              <dd>{formatDate(invoice.issue_date)}</dd>

              <dt>Due</dt>
              <dd>
                {invoice.due_date ? formatDate(invoice.due_date) : "No due date"}
              </dd>

              <dt>Currency</dt>
              <dd>{invoice.currency}</dd>

              <dt>Document</dt>
              <dd>
                {invoice.pdf_available
                  ? "Generated"
                  : "Generated on first download"}
              </dd>
            </dl>
          </div>
        </div>
      </div>

      {paying ? (
        <RecordPaymentForm
          invoice={invoice}
          onClose={() => setPaying(false)}
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
