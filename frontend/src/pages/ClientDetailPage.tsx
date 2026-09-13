import React, { useState, useEffect, useRef } from 'react';
import { api, totalText } from '../lib/api';
import { Client, ClientBalance, Invoice, Payment } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { StatTile } from '../components/ui/StatTile';
import { Panel } from '../components/ui/Panel';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { useToast } from '../components/ui/Toast';
import { formatDateTable } from '../lib/format';
import { IconPencil, IconPlus, IconDownload } from '../components/Icons';

type ClientDetailPageProps = {
  clientId: number;
  onNavigate: (path: string) => void;
  onOpenNewInvoice: (clientId?: number) => void;
  onOpenRecordPayment: (invoice: Invoice) => void;
  onViewPdf: (invoice: Invoice) => void;
  onViewReceiptPdf: (payment: Payment) => void;
};

export const ClientDetailPage: React.FC<ClientDetailPageProps> = ({
  clientId,
  onNavigate,
  onOpenNewInvoice,
  onOpenRecordPayment,
  onViewPdf,
  onViewReceiptPdf,
}) => {
  const { addToast } = useToast();
  const [balance, setBalance] = useState<ClientBalance | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);

  // Inline editing state for email and phone
  const [editingField, setEditingField] = useState<'email' | 'phone' | null>(null);
  const [editValue, setEditValue] = useState('');
  const hasAnimated = useRef(false);

  const loadClientData = async () => {
    try {
      setLoading(true);
      const [detailRes, clientsRes] = await Promise.all([
        api.getClientDetail(clientId),
        api.getClients(),
      ]);
      setBalance(detailRes.balance);
      setInvoices(detailRes.invoices);
      setPayments(detailRes.payments);
      const foundClient = clientsRes.clients.find((c) => c.client_id === clientId);
      if (foundClient) setClient(foundClient);
    } catch {
      setClient(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClientData();
  }, [clientId]);

  useEffect(() => {
    if (invoices.length > 0 || payments.length > 0) {
      hasAnimated.current = true;
    }
  }, [invoices, payments]);

  const handleStartEdit = (field: 'email' | 'phone') => {
    setEditingField(field);
    setEditValue(client ? (client[field] || '') : '');
  };

  const handleCancelEdit = () => {
    setEditingField(null);
    setEditValue('');
  };

  const handleCommitEdit = async () => {
    if (!editingField || !client) return;
    try {
      const updated = await api.patchClient(client.client_id, {
        field: editingField,
        value: editValue.trim() || null,
      });
      setClient(updated);
      setEditingField(null);
      addToast(`Updated ${updated.name}'s ${editingField}`);
    } catch (err: any) {
      // The server's own reason, e.g. an email it could not accept.
      addToast(err.detail || `Could not update the ${editingField}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCommitEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  if (loading) {
    return <LoadingSkeleton message="Loading client account details…" rows={6} />;
  }

  if (!client || !balance) {
    return (
      <EmptyState
        title="Client not found"
        description={`Could not find client #${clientId}.`}
        action={
          <Button variant="default" onClick={() => onNavigate('/clients')}>
            Back to clients
          </Button>
        }
      />
    );
  }

  // Distribution counts
  const paidCount = balance.invoice_counts_by_status['PAID'] || 0;
  const unpaidCount = balance.invoice_counts_by_status['UNPAID'] || 0;
  const partialCount = balance.invoice_counts_by_status['PARTIALLY_PAID'] || 0;
  // The balance covers live invoices only, so these two come from the list:
  // cancelled invoices are listed but not balanced, and "overdue" is an
  // attribute of an invoice, not a status the balance counts.
  const cancelledCount = invoices.filter((i) => i.invoice_status === 'CANCELLED').length;
  const overdueCount = invoices.filter((i) => i.is_overdue).length;

  return (
    <div className="space-y-3.5">
      {/* Back link */}
      <div>
        <button
          type="button"
          onClick={() => onNavigate('/clients')}
          className="text-[12.5px] font-[500] hover:underline"
          style={{ color: 'var(--ink-muted)' }}
        >
          ← Back to clients
        </button>
      </div>

      {/* Header with inline editable phone & email */}
      <PageHeader
        title={client.name}
        subtitle={
          <div className="flex flex-wrap items-center gap-3 text-[13px] mt-1">
            {/* Email with edit affordance */}
            <div className="flex items-center gap-1.5">
              {editingField === 'email' ? (
                <div className="flex items-center gap-1">
                  <input
                    type="email"
                    autoFocus
                    className="px-2 py-0.5 border rounded-[4px] text-[12.5px] outline-none ring-1 ring-[var(--accent)]"
                    style={{ borderColor: 'var(--accent)' }}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onBlur={handleCommitEdit}
                    placeholder="email@domain.com"
                  />
                  <span className="text-[10.5px]" style={{ color: 'var(--ink-faint)' }}>
                    Enter to save · Esc
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1 group">
                  {client.email ? (
                    <span style={{ color: 'var(--ink-muted)' }}>{client.email}</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleStartEdit('email')}
                      className="italic text-[12px] hover:underline"
                      style={{ color: 'var(--ink-faint)' }}
                    >
                      + Add email
                    </button>
                  )}
                  {client.email && (
                    <button
                      type="button"
                      onClick={() => handleStartEdit('email')}
                      className="p-0.5 rounded hover:bg-[var(--surface-sunken)] transition-standard opacity-60 group-hover:opacity-100"
                      title="Edit email"
                    >
                      <IconPencil size={11} />
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Phone with edit affordance (omitted if null unless editing or hovering) */}
            {client.phone || editingField === 'phone' ? (
              <>
                <span style={{ color: 'var(--line-strong)' }}>·</span>
                <div className="flex items-center gap-1.5">
                  {editingField === 'phone' ? (
                    <div className="flex items-center gap-1">
                      <input
                        type="text"
                        autoFocus
                        className="px-2 py-0.5 border rounded-[4px] text-[12.5px] outline-none ring-1 ring-[var(--accent)]"
                        style={{ borderColor: 'var(--accent)' }}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onBlur={handleCommitEdit}
                        placeholder="+91 …"
                      />
                      <span className="text-[10.5px]" style={{ color: 'var(--ink-faint)' }}>
                        Enter to save · Esc
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 group">
                      <span style={{ color: 'var(--ink-muted)' }}>{client.phone}</span>
                      <button
                        type="button"
                        onClick={() => handleStartEdit('phone')}
                        className="p-0.5 rounded hover:bg-[var(--surface-sunken)] transition-standard opacity-60 group-hover:opacity-100"
                        title="Edit phone"
                      >
                        <IconPencil size={11} />
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <span style={{ color: 'var(--line-strong)' }}>·</span>
                <button
                  type="button"
                  onClick={() => handleStartEdit('phone')}
                  className="italic text-[12px] hover:underline"
                  style={{ color: 'var(--ink-faint)' }}
                >
                  + Add phone
                </button>
              </>
            )}
          </div>
        }
        actions={
          <Button
            variant="primary"
            icon={<IconPlus size={15} />}
            onClick={() => onOpenNewInvoice(client.client_id)}
          >
            New invoice
          </Button>
        }
      />

      {/* Four tiles: Invoiced, Paid, Outstanding, Overdue */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Invoiced"
          value={totalText(balance.invoiced_total)}
        />
        <StatTile
          label="Paid"
          value={totalText(balance.paid_total)}
        />
        <StatTile
          label="Outstanding"
          value={totalText(balance.outstanding_total)}
        />
        <StatTile
          label="Overdue"
          value={totalText(balance.overdue_total)}
          isDanger={(balance.overdue_total[0]?.total_minor || 0) > 0}
        />
      </div>

      {/* Small status distribution strip */}
      <div
        className="flex flex-wrap items-center gap-2 text-[12px] px-3.5 py-2 rounded-[6px] border"
        style={{
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--line)',
        }}
      >
        <span className="font-[500] mr-1" style={{ color: 'var(--ink)' }}>
          Portfolio breakdown:
        </span>
        <Badge variant="ok">{paidCount} paid</Badge>
        {unpaidCount > 0 && <Badge variant="neutral">{unpaidCount} unpaid</Badge>}
        {partialCount > 0 && <Badge variant="warn">{partialCount} partially paid</Badge>}
        {cancelledCount > 0 && <Badge variant="neutral">{cancelledCount} cancelled</Badge>}
        {overdueCount > 0 && (
          <span className="text-[11.5px] ml-1 font-[500]" style={{ color: 'var(--bad-ink)' }}>
            ({overdueCount} of these overdue)
          </span>
        )}
      </div>

      {/* Two panels: Invoices and Payments */}
      <div className="space-y-4">
        {/* Scoped Invoices Panel: PRIMARY carries elevation="sm" */}
        <Panel
          elevation="sm"
          density="dense"
          title="Invoices"
          subtitle={`Billing records issued to ${client.name}`}
          actions={
            <Button
              variant="default"
              style={{ fontSize: '11.5px', padding: '3px 8px' }}
              onClick={() => onOpenNewInvoice(client.client_id)}
            >
              Issue invoice
            </Button>
          }
          noPadding
        >
          {invoices.length === 0 ? (
            <div className="p-7 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
              No invoices issued to this client yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[760px] text-[13px]" style={{ tableLayout: 'fixed' }}>
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
                    <th scope="col" className="py-2.5 px-3.5 text-left">Project</th>
                    <th scope="col" className="py-2.5 px-3.5 text-right">Amount</th>
                    <th scope="col" className="py-2.5 px-3.5 text-left">Status</th>
                    <th scope="col" className="py-2.5 px-3.5 text-left whitespace-nowrap">Due</th>
                    <th scope="col" className="py-2.5 px-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                  {invoices.map((inv, idx) => {
                    const isCancelled = inv.invoice_status === 'CANCELLED';
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
                        {/* 1. Invoice (104px fixed) */}
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

                        {/* 2. Project (takes slack, single line with ellipsis) */}
                        <td className="px-3.5 text-left align-middle min-w-0">
                          <div className="truncate text-[13px]" style={{ color: 'var(--ink)' }} title={inv.project}>
                            {inv.project}
                          </div>
                        </td>

                        {/* 3. Amount (140px fixed, right-aligned, tabular) */}
                        <td className="px-3.5 text-right tabular-nums align-middle">
                          <div
                            className={`font-[500] ${isCancelled ? 'line-through' : ''}`}
                            style={{ color: isCancelled ? 'var(--ink-faint)' : 'var(--ink)' }}
                          >
                            {inv.amount_display}
                          </div>
                          {inv.invoice_status === 'PARTIALLY_PAID' && (
                            <div className="text-[11.5px]" style={{ color: 'var(--ink-faint)' }}>
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

        {/* Scoped Payments Panel: FLAT border only */}
        <Panel
          elevation="none"
          density="dense"
          title="Payment ledger"
          subtitle={`All receipts recorded from ${client.name}`}
          noPadding
        >
          {payments.length === 0 ? (
            <div className="p-7 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
              No payments recorded from this client yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[650px] text-[13px]" style={{ tableLayout: 'fixed' }}>
                <colgroup>
                  <col style={{ width: '120px' }} />
                  <col style={{ width: '140px' }} />
                  <col style={{ width: '104px' }} />
                  <col style={{ width: '130px' }} />
                  <col style={{ width: 'auto' }} />
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
                    <th scope="col" className="py-2.5 px-3.5 text-left">Invoice</th>
                    <th scope="col" className="py-2.5 px-3.5 text-left">Method</th>
                    <th scope="col" className="py-2.5 px-3.5 text-left">Receipt</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                  {payments.map((p, idx) => {
                    const shouldAnimate = !hasAnimated.current;
                    return (
                      <tr
                        key={p.payment_id}
                        className={`table-row ${shouldAnimate ? 'table-row-enter' : ''}`}
                        style={{
                          height: '52px',
                          ...(shouldAnimate ? { animationDelay: `${Math.min(idx, 10) * 24}ms` } : {}),
                        }}
                      >
                        <td className="px-3.5 text-[12.5px] text-left align-middle whitespace-nowrap" style={{ color: 'var(--ink-muted)' }}>
                          {formatDateTable(p.payment_date)}
                        </td>
                        <td className="px-3.5 text-right font-[500] font-mono tabular-nums align-middle" style={{ color: 'var(--ok-ink)' }}>
                          {p.amount_display}
                        </td>
                        <td className="px-3.5 font-mono text-left align-middle">
                          <button
                            type="button"
                            onClick={() => onNavigate(`/invoices/${p.invoice_id}`)}
                            className="hover:underline"
                            style={{ color: 'var(--ink)' }}
                          >
                            {p.invoice_number}
                          </button>
                        </td>
                        <td className="px-3.5 text-left align-middle">
                          {p.method ? <Badge variant="neutral">{p.method}</Badge> : <span className="text-[12px]" style={{ color: 'var(--ink-faint)' }}>Not recorded</span>}
                        </td>
                        <td className="px-3.5 font-mono font-[500] text-left align-middle truncate">
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
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
};
