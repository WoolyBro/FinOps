import React, { useState, useEffect } from 'react';
import { api, totalMinor, totalText } from '../lib/api';
import { ApiError, ClientBreakdownRow } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { IconPlus } from '../components/Icons';

type ClientsPageProps = {
  onNavigate: (path: string) => void;
  onOpenAddClient: () => void;
};

export const ClientsPage: React.FC<ClientsPageProps> = ({ onNavigate, onOpenAddClient }) => {
  // Balances come from the server, largest amount owed first.
  const [clientsData, setClientsData] = useState<ClientBreakdownRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      setClientsData((await api.getClientBreakdown()).clients);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-3.5">
      <PageHeader
        title="Clients"
        actions={
          <Button
            variant="primary"
            icon={<IconPlus size={15} />}
            onClick={onOpenAddClient}
          >
            Add client
          </Button>
        }
      />

      {error ? (
        <ErrorState error="Could not load clients" detail={error.detail} onRetry={loadData} />
      ) : loading ? (
        <LoadingSkeleton message="Loading clients…" rows={6} />
      ) : clientsData.length === 0 ? (
        <EmptyState
          title="No clients yet"
          description="Register your clients to issue invoices and track balances."
          action={
            <Button variant="primary" onClick={onOpenAddClient}>
              Add client
            </Button>
          }
        />
      ) : (
        /* Card grid, minmax(280px, 1fr), not a table */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {clientsData.map((client) => {
            const totalInvoices = client.invoice_count;
            const paidInvoices = client.paid_invoice_count;
            const isOverdueNonZero = totalMinor(client.overdue_total) > 0;
            return (
              <div
                key={client.client_id}
                role="link"
                tabIndex={0}
                onClick={() => onNavigate(`/clients/${client.client_id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onNavigate(`/clients/${client.client_id}`);
                }}
                className="rounded-[8px] border p-4 cursor-pointer transition-standard flex flex-col justify-between"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--line)',
                  boxShadow: 'none',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--line-strong)';
                  e.currentTarget.style.backgroundColor = 'var(--surface-sunken)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--line)';
                  e.currentTarget.style.backgroundColor = 'var(--surface)';
                }}
              >
                <div>
                  <h3
                    className="text-[14.5px] font-[500] leading-snug tracking-[-0.01em]"
                    style={{ color: 'var(--ink)' }}
                  >
                    {client.name}
                  </h3>
                  <div
                    className="text-[12px] mt-1 space-y-0.5 truncate"
                    style={{ color: 'var(--ink-muted)' }}
                  >
                    <div>
                      {client.email ? (
                        client.email
                      ) : (
                        <span className="italic" style={{ color: 'var(--ink-faint)' }}>
                          No email on file
                        </span>
                      )}
                    </div>
                    {client.phone && <div>{client.phone}</div>}
                  </div>
                </div>

                <div className="mt-3.5 pt-2.5 border-t" style={{ borderColor: 'var(--line)' }}>
                  <div className="grid grid-cols-2 gap-2 text-[12.5px] mb-1.5">
                    <div>
                      <div className="text-[10.5px] font-[550] uppercase tracking-[0.05em]" style={{ color: 'var(--ink-faint)' }}>
                        Outstanding
                      </div>
                      <div className="font-[500] font-mono tabular-nums mt-0.5" style={{ color: 'var(--ink)' }}>
                        {totalText(client.outstanding_total)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10.5px] font-[550] uppercase tracking-[0.05em]" style={{ color: 'var(--ink-faint)' }}>
                        Overdue
                      </div>
                      <div
                        className="font-[500] font-mono tabular-nums mt-0.5"
                        style={{ color: isOverdueNonZero ? 'var(--bad-ink)' : 'var(--ink)' }}
                      >
                        {totalText(client.overdue_total)}
                      </div>
                    </div>
                  </div>

                  <div
                    className="text-[11.5px] font-[450] pt-2 border-t"
                    style={{ borderColor: 'var(--line)', color: 'var(--ink-faint)' }}
                  >
                    {totalInvoices} invoice{totalInvoices === 1 ? '' : 's'} · {paidInvoices} paid
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
