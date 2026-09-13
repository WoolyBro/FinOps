import React, { useState, useEffect, useRef } from 'react';
import { api, totalText } from '../lib/api';
import { ApiError, Client, CurrencyTotal, Payment } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { StatTile } from '../components/ui/StatTile';
import { Panel } from '../components/ui/Panel';
import { Badge } from '../components/ui/Badge';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { formatDateTable } from '../lib/format';

type PaymentsPageProps = {
  onNavigate: (path: string) => void;
  onViewReceiptPdf: (payment: Payment) => void;
  flashPaymentId?: string | number | null;
};

export const PaymentsPage: React.FC<PaymentsPageProps> = ({
  onNavigate,
  onViewReceiptPdf,
  flashPaymentId,
}) => {
  const [filteredPayments, setPayments] = useState<Payment[]>([]);
  const [matchCount, setMatchCount] = useState(0);
  const [received, setReceived] = useState<CurrencyTotal[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const hasAnimated = useRef(false);

  // Filters are applied by the server, so the total below covers every
  // matching payment — not just the rows that happened to be loaded.
  const [selectedClientId, setSelectedClientId] = useState<string>('ALL');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => {
    api.getClients().then((res) => setClients(res.clients)).catch(() => undefined);
  }, []);

  const loadData = async () => {
    if (startDate && endDate && startDate > endDate) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.getPayments({
        client_id: selectedClientId === 'ALL' ? undefined : parseInt(selectedClientId, 10),
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      setPayments(res.payments);
      setMatchCount(res.count);
      setReceived(res.received_total);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClientId, startDate, endDate]);

  useEffect(() => {
    if (filteredPayments.length > 0) {
      const timer = window.setTimeout(() => (hasAnimated.current = true), 400);
      return () => window.clearTimeout(timer);
    }
  }, [filteredPayments]);

  const filtered = selectedClientId !== 'ALL' || !!startDate || !!endDate;

  return (
    <div className="space-y-3.5">
      <PageHeader
        title="Payments"
      />

      {/* Date-range and client filters in header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Client Filter */}
          <div className="flex items-center gap-1.5">
            <label className="text-[11.5px] font-[550]" style={{ color: 'var(--ink-muted)' }}>
              Client:
            </label>
            <select
              className="px-2 py-1 border rounded-[6px] text-[12.5px] transition-standard focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--line)',
                color: 'var(--ink)',
              }}
              value={selectedClientId}
              onChange={(e) => setSelectedClientId(e.target.value)}
            >
              <option value="ALL">All clients</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range Filter */}
          <div className="flex items-center gap-1.5">
            <label className="text-[11.5px] font-[550]" style={{ color: 'var(--ink-muted)' }}>
              From:
            </label>
            <input
              type="date"
              className="px-2 py-1 border rounded-[6px] text-[12px] tabular-nums"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--line)',
                color: 'var(--ink)',
              }}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <label className="text-[11.5px] font-[550]" style={{ color: 'var(--ink-muted)' }}>
              To:
            </label>
            <input
              type="date"
              className="px-2 py-1 border rounded-[6px] text-[12px] tabular-nums"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--line)',
                color: 'var(--ink)',
              }}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
        </div>

        {(selectedClientId !== 'ALL' || startDate || endDate) && (
          <button
            type="button"
            className="text-[12px] font-[500] hover:underline"
            style={{ color: 'var(--accent-ink)' }}
            onClick={() => {
              setSelectedClientId('ALL');
              setStartDate('');
              setEndDate('');
            }}
          >
            Reset filters
          </button>
        )}
      </div>

      {/* Single Total received in range tile above table */}
      <div className="max-w-[280px]">
        <StatTile
          label={filtered ? 'Received in this selection' : 'Received, all time'}
          value={totalText(received)}
          note={`${matchCount} payment${matchCount === 1 ? '' : 's'}${
            matchCount > filteredPayments.length ? ` · showing the latest ${filteredPayments.length}` : ''
          }`}
        />
      </div>

      {error && <ErrorState error="Could not load payments" detail={error.detail} onRetry={loadData} />}

      <Panel elevation="sm" density="dense" noPadding>
        {loading && filteredPayments.length === 0 ? (
          <LoadingSkeleton message="Loading payment ledger…" rows={6} />
        ) : filteredPayments.length === 0 ? (
          <EmptyState
            title={filtered ? 'No payments match these filters' : 'No payments recorded'}
            description={
              filtered
                ? 'Try a wider date range or another client.'
                : 'Payments you record will appear here as a permanent ledger.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[760px] text-[13px]" style={{ tableLayout: 'fixed' }}>
              <colgroup>
                <col style={{ width: '120px' }} />
                <col style={{ width: '140px' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: '104px' }} />
                <col style={{ width: '130px' }} />
                <col style={{ width: '140px' }} />
              </colgroup>
              <thead
                style={{
                  backgroundColor: 'var(--surface-sunken)',
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <tr className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-muted)' }}>
                  <th scope="col" className="py-2.5 px-3.5 text-left whitespace-nowrap">Date</th>
                  <th scope="col" className="py-2.5 px-3.5 text-right">Amount</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Client & Project</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Invoice</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Method</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Receipt</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                {filteredPayments.map((p, idx) => {
                  const shouldAnimate = !hasAnimated.current;
                  return (
                    <tr
                      key={p.payment_id}
                      className={`table-row ${shouldAnimate ? 'table-row-enter' : ''} ${flashPaymentId === p.payment_id ? 'optimistic-flash' : ''}`}
                      style={{
                        height: '52px',
                        ...(shouldAnimate ? { animationDelay: `${Math.min(idx, 10) * 24}ms` } : {}),
                      }}
                    >
                      {/* Date: 120px fixed, nowrap */}
                      <td className="px-3.5 text-[12.5px] text-left align-middle whitespace-nowrap" style={{ color: 'var(--ink-muted)' }}>
                        {formatDateTable(p.payment_date)}
                      </td>

                      {/* Amount: 140px right-aligned, tabular */}
                      <td className="px-3.5 text-right font-[500] font-mono tabular-nums align-middle" style={{ color: 'var(--ok-ink)' }}>
                        {p.amount_display}
                      </td>

                      {/* Client & Project: auto, takes remainder */}
                      <td className="px-3.5 text-left align-middle min-w-0">
                        <div className="font-[500] truncate" style={{ color: 'var(--ink)' }}>
                          <button
                            type="button"
                            className="hover:underline text-left"
                            onClick={() => onNavigate(`/clients/${p.client_id}`)}
                          >
                            {p.client_name}
                          </button>
                        </div>
                        <div className="text-[12px] leading-snug truncate" style={{ color: 'var(--ink-faint)' }} title={p.project}>
                          {p.project}
                        </div>
                      </td>

                      {/* Invoice: 104px monospace link */}
                      <td className="px-3.5 font-mono font-[500] text-left align-middle">
                        <button
                          type="button"
                          onClick={() => onNavigate(`/invoices/${p.invoice_id}`)}
                          className="hover:underline text-left cursor-pointer"
                          style={{ color: 'var(--ink)' }}
                        >
                          {p.invoice_number}
                        </button>
                      </td>

                      {/* Method: 130px neutral badge with reference beneath in --ink-faint */}
                      <td className="px-3.5 text-left align-middle">
                        {p.method ? (
                          <Badge variant="neutral">{p.method}</Badge>
                        ) : (
                          <span className="text-[12px]" style={{ color: 'var(--ink-faint)' }}>Not recorded</span>
                        )}
                        {p.reference && (
                          <div className="text-[11px] font-mono mt-0.5 truncate" style={{ color: 'var(--ink-faint)' }}>
                            {p.reference}
                          </div>
                        )}
                      </td>

                      {/* Receipt: 140px monospace number linking to receipt PDF */}
                      <td className="px-3.5 font-mono font-[500] text-left align-middle">
                        {p.receipt_number ? (
                          <button
                            type="button"
                            onClick={() => onViewReceiptPdf(p)}
                            className="hover:underline text-left cursor-pointer"
                            style={{ color: 'var(--ink)' }}
                            title="View receipt PDF"
                          >
                            {p.receipt_number}
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => onViewReceiptPdf(p)}
                            className="font-sans text-[12px] hover:underline text-left cursor-pointer"
                            style={{ color: 'var(--accent-ink)' }}
                            title="Issues a receipt number for this payment"
                          >
                            Issue receipt
                          </button>
                        )}
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
