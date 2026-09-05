"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  api,
  totalsText,
  type Client,
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

type Detail = {
  balance: ClientBalance;
  invoices: Invoice[];
  payments: Payment[];
};

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api
      .clients()
      .then((r) => {
        setClients(r.clients);
        if (r.clients.length > 0) setSelected(r.clients[0].client_id);
      })
      .catch((err) => setError(err as ApiError));
  }, []);

  useEffect(() => {
    if (selected === null) return;
    setDetail(null);
    api
      .client(selected)
      .then(setDetail)
      .catch((err) => setError(err as ApiError));
  }, [selected]);

  return (
    <>
      <h1 className="page-title">Clients</h1>
      <p className="page-sub">
        Balances are the sum of what each client has been invoiced, less what
        the ledger says they have paid.
      </p>

      {error ? <LoadError error={error} /> : null}

      <div className="agent-layout with-side">
        <div className="panel">
          <div className="panel-head">
            <h2>Client</h2>
            <span className="hint">
              {detail ? `${detail.balance.invoice_count} invoices` : ""}
            </span>
          </div>

          {selected === null ? (
            <Empty>No clients yet. Ask the agent to add one.</Empty>
          ) : detail === null && !error ? (
            <Loading what="this client" />
          ) : detail ? (
            <div className="panel-body">
              <div className="stat-row" style={{ marginBottom: 18 }}>
                <div className="stat">
                  <div className="label">Invoiced</div>
                  <div className="value">
                    {totalsText(detail.balance.invoiced_total, "₹0.00")}
                  </div>
                </div>
                <div className="stat">
                  <div className="label">Paid</div>
                  <div className="value">
                    {totalsText(detail.balance.paid_total, "₹0.00")}
                  </div>
                </div>
                <div className="stat">
                  <div className="label">Outstanding</div>
                  <div className="value">
                    {totalsText(detail.balance.outstanding_total, "₹0.00")}
                  </div>
                </div>
                <div className="stat">
                  <div className="label">Overdue</div>
                  <div className="value overdue">
                    {totalsText(detail.balance.overdue_total, "₹0.00")}
                  </div>
                </div>
              </div>

              <h3 style={{ fontSize: 12, margin: "0 0 8px" }}>
                Invoice history
              </h3>
              {detail.invoices.length === 0 ? (
                <div className="faint">No invoices for this client.</div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Invoice</th>
                        <th>Project</th>
                        <th className="num">Amount</th>
                        <th className="num">Outstanding</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.invoices.map((invoice) => (
                        <tr key={invoice.invoice_id}>
                          <td className="mono">{invoice.invoice_number}</td>
                          <td className="muted">{invoice.project}</td>
                          <td className="num">{invoice.amount_display}</td>
                          <td className="num">
                            {invoice.outstanding_display}
                          </td>
                          <td>
                            <StatusBadge invoice={invoice} />
                            <OverdueBadge invoice={invoice} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <h3 style={{ fontSize: 12, margin: "20px 0 8px" }}>Payments</h3>
              {detail.payments.length === 0 ? (
                <div className="faint">Nothing received yet.</div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Invoice</th>
                        <th className="num">Amount</th>
                        <th>Receipt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.payments.map((payment) => (
                        <tr key={payment.payment_id}>
                          <td className="muted">
                            {formatDate(payment.payment_date)}
                          </td>
                          <td className="mono">{payment.invoice_number}</td>
                          <td className="num">{payment.amount_display}</td>
                          <td>
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
          ) : null}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>All clients</h2>
            <span className="hint">{clients?.length ?? 0}</span>
          </div>
          {clients === null && !error ? (
            <Loading what="clients" />
          ) : clients && clients.length === 0 ? (
            <Empty>No clients yet.</Empty>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                  </tr>
                </thead>
                <tbody>
                  {clients?.map((client) => (
                    <tr
                      key={client.client_id}
                      onClick={() => setSelected(client.client_id)}
                      style={{
                        cursor: "pointer",
                        background:
                          client.client_id === selected ? "#f2f2ee" : undefined,
                      }}
                    >
                      <td>{client.name}</td>
                      <td className="muted">{client.email ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
