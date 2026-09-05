"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  api,
  totalsText,
  type Invoice,
  type Summary,
} from "@/lib/api";
import { AgentPanel } from "@/components/AgentPanel";
import {
  Empty,
  LoadError,
  Loading,
  OverdueBadge,
  StatusBadge,
  formatDate,
} from "@/components/common";

export default function OverviewPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(() => {
    Promise.all([api.summary(), api.invoices()])
      .then(([s, i]) => {
        setSummary(s);
        setInvoices(i.invoices);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, []);

  useEffect(load, [load]);

  const counts = summary?.invoice_counts_in_period;

  return (
    <>
      <h1 className="page-title">Overview</h1>
      <p className="page-sub">
        {summary
          ? `Received ${formatDate(summary.period_start)} – ${formatDate(
              summary.period_end,
            )}. Outstanding and overdue are current totals across every open invoice.`
          : "Your billing position, derived from the invoice and payment ledger."}
      </p>

      {error ? <LoadError error={error} /> : null}

      <div className="stat-row">
        <div className="stat">
          <div className="label">Received this period</div>
          <div className="value">
            {summary ? totalsText(summary.received_total, "₹0.00") : "—"}
          </div>
        </div>
        <div className="stat">
          <div className="label">Outstanding</div>
          <div className="value">
            {summary ? totalsText(summary.outstanding_total, "₹0.00") : "—"}
          </div>
          <div className="note">across all open invoices</div>
        </div>
        <div className="stat">
          <div className="label">Overdue</div>
          <div className="value overdue">
            {summary ? totalsText(summary.overdue_total, "₹0.00") : "—"}
          </div>
          <div className="note">past due date, still owed</div>
        </div>
        <div className="stat">
          <div className="label">Invoices this period</div>
          <div className="value">
            {summary ? summary.invoices_issued_in_period : "—"}
          </div>
          <div className="note">
            {counts
              ? `${counts.PAID ?? 0} paid · ${
                  counts.PARTIALLY_PAID ?? 0
                } partial · ${counts.UNPAID ?? 0} unpaid`
              : " "}
          </div>
        </div>
      </div>

      <div className="agent-layout with-side">
        <AgentPanel onStateChange={load} />

        <div className="panel">
          <div className="panel-head">
            <h2>Recent invoices</h2>
            <Link className="hint" href="/invoices">
              View all →
            </Link>
          </div>
          {invoices === null && !error ? (
            <Loading what="invoices" />
          ) : invoices && invoices.length === 0 ? (
            <Empty>
              No invoices yet. Ask the agent to create one.
            </Empty>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Client</th>
                    <th className="num">Outstanding</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices?.slice(0, 8).map((invoice) => (
                    <tr key={invoice.invoice_id}>
                      <td className="mono">{invoice.invoice_number}</td>
                      <td>{invoice.client_name}</td>
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
          )}
        </div>
      </div>
    </>
  );
}
