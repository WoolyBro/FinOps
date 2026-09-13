import React, { useState, useEffect, useRef } from 'react';
import { api, totalMinor, totalText } from '../lib/api';
import { ApiError, Invoice, Overview } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { StatTile } from '../components/ui/StatTile';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { ErrorState } from '../components/ui/ErrorState';
import { formatDateTable, formatRelative } from '../lib/format';

type OverviewPageProps = {
  onNavigate: (path: string) => void;
  onOpenRecordPayment: (invoice: Invoice) => void;
  onPrefillAgent: (text: string) => void;
};

/** "Across 1 open invoice" / "Across 8 open invoices" */
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate, onOpenRecordPayment, onPrefillAgent }) => {
  const [view, setView] = useState<Overview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [agentInput, setAgentInput] = useState('');
  const hasAnimated = useRef(false);

  const load = async () => {
    try {
      setError(null);
      setView(await api.getOverview());
    } catch (err) {
      setError(err as ApiError);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (view) {
      const timer = window.setTimeout(() => (hasAnimated.current = true), 400);
      return () => window.clearTimeout(timer);
    }
  }, [view]);

  const handleAgentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (agentInput.trim()) onPrefillAgent(agentInput.trim());
  };

  const loading = !view && !error;
  const month = view?.month;
  const rate = month?.collection_rate_percent ?? null;
  const overdueMinor = totalMinor(view?.overdue_total);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Overview"
        subtitle={view ? `As of ${formatDateTable(view.as_of)}.` : undefined}
        actions={
          <Button variant="default" onClick={() => onNavigate('/invoices')}>
            View invoices
          </Button>
        }
      />

      <form onSubmit={handleAgentSubmit} className="relative">
        <input
          type="text"
          aria-label="Tell the agent what happened"
          className="w-full px-3.5 py-2 border rounded-[6px] text-[13px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
          style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--line-strong)', color: 'var(--ink-strong)' }}
          placeholder="Tell FreelanceFlow what happened…"
          value={agentInput}
          onChange={(e) => setAgentInput(e.target.value)}
        />
        <div className="absolute right-1.5 top-1/2 -translate-y-1/2">
          <Button type="submit" variant="default" disabled={!agentInput.trim()} style={{ padding: '3px 8px', fontSize: '11.5px' }}>
            Ask agent
          </Button>
        </div>
      </form>

      {error && <ErrorState error="Could not load the overview" detail={error.detail} onRetry={load} />}

      <div className="grid grid-cols-1 md:grid-cols-7 gap-3.5">
        <div className="md:col-span-3">
          <StatTile
            size="loud"
            label="Total outstanding"
            value={view ? totalText(view.outstanding_total) : '—'}
            subValue={
              overdueMinor > 0 ? (
                <span className="text-[12.5px] font-[550] ml-1">· {totalText(view?.overdue_total)} overdue</span>
              ) : undefined
            }
            note={view ? `Across ${plural(view.open_invoice_count, 'open invoice')}` : undefined}
          />
        </div>
        <div className="md:col-span-2">
          <StatTile
            label="Received this month"
            value={month ? totalText(month.received_total) : '—'}
            note={month ? `${month.name} · ${plural(month.payments_received, 'payment')}` : undefined}
          />
        </div>
        <div className="md:col-span-2">
          <StatTile
            label="Clients"
            value={view ? String(view.client_count) : '—'}
            note={view ? `${view.clients_with_balance} with a balance owed` : undefined}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Panel
          elevation="sm"
          density="dense"
          title="Needs attention"
          subtitle={
            view
              ? view.overdue_invoice_count > 0
                ? `${plural(view.overdue_invoice_count, 'invoice')} overdue, oldest ${view.oldest_overdue?.days_overdue} days`
                : 'Nothing is overdue'
              : undefined
          }
          actions={
            <Button variant="default" style={{ fontSize: '11.5px', padding: '3px 8px' }} onClick={() => onNavigate('/overdue')}>
              View all
            </Button>
          }
          noPadding
        >
          {loading ? (
            <LoadingSkeleton message="Loading overdue invoices…" rows={4} />
          ) : !view || view.needs_attention.length === 0 ? (
            <div className="p-8 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
              Every invoice with a due date is paid or still within terms.
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--line)' }}>
              {view.needs_attention.map((inv, idx) => {
                const animate = !hasAnimated.current;
                return (
                  <div
                    key={inv.invoice_id}
                    className={`table-row ${animate ? 'table-row-enter' : ''} flex items-center justify-between px-4 py-2.5 text-[13px]`}
                    style={animate ? { animationDelay: `${Math.min(idx, 8) * 24}ms` } : undefined}
                  >
                    <div className="flex items-center gap-3 min-w-0 pr-2">
                      <div className="shrink-0">
                        <Badge status="OVERDUE" daysOverdue={inv.days_overdue} />
                      </div>
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => onNavigate(`/invoices/${inv.invoice_id}`)}
                          className="font-mono font-[500] hover:underline text-left block"
                          style={{ color: 'var(--ink)' }}
                        >
                          {inv.invoice_number}
                        </button>
                        <div className="text-[12px] truncate" style={{ color: 'var(--ink-faint)' }}>
                          {inv.client_name} · {inv.project}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 text-right">
                      <div className="font-[500] font-mono tabular-nums text-[13px]" style={{ color: 'var(--bad-ink)' }}>
                        {inv.outstanding_display}
                      </div>
                      <Button variant="default" style={{ fontSize: '11.5px', padding: '3px 8px' }} onClick={() => onOpenRecordPayment(inv)}>
                        Record payment
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel
          elevation="none"
          density="dense"
          title="Recent activity"
          subtitle="Invoices issued and payments received, newest first"
          actions={
            <Button variant="default" style={{ fontSize: '11.5px', padding: '3px 8px' }} onClick={() => onNavigate('/payments')}>
              View ledger
            </Button>
          }
          noPadding
        >
          {loading ? (
            <LoadingSkeleton message="Loading ledger activity…" rows={6} />
          ) : !view || view.recent_activity.length === 0 ? (
            <div className="p-8 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
              Nothing yet. Invoices and payments appear here as they happen.
            </div>
          ) : (
            <div className="divide-y text-[13px]" style={{ borderColor: 'var(--line)' }}>
              {view.recent_activity.map((event, idx) => {
                const animate = !hasAnimated.current;
                return (
                  <button
                    type="button"
                    key={`${event.kind}-${event.payment_id ?? event.invoice_id}`}
                    onClick={() => onNavigate(`/invoices/${event.invoice_id}`)}
                    className={`table-row ${animate ? 'table-row-enter' : ''} w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-[var(--surface-sunken)]`}
                    style={animate ? { animationDelay: `${Math.min(idx, 8) * 24}ms` } : undefined}
                  >
                    <span className="pr-3 leading-snug truncate" style={{ color: 'var(--ink-body)' }}>
                      {event.kind === 'payment' ? (
                        <>
                          Payment of <span className="font-[600] tabular-nums">{event.amount_display}</span> from{' '}
                          <span className="font-[600]">{event.client_name}</span> against{' '}
                          <span className="font-mono font-[600]">{event.invoice_number}</span>
                        </>
                      ) : (
                        <>
                          Invoice <span className="font-mono font-[600]">{event.invoice_number}</span> issued to{' '}
                          <span className="font-[600]">{event.client_name}</span> for{' '}
                          <span className="font-[600] tabular-nums">{event.amount_display}</span>
                        </>
                      )}
                    </span>
                    <span className="text-[11.5px] shrink-0 font-mono" style={{ color: 'var(--ink-faint)' }}>
                      {formatRelative(event.date, view.as_of)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </Panel>
      </div>

      {month && (
        <div className="rounded-[8px] border p-4 sm:p-5" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--line)' }}>
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 lg:gap-8">
            <div className="flex-1 min-w-0">
              <div className="text-[13.5px] font-[500] leading-snug" style={{ color: 'var(--ink)' }}>
                {rate === null
                  ? `Nothing invoiced yet in ${month.name}${
                      totalMinor(month.received_total) > 0 ? ` — ${totalText(month.received_total)} collected on earlier invoices` : ''
                    }.`
                  : `${totalText(month.received_total)} collected against ${totalText(month.invoiced_total)} invoiced in ${month.name} — ${rate}%.`}
              </div>
              {rate !== null && (
                <div className="w-full h-1 mt-3 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--line)' }}>
                  <div
                    className="h-full rounded-full progress-grow"
                    style={{ width: `${Math.min(rate, 100)}%`, transformOrigin: 'left', backgroundColor: 'var(--accent)' }}
                  />
                </div>
              )}
            </div>

            <div className="flex items-center gap-6 shrink-0 pt-3 lg:pt-0 border-t lg:border-t-0 border-[var(--line)]">
              <div>
                <div className="text-[12px]" style={{ color: 'var(--ink-muted)' }}>
                  Oldest unpaid
                </div>
                <div
                  className="text-[15px] font-[550] font-mono tabular-nums mt-0.5"
                  style={{ color: view?.oldest_overdue ? 'var(--bad-ink)' : 'var(--ink)' }}
                  title={view?.oldest_overdue ? `${view.oldest_overdue.invoice_number} · ${view.oldest_overdue.client_name}` : undefined}
                >
                  {view?.oldest_overdue ? `${view.oldest_overdue.days_overdue} days late` : 'None late'}
                </div>
              </div>
              <div className="h-7 w-px" style={{ backgroundColor: 'var(--line)' }} />
              <div>
                <div className="text-[12px]" style={{ color: 'var(--ink-muted)' }}>
                  Average time to payment
                </div>
                <div
                  className="text-[15px] font-[550] font-mono tabular-nums mt-0.5"
                  style={{ color: 'var(--ink)' }}
                  title={view?.settled_invoice_count ? `Across ${plural(view.settled_invoice_count, 'settled invoice')}` : undefined}
                >
                  {view?.average_days_to_payment != null ? `${view.average_days_to_payment} days` : '—'}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
