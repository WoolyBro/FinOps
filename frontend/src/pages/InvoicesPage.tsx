import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { Invoice } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Panel } from '../components/ui/Panel';
import { EmptyState } from '../components/ui/EmptyState';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { formatDateTable } from '../lib/format';
import { IconPlus, IconSearch, IconDownload } from '../components/Icons';

type InvoicesPageProps = {
  onNavigate: (path: string) => void;
  onOpenNewInvoice: () => void;
  onOpenRecordPayment: (invoice: Invoice) => void;
  onViewPdf: (invoice: Invoice) => void;
  flashInvoiceId?: string | number | null;
};

type FilterStatus = 'ALL' | 'UNPAID' | 'PARTIALLY_PAID' | 'PAID' | 'OVERDUE';

export const InvoicesPage: React.FC<InvoicesPageProps> = ({
  onNavigate,
  onOpenNewInvoice,
  onOpenRecordPayment,
  onViewPdf,
  flashInvoiceId,
}) => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterStatus>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const hasAnimated = useRef(false);

  const loadInvoices = async () => {
    try {
      setLoading(true);
      const res = await api.getInvoices();
      setInvoices(res.invoices);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, []);

  useEffect(() => {
    if (invoices.length > 0) {
      hasAnimated.current = true;
    }
  }, [invoices]);

  // Filter & search logic
  const filteredInvoices = invoices.filter((inv) => {
    // Filter segmented status
    if (filter === 'UNPAID' && (inv.invoice_status !== 'UNPAID' || inv.is_overdue)) return false;
    if (filter === 'PARTIALLY_PAID' && inv.invoice_status !== 'PARTIALLY_PAID') return false;
    if (filter === 'PAID' && inv.invoice_status !== 'PAID') return false;
    if (filter === 'OVERDUE' && (!inv.is_overdue || inv.invoice_status === 'PAID')) return false;

    // Search input: client name, invoice number, or project
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchNumber = inv.invoice_number.toLowerCase().includes(q);
      const matchClient = inv.client_name.toLowerCase().includes(q);
      const matchProject = inv.project.toLowerCase().includes(q);
      if (!matchNumber && !matchClient && !matchProject) return false;
    }

    return true;
  });

  return (
    <div className="space-y-3.5">
      <PageHeader
        title="Invoices"
        actions={
          <Button
            variant="primary"
            icon={<IconPlus size={15} />}
            onClick={onOpenNewInvoice}
          >
            New invoice
          </Button>
        }
      />

      {/* Segmented Filter Control and Search */}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        {/* Segmented filter control */}
        <div
          className="inline-flex p-0.5 rounded-[6px] border text-[12.5px] font-[500]"
          style={{
            backgroundColor: 'var(--surface-sunken)',
            borderColor: 'var(--line)',
          }}
        >
          {(
            [
              { id: 'ALL', label: 'All' },
              { id: 'UNPAID', label: 'Unpaid' },
              { id: 'PARTIALLY_PAID', label: 'Partially paid' },
              { id: 'PAID', label: 'Paid' },
              { id: 'OVERDUE', label: 'Overdue' },
            ] as const
          ).map((item) => {
            const active = filter === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
                className="px-2.5 py-1 rounded-[4px] transition-standard text-left"
                style={{
                  backgroundColor: active ? 'var(--surface)' : 'transparent',
                  color: active ? 'var(--ink)' : 'var(--ink-muted)',
                  fontWeight: active ? 600 : 500,
                  boxShadow: active ? 'var(--shadow-xs)' : 'none',
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        {/* Live Search Input */}
        <div className="relative w-full sm:w-60">
          <span
            className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: 'var(--ink-faint)' }}
          >
            <IconSearch size={13} />
          </span>
          <input
            type="text"
            className="w-full pl-7 pr-3 py-1 border rounded-[6px] text-[12.5px] transition-standard focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--line-strong)',
              color: 'var(--ink-strong)',
            }}
            placeholder="Search client, project, #…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Six-Column Table Panel: PRIMARY carries elevation="sm" */}
      <Panel elevation="sm" noPadding>
        {loading ? (
          <LoadingSkeleton message="Loading invoices…" rows={8} />
        ) : filteredInvoices.length === 0 ? (
          invoices.length === 0 ? (
            <EmptyState
              title="No invoices yet"
              description="No invoices issued yet. Create your first invoice or tell the agent to bill a client."
              action={
                <Button variant="primary" onClick={onOpenNewInvoice}>
                  Create invoice
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No invoices match the filter"
              description={`No invoices found matching "${searchQuery || filter}".`}
              action={
                <Button
                  variant="default"
                  onClick={() => {
                    setFilter('ALL');
                    setSearchQuery('');
                  }}
                >
                  Reset filters
                </Button>
              }
            />
          )
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[760px]" style={{ tableLayout: 'fixed' }}>
              <colgroup>
                <col style={{ width: '104px' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: '140px' }} />
                <col style={{ width: '128px' }} />
                <col style={{ width: '150px' }} />
                <col style={{ width: '180px' }} />
              </colgroup>
              <thead
                style={{
                  backgroundColor: 'var(--surface-sunken)',
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <tr className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-muted)' }}>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Invoice</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Client & Project</th>
                  <th scope="col" className="py-2.5 px-3.5 text-right">Amount</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left">Status</th>
                  <th scope="col" className="py-2.5 px-3.5 text-left whitespace-nowrap">Due</th>
                  <th scope="col" className="py-2.5 px-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y text-[13px]" style={{ borderColor: 'var(--line)' }}>
                {filteredInvoices.map((inv, idx) => {
                  const isCancelled = inv.invoice_status === 'CANCELLED';
                  const shouldAnimate = !hasAnimated.current;

                  return (
                    <tr
                      key={inv.invoice_id}
                      className={`table-row ${shouldAnimate ? 'table-row-enter' : ''} ${flashInvoiceId === inv.invoice_id ? 'optimistic-flash' : ''}`}
                      style={{
                        height: '52px',
                        ...(shouldAnimate ? { animationDelay: `${Math.min(idx, 10) * 24}ms` } : {}),
                      }}
                    >
                      {/* 1. Invoice (104px fixed, monospace number, links to detail page) */}
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

                      {/* 2. Client & Project (takes slack, single line with ellipsis) */}
                      <td className="px-3.5 text-left align-middle min-w-0">
                        <div className="font-[500] truncate" style={{ color: 'var(--ink)' }}>
                          {inv.client_name}
                        </div>
                        <div
                          className="text-[12px] leading-snug truncate"
                          style={{ color: 'var(--ink-faint)' }}
                          title={inv.project}
                        >
                          {inv.project}
                        </div>
                      </td>

                      {/* 3. Amount (140px right-aligned, tabular, struck through if cancelled) */}
                      <td className="px-3.5 text-right tabular-nums align-middle">
                        <div
                          className={`font-[500] ${isCancelled ? 'line-through' : ''}`}
                          style={{ color: isCancelled ? 'var(--ink-faint)' : 'var(--ink)' }}
                        >
                          {inv.amount_display}
                        </div>
                        {inv.invoice_status === 'PARTIALLY_PAID' && (
                          <div
                            className="text-[11.5px]"
                            style={{ color: 'var(--ink-faint)' }}
                          >
                            {inv.outstanding_display} left
                          </div>
                        )}
                      </td>

                      {/* 4. Status (128px fixed: stacked status badge above, overdue badge below) */}
                      <td className="px-3.5 text-left align-middle">
                        <div className="flex flex-col items-start gap-1">
                          <Badge status={inv.invoice_status} />
                          {inv.is_overdue && inv.invoice_status !== 'PAID' && !isCancelled && (
                            <Badge status="OVERDUE" daysOverdue={inv.days_overdue} />
                          )}
                        </div>
                      </td>

                      {/* 5. Due (150px fixed, white-space: nowrap, date only) */}
                      <td className="px-3.5 text-[12.5px] text-left align-middle whitespace-nowrap" style={{ color: 'var(--ink-muted)' }}>
                        {formatDateTable(inv.due_date)}
                      </td>

                      {/* 6. Actions (180px fixed: fixed two-slot grid: Record payment slot + PDF slot) */}
                      <td className="px-3.5 align-middle">
                        <div
                          className="row-actions grid items-center gap-1.5"
                          style={{ gridTemplateColumns: '1fr auto' }}
                        >
                          <div className="flex justify-end">
                            {inv.invoice_status !== 'PAID' && !isCancelled ? (
                              <Button
                                variant="primary"
                                style={{ fontSize: '11.5px', padding: '3px 8px', whiteSpace: 'nowrap' }}
                                onClick={() => onOpenRecordPayment(inv)}
                              >
                                Record payment
                              </Button>
                            ) : null}
                          </div>
                          <div className="w-[50px] flex justify-end">
                            {inv.pdf_available ? (
                              <Button
                                variant="default"
                                icon={<IconDownload size={12} />}
                                style={{ fontSize: '11.5px', padding: '3px 6px', whiteSpace: 'nowrap' }}
                                onClick={() => onViewPdf(inv)}
                                title="Download PDF"
                              >
                                PDF
                              </Button>
                            ) : null}
                          </div>
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
