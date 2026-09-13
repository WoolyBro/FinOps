import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Invoice, Payment } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { StatTile } from '../components/ui/StatTile';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDateProse, formatDateTable } from '../lib/format';
import { IconDownload, IconArrowRight } from '../components/Icons';

type InvoiceDetailPageProps = {
  invoiceId: number;
  onNavigate: (path: string) => void;
  onOpenRecordPayment: (invoice: Invoice) => void;
  onViewPdf: (invoice: Invoice) => void;
  onViewReceiptPdf: (payment: Payment) => void;
};

export const InvoiceDetailPage: React.FC<InvoiceDetailPageProps> = ({
  invoiceId,
  onNavigate,
  onOpenRecordPayment,
  onViewPdf,
  onViewReceiptPdf,
}) => {
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDetail = async () => {
    try {
      setLoading(true);
      const res = await api.getInvoiceDetail(invoiceId);
      setInvoice(res.invoice);
      setPayments(res.payments);
    } catch {
      setInvoice(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [invoiceId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton message="Loading invoice details…" rows={6} />
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="space-y-6">
        <EmptyState
          title="Invoice not found"
          description={`Could not find invoice #${invoiceId}.`}
          action={
            <Button variant="default" onClick={() => onNavigate('/invoices')}>
              Back to invoices
            </Button>
          }
        />
      </div>
    );
  }

  // Calculate percentage paid
  const percentPaid = invoice.amount_minor > 0
    ? Math.min(100, Math.round((invoice.amount_paid_minor / invoice.amount_minor) * 100))
    : 0;

  const isCancelled = invoice.invoice_status === 'CANCELLED';

  return (
    <div className="space-y-3.5">
      {/* Back button */}
      <div>
        <button
          type="button"
          onClick={() => onNavigate('/invoices')}
          className="text-[12.5px] font-[500] hover:underline flex items-center gap-1"
          style={{ color: 'var(--ink-muted)' }}
        >
          ← Back to invoices
        </button>
      </div>

      {/* Header */}
      <PageHeader
        title={
          <div className="flex items-center gap-2.5">
            <span className="font-mono">{invoice.invoice_number}</span>
            <Badge status={invoice.invoice_status} />
            {invoice.is_overdue && invoice.invoice_status !== 'PAID' && !isCancelled && (
              <Badge status="OVERDUE" daysOverdue={invoice.days_overdue} />
            )}
          </div>
        }
        subtitle={
          <span>
            Billed to{' '}
            <button
              type="button"
              className="font-[500] underline"
              style={{ color: 'var(--ink)' }}
              onClick={() => onNavigate(`/clients/${invoice.client_id}`)}
            >
              {invoice.client_name}
            </button>{' '}
            for {invoice.project}
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            {invoice.pdf_available && (
              <Button
                variant="default"
                icon={<IconDownload size={14} />}
                onClick={() => onViewPdf(invoice)}
              >
                Download PDF
              </Button>
            )}
            {invoice.invoice_status !== 'PAID' && !isCancelled && (
              <Button
                variant="primary"
                onClick={() => onOpenRecordPayment(invoice)}
              >
                Record payment
              </Button>
            )}
          </div>
        }
      />

      {/* Three-tile row: Invoice amount, Paid, Outstanding */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatTile
          label="Invoice amount"
          value={
            isCancelled ? (
              <span className="line-through" style={{ color: 'var(--ink-muted)' }}>
                {invoice.amount_display}
              </span>
            ) : (
              invoice.amount_display
            )
          }
          note={isCancelled ? 'Cancelled — not collectible' : undefined}
        />
        <StatTile
          label="Paid to date"
          value={invoice.amount_paid_display}
        />
        <StatTile
          label="Outstanding"
          value={isCancelled ? '₹0.00' : invoice.outstanding_display}
          isDanger={!isCancelled && invoice.outstanding_minor > 0 && invoice.is_overdue}
        />
      </div>

      {/* Payment progress bar (only for active invoices) */}
      {!isCancelled && (
        <div
          className="p-3.5 rounded-[8px] border"
          style={{
            backgroundColor: 'var(--surface)',
            borderColor: 'var(--line)',
            boxShadow: 'none',
          }}
        >
          <div className="flex justify-between items-center text-[12px] font-[500] mb-2">
            <span style={{ color: 'var(--ink-body)' }}>Payment progress</span>
            <span className="tabular-nums" style={{ color: 'var(--ink-muted)' }}>
              {invoice.amount_paid_display} of {invoice.amount_display} · {percentPaid}% paid
            </span>
          </div>
          <div
            className="w-full h-[5px] rounded-full overflow-hidden"
            style={{ backgroundColor: 'var(--line)' }}
          >
            <div
              className="h-full rounded-full progress-grow"
              style={{
                width: `${percentPaid}%`,
                transformOrigin: 'left',
                backgroundColor: percentPaid >= 100 ? 'var(--ok-ink)' : 'var(--accent)',
              }}
            />
          </div>
        </div>
      )}

      {/* Details Panel: PRIMARY carries elevation="sm" */}
      <Panel elevation="sm" title="Invoice details" subtitle="Terms, dates and project scope">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3.5 text-[13px]">
          <div>
            <dt className="text-[11.5px] font-[500]" style={{ color: 'var(--ink-muted)' }}>
              Issue date
            </dt>
            <dd className="mt-0.5 font-[500]" style={{ color: 'var(--ink)' }}>
              {formatDateProse(invoice.issue_date)}
            </dd>
          </div>

          <div>
            <dt className="text-[11.5px] font-[500]" style={{ color: 'var(--ink-muted)' }}>
              Due date
            </dt>
            <dd className="mt-0.5 font-[500] flex items-center gap-2" style={{ color: 'var(--ink)' }}>
              <span>{formatDateProse(invoice.due_date)}</span>
              {invoice.is_overdue && invoice.invoice_status !== 'PAID' && !isCancelled && (
                <Badge status="OVERDUE" daysOverdue={invoice.days_overdue} />
              )}
            </dd>
          </div>

          <div>
            <dt className="text-[11.5px] font-[500]" style={{ color: 'var(--ink-muted)' }}>
              Billing currency
            </dt>
            <dd className="mt-0.5 font-mono" style={{ color: 'var(--ink)' }}>
              {invoice.currency} (Indian Rupee)
            </dd>
          </div>

          <div>
            <dt className="text-[11.5px] font-[500]" style={{ color: 'var(--ink-muted)' }}>
              Project reference
            </dt>
            <dd className="mt-0.5 font-[500]" style={{ color: 'var(--ink)' }}>
              {invoice.project}
            </dd>
          </div>

          {invoice.description && (
            <div className="md:col-span-2 pt-2.5 border-t" style={{ borderColor: 'var(--line)' }}>
              <dt className="text-[11.5px] font-[500]" style={{ color: 'var(--ink-muted)' }}>
                Description
              </dt>
              <dd
                className="mt-1 leading-relaxed whitespace-pre-wrap text-[12.5px]"
                style={{ color: 'var(--ink-body)' }}
              >
                {invoice.description}
              </dd>
            </div>
          )}
        </dl>
      </Panel>

      {/* Payments against this invoice panel: FLAT border only */}
      <Panel
        elevation="none"
        density="dense"
        title="Payments against this invoice"
        subtitle="Receipts and incoming transactions"
        noPadding
      >
        {payments.length === 0 ? (
          <div className="py-7 px-4 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
            No payments recorded against this invoice yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse table-fixed min-w-[650px] text-[13px]">
              <thead
                style={{
                  backgroundColor: 'var(--surface-sunken)',
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <tr className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-muted)' }}>
                  <th scope="col" style={{ width: '110px' }} className="py-2.5 px-3.5 text-left">Date</th>
                  <th scope="col" style={{ width: '120px' }} className="py-2.5 px-3.5 text-right">Amount</th>
                  <th scope="col" style={{ width: '100px' }} className="py-2.5 px-3.5 text-left">Method</th>
                  <th scope="col" style={{ width: 'auto' }} className="py-2.5 px-3.5 text-left">Reference</th>
                  <th scope="col" style={{ width: '120px' }} className="py-2.5 px-3.5 text-left">Receipt</th>
                  <th scope="col" style={{ width: '130px' }} className="py-2.5 px-3.5 text-right">Outstanding</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                {payments.map((p) => (
                  <tr key={p.payment_id} className="hover:bg-[var(--surface-sunken)] transition-standard">
                    <td className="py-2 px-3.5 text-[12.5px] text-left" style={{ color: 'var(--ink-muted)' }}>
                      {formatDateTable(p.payment_date)}
                    </td>
                    <td className="py-2 px-3.5 text-right font-[500] font-mono tabular-nums" style={{ color: 'var(--ok-ink)' }}>
                      {p.amount_display}
                    </td>
                    <td className="py-2 px-3.5 text-left">
                      {p.method ? <Badge variant="neutral">{p.method}</Badge> : <span className="text-[12px]" style={{ color: 'var(--ink-faint)' }}>Not recorded</span>}
                    </td>
                    <td className="py-2 px-3.5 font-mono text-[11.5px] text-left" style={{ color: 'var(--ink-faint)' }}>
                      {p.reference || '—'}
                    </td>
                    <td className="py-2 px-3.5 font-mono font-[500] text-left">
                      {p.receipt_number ? (
                        <button
                          type="button"
                          className="hover:underline text-left cursor-pointer"
                          style={{ color: 'var(--ink)' }}
                          onClick={() => onViewReceiptPdf(p)}
                        >
                          {p.receipt_number}
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="font-sans text-[12px] hover:underline text-left cursor-pointer"
                          style={{ color: 'var(--accent-ink)' }}
                          title="Issues a receipt number for this payment"
                          onClick={() => onViewReceiptPdf(p)}
                        >
                          Issue receipt
                        </button>
                      )}
                    </td>
                    <td className="py-2 px-3.5 text-right font-mono tabular-nums text-[12.5px]" style={{ color: 'var(--ink-muted)' }}>
                      {p.outstanding_after_display}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};
