import React, { useState, useEffect, useRef } from 'react';
import { api, totalText } from '../lib/api';
import { ApiError, CurrencyTotal, Invoice } from '../types';
import { ErrorState } from '../components/ui/ErrorState';
import { PageHeader } from '../components/layout/PageHeader';
import { StatTile } from '../components/ui/StatTile';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { useToast } from '../components/ui/Toast';
import { formatDateTable } from '../lib/format';

type OverduePageProps = {
  onNavigate: (path: string) => void;
  onOpenRecordPayment: (invoice: Invoice) => void;
};

export const OverduePage: React.FC<OverduePageProps> = ({
  onNavigate,
  onOpenRecordPayment,
}) => {
  const { addToast } = useToast();
  const [overdueInvoices, setOverdueInvoices] = useState<Invoice[]>([]);
  const [overdueTotal, setOverdueTotal] = useState<CurrencyTotal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [draftingId, setDraftingId] = useState<number | null>(null);
  const hasAnimated = useRef(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getReportsOverdue();
      setOverdueInvoices(res.invoices);
      setOverdueTotal(res.overdue_total);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (overdueInvoices.length > 0) {
      const timer = window.setTimeout(() => (hasAnimated.current = true), 400);
      return () => window.clearTimeout(timer);
    }
  }, [overdueInvoices]);

  const handleDraftReminder = async (inv: Invoice) => {
    setDraftingId(inv.invoice_id);
    try {
      const { created } = await api.postReminder({ invoice_id: inv.invoice_id });
      addToast(
        created
          ? `Drafted a reminder for ${inv.invoice_number} — review it before it goes anywhere`
          : `${inv.invoice_number} already has a reminder waiting — opening it`,
      );
      onNavigate('/reminders');
    } catch (err) {
      addToast((err as ApiError).detail);
    } finally {
      setDraftingId(null);
    }
  };

  const longestOverdueInvoice = overdueInvoices[0] || null;

  return (
    <div className="space-y-3.5">
      <PageHeader
        title="Overdue"
        subtitle="Past their due date with money still owed, most overdue first. Nothing here is stored — it is worked out from due dates and the payment ledger each time you look."
      />

      {error && <ErrorState error="Could not load overdue invoices" detail={error.detail} onRetry={loadData} />}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatTile
          label="Total overdue"
          value={totalText(overdueTotal)}
          note={overdueInvoices.length ? 'owed past the due date' : 'nothing late'}
          isDanger={overdueInvoices.length > 0}
        />
        <StatTile
          label="Invoices late"
          value={String(overdueInvoices.length)}
          isDanger={overdueInvoices.length > 0}
        />
        <StatTile
          label="Longest overdue"
          value={longestOverdueInvoice ? `${longestOverdueInvoice.days_overdue} days` : '—'}
          note={longestOverdueInvoice ? `${longestOverdueInvoice.client_name} · ${longestOverdueInvoice.invoice_number}` : undefined}
          isDanger={overdueInvoices.length > 0}
        />
      </div>

      <Panel elevation="sm" density="dense" noPadding>
        {loading ? (
          <LoadingSkeleton message="Calculating overdue balances…" rows={5} />
        ) : overdueInvoices.length === 0 ? (
          <EmptyState
            title="Nothing is overdue"
            description="Every invoice with a due date has either been paid or is still within terms."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[760px] text-[13px]" style={{ tableLayout: 'fixed' }}>
              <colgroup>
                <col style={{ width: '110px' }} />
                <col style={{ width: '104px' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: '140px' }} />
                <col style={{ width: '130px' }} />
                <col style={{ width: '220px' }} />
              </colgroup>
              <thead
                style={{
                  backgroundColor: 'var(--surface-sunken)',
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <tr className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-muted)' }}>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Late by</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Invoice</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Client & Project</th>
                  <th scope="col" className="py-2.5 px-3.5 text-right">Outstanding</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left whitespace-nowrap">Due</th>
                  <th scope="col" className="py-2.5 px-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                {overdueInvoices.map((inv, idx) => {
                  const shouldAnimate = !hasAnimated.current;
                  return (
                    <tr
                      key={inv.invoice_id}
                      className={`table-row ${shouldAnimate ? 'table-row-enter' : ''}`}
                      style={{
                        height: '52px',
                        ...(shouldAnimate ? { animationDelay: `${Math.min(idx, 10) * 24}ms` } : {}),
                      }}
                    >
                      {/* Late by (110px fixed, red days badge, left aligned) */}
                      <td className="px-3.5 text-left align-middle">
                        <Badge status="OVERDUE" daysOverdue={inv.days_overdue} />
                      </td>

                      {/* Invoice: 104px fixed */}
                      <td className="px-3.5 font-mono font-[500] text-left align-middle">
                        <button
                          type="button"
                          onClick={() => onNavigate(`/invoices/${inv.invoice_id}`)}
                          className="hover:underline text-left cursor-pointer"
                          style={{ color: 'var(--ink)' }}
                        >
                          {inv.invoice_number}
                        </button>
                      </td>

                      {/* Client & Project: auto, takes remainder */}
                      <td className="px-3.5 text-left align-middle min-w-0">
                        <div className="font-[500] truncate" style={{ color: 'var(--ink)' }}>
                          <button
                            type="button"
                            className="hover:underline text-left"
                            onClick={() => onNavigate(`/clients/${inv.client_id}`)}
                          >
                            {inv.client_name}
                          </button>
                        </div>
                        <div className="text-[12px] leading-snug truncate" style={{ color: 'var(--ink-faint)' }} title={inv.project}>
                          {inv.project}
                        </div>
                      </td>

                      {/* Outstanding: 140px fixed, right-aligned */}
                      <td className="px-3.5 text-right font-[500] font-mono tabular-nums align-middle" style={{ color: 'var(--bad-ink)' }}>
                        {inv.outstanding_display}
                      </td>

                      {/* Due: 130px fixed, whitespace-nowrap */}
                      <td className="px-3.5 text-[12.5px] text-left align-middle whitespace-nowrap" style={{ color: 'var(--ink-muted)' }}>
                        {formatDateTable(inv.due_date)}
                      </td>

                      {/* Actions: 220px fixed: Draft reminder and Record payment */}
                      <td className="px-3.5 text-right align-middle">
                        <div className="row-actions flex items-center justify-end gap-1.5">
                          <Button
                            variant="default"
                            style={{ fontSize: '11.5px', padding: '3px 7px', whiteSpace: 'nowrap' }}
                            busy={draftingId === inv.invoice_id}
                            busyText="Drafting…"
                            onClick={() => handleDraftReminder(inv)}
                          >
                            Draft reminder
                          </Button>
                          <Button
                            variant="primary"
                            style={{ fontSize: '11.5px', padding: '3px 8px', whiteSpace: 'nowrap' }}
                            onClick={() => onOpenRecordPayment(inv)}
                          >
                            Record payment
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};
