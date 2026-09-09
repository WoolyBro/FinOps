"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type Client, type Invoice } from "@/lib/api";
import {
  Empty,
  LoadError,
  Loading,
  OverdueBadge,
  StatusBadge,
  formatDate,
} from "@/components/common";
import { NewInvoiceForm, RecordPaymentForm } from "@/components/forms";

type Filter = "ALL" | "UNPAID" | "PARTIALLY_PAID" | "PAID" | "OVERDUE";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [creating, setCreating] = useState(false);
  const [paying, setPaying] = useState<Invoice | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.invoices(), api.clients()])
      .then(([i, c]) => {
        setInvoices(i.invoices);
        setClients(c.clients);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, []);

  useEffect(load, [load]);

  function flash(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3000);
  }

  const shown = (invoices ?? []).filter((invoice) => {
    if (filter === "ALL") return true;
    if (filter === "OVERDUE") return invoice.is_overdue;
    return invoice.invoice_status === filter;
  });

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Invoices</h1>
          <p className="page-sub">
            Paid and outstanding are computed from the payment ledger, not
            stored on the invoice.
          </p>
        </div>
        <div className="actions">
          <button
            className="btn primary"
            onClick={() => setCreating(true)}
            disabled={clients.length === 0}
            title={clients.length === 0 ? "Add a client first" : undefined}
          >
            + New invoice
          </button>
        </div>
      </div>

      {error ? <LoadError error={error} /> : null}

      <div className="segmented" role="group" aria-label="Filter invoices">
        {(["ALL", "UNPAID", "PARTIALLY_PAID", "PAID", "OVERDUE"] as Filter[]).map(
          (option) => (
            <button
              key={option}
              aria-pressed={filter === option}
              onClick={() => setFilter(option)}
            >
              {option === "ALL"
                ? "All"
                : option === "PARTIALLY_PAID"
                  ? "Partially paid"
                  : option.charAt(0) + option.slice(1).toLowerCase()}
            </button>
          ),
        )}
      </div>

      <div className="panel">
        {invoices === null && !error ? (
          <Loading what="invoices" />
        ) : shown.length === 0 ? (
          <Empty>
            {invoices?.length === 0 ? (
              <>
                <strong>No invoices yet</strong>
                Raise your first one and it will appear here with its balance.
              </>
            ) : (
              <>
                <strong>Nothing matches this filter</strong>
                Try a different status.
              </>
            )}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="num">Amount</th>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Status</th>
                  <th>Due</th>
                  <th className="num">Actions</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((invoice) => (
                  <tr key={invoice.invoice_id}>
                    <td className="num">
                      <div className="cell-stack" style={{ alignItems: "flex-end" }}>
                        <span className="lead">{invoice.amount_display}</span>
                        {invoice.outstanding_minor > 0 &&
                        invoice.amount_paid_minor > 0 ? (
                          <span className="sub">
                            {invoice.outstanding_display} outstanding
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="mono">{invoice.invoice_number}</td>
                    <td>
                      <div className="cell-stack">
                        <span className="lead">{invoice.client_name}</span>
                        <span className="sub">{invoice.project}</span>
                      </div>
                    </td>
                    <td>
                      <StatusBadge invoice={invoice} />
                      <OverdueBadge invoice={invoice} />
                    </td>
                    <td className="muted">{formatDate(invoice.due_date)}</td>
                    <td className="num">
                      <div className="row-actions">
                        {invoice.outstanding_minor > 0 &&
                        invoice.invoice_status !== "CANCELLED" ? (
                          <button
                            className="btn"
                            onClick={() => setPaying(invoice)}
                          >
                            Record payment
                          </button>
                        ) : null}
                        <a
                          className="btn"
                          href={api.invoicePdfUrl(invoice.invoice_id)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          PDF
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {creating ? (
        <NewInvoiceForm
          clients={clients}
          onClose={() => setCreating(false)}
          onDone={() => {
            load();
            flash("Invoice created");
          }}
        />
      ) : null}

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
