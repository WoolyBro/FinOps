"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ApiError,
  api,
  totalsText,
  type ClientBalance,
  type Invoice,
  type Payment,
} from "@/lib/api";
import {
  Empty,
  LoadError,
  Loading,
  OverdueBadge,
  StatusBadge,
  formatDate,
} from "@/components/common";
import { NewInvoiceForm } from "@/components/forms";

type Detail = {
  balance: ClientBalance;
  invoices: Invoice[];
  payments: Payment[];
};

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [invoicing, setInvoicing] = useState(false);
  const [tab, setTab] = useState<"invoices" | "payments">("invoices");
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .client(clientId)
      .then((body) => {
        setDetail(body);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, [clientId]);

  useEffect(load, [load]);

  if (error) {
    return (
      <>
        <Link className="back-link" href="/clients">
          ← Clients
        </Link>
        <LoadError error={error} />
      </>
    );
  }

  if (!detail) return <Loading what="this client" />;

  const { balance, invoices, payments } = detail;
  const counts = balance.invoice_counts_by_status;

  return (
    <>
      <Link className="back-link" href="/clients">
        ← Clients
      </Link>

      <div className="page-head">
        <div>
          <h1 className="page-title">{balance.client_name}</h1>
          <p className="page-sub">
            {balance.invoice_count} invoices · {counts.PAID ?? 0} paid ·{" "}
            {counts.PARTIALLY_PAID ?? 0} partially paid · {counts.UNPAID ?? 0}{" "}
            unpaid
          </p>
        </div>
        <div className="actions">
          <button className="btn primary" onClick={() => setInvoicing(true)}>
            + New invoice
          </button>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat">
          <div className="label">Invoiced</div>
          <div className="value">
            {totalsText(balance.invoiced_total, "₹0.00")}
          </div>
        </div>
        <div className="stat">
          <div className="label">Paid</div>
          <div className="value">{totalsText(balance.paid_total, "₹0.00")}</div>
        </div>
        <div className="stat">
          <div className="label">Outstanding</div>
          <div className="value">
            {totalsText(balance.outstanding_total, "₹0.00")}
          </div>
        </div>
        <div className="stat">
          <div className="label">Overdue</div>
          <div className="value overdue">
            {totalsText(balance.overdue_total, "₹0.00")}
          </div>
        </div>
      </div>

      <div className="segmented" role="group" aria-label="Client history">
        <button
          aria-pressed={tab === "invoices"}
          onClick={() => setTab("invoices")}
        >
          Invoices ({invoices.length})
        </button>
        <button
          aria-pressed={tab === "payments"}
          onClick={() => setTab("payments")}
        >
          Payments ({payments.length})
        </button>
      </div>

      <div className="panel">
        {tab === "invoices" ? (
          invoices.length === 0 ? (
            <Empty>
              <strong>No invoices for this client</strong>
              Raise one and it will appear here.
            </Empty>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th className="num">Amount</th>
                    <th>Invoice</th>
                    <th>Project</th>
                    <th className="num">Outstanding</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.invoice_id}>
                      <td className="num strong">{invoice.amount_display}</td>
                      <td className="mono">
                        <Link
                          className="link"
                          href={`/invoices/${invoice.invoice_id}`}
                        >
                          {invoice.invoice_number}
                        </Link>
                      </td>
                      <td className="muted">{invoice.project}</td>
                      <td className="num">{invoice.outstanding_display}</td>
                      <td>
                        <StatusBadge invoice={invoice} />
                        <OverdueBadge invoice={invoice} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : payments.length === 0 ? (
          <Empty>
            <strong>Nothing received yet</strong>
            Payments recorded against this client&apos;s invoices show here.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="num">Amount</th>
                  <th>Date</th>
                  <th>Invoice</th>
                  <th>Method</th>
                  <th className="num">Receipt</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment) => (
                  <tr key={payment.payment_id}>
                    <td className="num strong">{payment.amount_display}</td>
                    <td className="muted">{formatDate(payment.payment_date)}</td>
                    <td className="mono">
                      <Link
                        className="link"
                        href={`/invoices/${payment.invoice_id}`}
                      >
                        {payment.invoice_number}
                      </Link>
                    </td>
                    <td className="muted">{payment.method ?? "—"}</td>
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

      {invoicing ? (
        <NewInvoiceForm
          clients={[
            {
              client_id: balance.client_id,
              name: balance.client_name,
              email: null,
              phone: null,
              address: null,
              created_at: "",
            },
          ]}
          presetClientId={balance.client_id}
          onClose={() => setInvoicing(false)}
          onDone={() => {
            load();
            setToast("Invoice created");
            setTimeout(() => setToast(null), 3000);
          }}
        />
      ) : null}

      {toast ? <div className="toast">{toast}</div> : null}
    </>
  );
}
