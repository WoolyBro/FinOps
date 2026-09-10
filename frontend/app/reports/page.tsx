"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  api,
  totalsText,
  type CurrencyTotal,
  type Invoice,
  type Summary,
} from "@/lib/api";
import { Empty, LoadError, Loading, formatDate } from "@/components/common";

function monthBounds(offset = 0) {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const end = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  return { start: iso(start), end: iso(end) };
}

function yearToDate() {
  const now = new Date();
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  return { start: `${now.getFullYear()}-01-01`, end: iso(now) };
}

/**
 * The period and the snapshot mean different things, and the page says so.
 *
 * Received and invoices-issued are flows, scoped to the dates. Outstanding and
 * overdue are current totals across every open invoice, because a balance owed
 * does not belong to a calendar month.
 */
export default function ReportsPage() {
  const [range, setRange] = useState(monthBounds());
  const [preset, setPreset] = useState<string>("this-month");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [outstanding, setOutstanding] = useState<Invoice[]>([]);
  const [outstandingTotal, setOutstandingTotal] = useState<CurrencyTotal[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(() => {
    setSummary(null);
    Promise.all([api.summaryFor(range.start, range.end), api.outstanding()])
      .then(([s, o]) => {
        setSummary(s);
        setOutstanding(o.invoices);
        setOutstandingTotal(o.outstanding_total);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, [range.start, range.end]);

  useEffect(load, [load]);

  function applyPreset(name: string) {
    setPreset(name);
    if (name === "this-month") setRange(monthBounds());
    else if (name === "last-month") setRange(monthBounds(-1));
    else if (name === "ytd") setRange(yearToDate());
  }

  const counts = summary?.invoice_counts_in_period;

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Reports</h1>
          <p className="page-sub">
            Every figure is worked out from the invoice and payment ledger when
            you load the page. Nothing is stored, so nothing can go stale.
          </p>
        </div>
      </div>

      {error ? <LoadError error={error} /> : null}

      <div className="filter-bar">
        <div className="segmented" role="group" aria-label="Reporting period">
          {[
            ["this-month", "This month"],
            ["last-month", "Last month"],
            ["ytd", "Year to date"],
            ["custom", "Custom"],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={preset === value}
              onClick={() => applyPreset(value)}
            >
              {label}
            </button>
          ))}
        </div>

        {preset === "custom" ? (
          <div className="range-inputs">
            <label>
              <span>From</span>
              <input
                type="date"
                value={range.start}
                onChange={(e) => setRange({ ...range, start: e.target.value })}
              />
            </label>
            <label>
              <span>To</span>
              <input
                type="date"
                value={range.end}
                onChange={(e) => setRange({ ...range, end: e.target.value })}
              />
            </label>
          </div>
        ) : (
          <span className="range-caption">
            {formatDate(range.start)} – {formatDate(range.end)}
          </span>
        )}
      </div>

      <div className="section-label">In this period</div>
      <div className="stat-row">
        <div className="stat">
          <div className="label">Received</div>
          <div className="value">
            {summary ? totalsText(summary.received_total, "₹0.00") : "—"}
          </div>
          <div className="note">payments dated in the period</div>
        </div>
        <div className="stat">
          <div className="label">Invoices issued</div>
          <div className="value">
            {summary ? summary.invoices_issued_in_period : "—"}
          </div>
          <div className="note">
            {counts
              ? `${counts.PAID ?? 0} paid · ${counts.PARTIALLY_PAID ?? 0} partial · ${counts.UNPAID ?? 0} unpaid`
              : " "}
          </div>
        </div>
      </div>

      <div className="section-label">
        Right now
        <span className="section-note">
          across every open invoice, whenever it was issued
        </span>
      </div>
      <div className="stat-row">
        <div className="stat">
          <div className="label">Outstanding</div>
          <div className="value">
            {summary ? totalsText(summary.outstanding_total, "₹0.00") : "—"}
          </div>
          <div className="note">{outstanding.length} open invoices</div>
        </div>
        <div className="stat">
          <div className="label">Overdue</div>
          <div className="value overdue">
            {summary ? totalsText(summary.overdue_total, "₹0.00") : "—"}
          </div>
          <div className="note">
            <Link className="link" href="/overdue">
              Chase these →
            </Link>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Outstanding invoices</h2>
          <span className="hint">
            {totalsText(outstandingTotal, "₹0.00")} owed in total
          </span>
        </div>
        {summary === null && !error ? (
          <Loading what="the ledger" />
        ) : outstanding.length === 0 ? (
          <Empty>
            <strong>Nothing outstanding</strong>
            Every invoice has been settled.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="num">Outstanding</th>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Due</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {outstanding.map((invoice) => (
                  <tr key={invoice.invoice_id}>
                    <td className="num strong">{invoice.outstanding_display}</td>
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
                    <td className="muted">{formatDate(invoice.due_date)}</td>
                    <td>
                      {invoice.is_overdue ? (
                        <span className="badge overdue" style={{ marginLeft: 0 }}>
                          {invoice.days_overdue} days late
                        </span>
                      ) : (
                        <span className="badge UNPAID">Within terms</span>
                      )}
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
