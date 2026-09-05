"use client";

import { useEffect, useState } from "react";
import { ApiError, api, type Invoice } from "@/lib/api";
import {
  Empty,
  LoadError,
  Loading,
  OverdueBadge,
  StatusBadge,
  formatDate,
} from "@/components/common";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api
      .invoices()
      .then((r) => setInvoices(r.invoices))
      .catch((err) => setError(err as ApiError));
  }, []);

  return (
    <>
      <h1 className="page-title">Invoices</h1>
      <p className="page-sub">
        Paid and outstanding amounts are computed from the payment ledger, not
        stored on the invoice.
      </p>

      {error ? <LoadError error={error} /> : null}

      <div className="panel">
        {invoices === null && !error ? (
          <Loading what="invoices" />
        ) : invoices && invoices.length === 0 ? (
          <Empty>No invoices yet.</Empty>
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
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {invoices?.map((invoice) => (
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
                      <a
                        className="btn"
                        href={api.invoicePdfUrl(invoice.invoice_id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
