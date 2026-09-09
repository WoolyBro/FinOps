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

      <div className="actions" style={{ marginBottom: 14 }}>
        {(["ALL", "UNPAID", "PARTIALLY_PAID", "PAID", "OVERDUE"] as Filter[]).map(
          (option) => (
            <button
              key={option}
              className={`btn ${filter === option ? "primary" : ""}`}
              onClick={() => setFilter(option)}
            >
              {option.replace("_", " ")}
            </button>
          ),
        )}
      </div>

      <div className="panel">
        {invoices === null && !error ? (
          <Loading what="invoices" />
        ) : shown.length === 0 ? (
          <Empty>
            {invoices?.length === 0
              ? "No invoices yet. Create one to get started."
              : "No invoices match this filter."}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Project</th>
                  <th className="num">Amount</th>
                  <th className="num">Paid</th>
                  <th className="num">Outstanding</th>
                  <th>Due</th>
                  <th>Status</th>
                  <th className="num">Actions</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((invoice) => (
                  <tr key={invoice.invoice_id}>
                    <td className="mono">{invoice.invoice_number}</td>
                    <td>{invoice.client_name}</td>
                    <td className="muted">{invoice.project}</td>
                    <td className="num">{invoice.amount_display}</td>
                    <td className="num muted">{invoice.amount_paid_display}</td>
                    <td className="num">{invoice.outstanding_display}</td>
                    <td className="muted">{formatDate(invoice.due_date)}</td>
                    <td>
                      <StatusBadge invoice={invoice} />
                      <OverdueBadge invoice={invoice} />
                    </td>
                    <td className="num">
                      <div className="actions" style={{ justifyContent: "flex-end" }}>
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
