"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, api, type Payment } from "@/lib/api";
import { Empty, LoadError, Loading, formatDate } from "@/components/common";

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api
      .payments()
      .then((r) => setPayments(r.payments))
      .catch((err) => setError(err as ApiError));
  }, []);

  return (
    <>
      <h1 className="page-title">Payments</h1>
      <p className="page-sub">
        Every payment received. A payment keeps one receipt number for life.
      </p>

      {error ? <LoadError error={error} /> : null}

      <div className="panel">
        {payments === null && !error ? (
          <Loading what="payments" />
        ) : payments && payments.length === 0 ? (
          <Empty>
            <strong>No payments yet</strong>
            Record one against an invoice and the balance updates here.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Client</th>
                  <th>Invoice</th>
                  <th className="num">Amount</th>
                  <th className="num">Balance after</th>
                  <th>Method</th>
                  <th>Receipt</th>
                </tr>
              </thead>
              <tbody>
                {payments?.map((payment) => (
                  <tr key={payment.payment_id}>
                    <td className="muted">{formatDate(payment.payment_date)}</td>
                    <td className="strong">{payment.client_name}</td>
                    <td className="mono">
                      <Link className="link" href={`/invoices/${payment.invoice_id}`}>
                        {payment.invoice_number}
                      </Link>
                    </td>
                    <td className="num strong">{payment.amount_display}</td>
                    <td className="num muted">
                      {payment.outstanding_after_display}
                    </td>
                    <td className="muted">{payment.method ?? "—"}</td>
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
    </>
  );
}
