import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { ApiError, Reminder } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { useToast } from '../components/ui/Toast';
import { formatDateProse } from '../lib/format';
import { IconCopy } from '../components/Icons';

type RemindersPageProps = {
  onNavigate: (path: string) => void;
};

const small = { fontSize: '11.5px', padding: '3px 8px' } as const;

/**
 * Drafted reminders, for a person to read before anything goes out.
 *
 * Nothing on this page sends a message — there is no delivery integration.
 * Approving records that a human checked the wording; the freelancer copies
 * the text and sends it themselves.
 */
export const RemindersPage: React.FC<RemindersPageProps> = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const loadReminders = async () => {
    try {
      setLoading(true);
      setError(null);
      setReminders((await api.getReminders()).reminders);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReminders();
  }, []);

  const act = async (id: number, action: 'approve' | 'withdraw') => {
    setBusyId(id);
    try {
      const updated = action === 'approve' ? await api.approveReminder(id) : await api.discardReminder(id);
      setReminders((prev) => prev.map((r) => (r.reminder_id === id ? updated : r)));
      addToast(
        action === 'approve'
          ? `Approved the reminder for ${updated.invoice_number} — copy the text to send it`
          : `Withdrew the reminder for ${updated.invoice_number}. It stays on record as cancelled.`,
      );
    } catch (err) {
      addToast((err as ApiError).detail);
    } finally {
      setBusyId(null);
    }
  };

  // Withdraw the out-of-date reminder and draft a fresh one from today's balance.
  const redraft = async (reminder: Reminder) => {
    setBusyId(reminder.reminder_id);
    try {
      await api.discardReminder(reminder.reminder_id);
      await api.postReminder({ invoice_id: reminder.invoice_id });
      addToast(`Redrafted the reminder for ${reminder.invoice_number} with the current balance`);
      await loadReminders();
    } catch (err) {
      addToast((err as ApiError).detail);
    } finally {
      setBusyId(null);
    }
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      addToast('Message copied');
    } catch {
      addToast('Could not reach the clipboard — select the text and copy it instead');
    }
  };

  const groups: { status: Reminder['reminder_status']; label: string }[] = [
    { status: 'DRAFT', label: 'Waiting for review' },
    { status: 'APPROVED', label: 'Approved' },
    { status: 'SENT', label: 'Sent' },
    { status: 'CANCELLED', label: 'Withdrawn' },
  ];

  const card = (reminder: Reminder, prominent: boolean) => {
    const muted = reminder.reminder_status === 'CANCELLED' || reminder.reminder_status === 'SENT';
    const stale = !!reminder.balance_changed;
    const settled = stale && reminder.current_outstanding_minor === 0;
    return (
      <Panel
        key={reminder.reminder_id}
        elevation={prominent ? 'sm' : 'none'}
        density="dense"
        title={
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-[500]">{reminder.client_name}</span>
            <span style={{ color: 'var(--line-strong)' }}>·</span>
            <button
              type="button"
              className="font-mono text-[12.5px] hover:underline"
              onClick={() => onNavigate(`/invoices/${reminder.invoice_id}`)}
            >
              {reminder.invoice_number}
            </button>
            <Badge status={reminder.reminder_status} />
          </div>
        }
        subtitle={[
          reminder.project,
          reminder.client_email ? `to ${reminder.client_email}` : 'no email on file',
          `drafted ${formatDateProse(reminder.created_at.slice(0, 10))}`,
        ].join(' · ')}
        actions={
          stale ? (
            <div className="flex items-center gap-2">
              <Button variant="default" style={small} disabled={busyId === reminder.reminder_id} onClick={() => act(reminder.reminder_id, 'withdraw')}>
                Withdraw
              </Button>
              {!settled && (
                <Button
                  variant="primary"
                  style={{ ...small, padding: '3px 10px' }}
                  busy={busyId === reminder.reminder_id}
                  busyText="Redrafting…"
                  onClick={() => redraft(reminder)}
                >
                  Redraft with current balance
                </Button>
              )}
            </div>
          ) : reminder.reminder_status === 'DRAFT' ? (
            <div className="flex items-center gap-2">
              <Button variant="danger" style={small} disabled={busyId === reminder.reminder_id} onClick={() => act(reminder.reminder_id, 'withdraw')}>
                Withdraw
              </Button>
              <Button
                variant="primary"
                style={{ ...small, padding: '3px 10px' }}
                busy={busyId === reminder.reminder_id}
                busyText="Approving…"
                onClick={() => act(reminder.reminder_id, 'approve')}
              >
                Approve
              </Button>
            </div>
          ) : reminder.reminder_status === 'APPROVED' ? (
            <div className="flex items-center gap-2">
              <Button variant="default" style={small} disabled={busyId === reminder.reminder_id} onClick={() => act(reminder.reminder_id, 'withdraw')}>
                Withdraw
              </Button>
              <Button variant="default" icon={<IconCopy size={13} />} style={small} onClick={() => handleCopy(reminder.message)}>
                Copy message
              </Button>
            </div>
          ) : undefined
        }
      >
        {stale && (
          <div
            role="alert"
            className="mb-2.5 p-2.5 rounded-[5px] border text-[12.5px] leading-relaxed"
            style={{ backgroundColor: 'var(--warn-bg)', borderColor: 'var(--warn-line)', color: 'var(--warn-ink)' }}
          >
            {settled
              ? `${reminder.invoice_number} has been paid in full since this was drafted. Withdraw it — there is nothing left to remind about.`
              : `A payment has landed since this was drafted. ${reminder.invoice_number} now has ${reminder.current_outstanding_display} outstanding, so the amount below is out of date.`}
          </div>
        )}
        <div
          className="p-3 rounded-[5px] border text-[12.5px] leading-relaxed whitespace-pre-wrap font-sans select-text"
          style={{
            backgroundColor: 'var(--surface-sunken)',
            borderColor: 'var(--line)',
            color: muted || stale ? 'var(--ink-muted)' : 'var(--ink-strong)',
            textDecoration: stale ? 'line-through' : undefined,
            textDecorationColor: stale ? 'var(--warn-line)' : undefined,
          }}
        >
          {reminder.message}
        </div>
        {reminder.reminder_status === 'APPROVED' && !stale && (
          <div className="text-[12px] mt-2.5" style={{ color: 'var(--ink-muted)' }}>
            Approved messages are not sent automatically — copy the text and send it yourself.
          </div>
        )}
      </Panel>
    );
  };

  return (
    <div className="space-y-3.5">
      <PageHeader
        title="Reminders"
        actions={
          <Button variant="default" onClick={() => onNavigate('/overdue')}>
            Check overdue invoices
          </Button>
        }
      />

      {error ? (
        <ErrorState error="Could not load reminders" detail={error.detail} onRetry={loadReminders} />
      ) : loading ? (
        <LoadingSkeleton message="Loading reminders…" rows={4} />
      ) : reminders.length === 0 ? (
        <EmptyState
          title="No reminders drafted"
          description="Draft one from any overdue invoice. The wording is built from the invoice itself — number, amount, due date."
          action={
            <Button variant="primary" onClick={() => onNavigate('/overdue')}>
              View overdue invoices
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {groups.map(({ status, label }) => {
            const items = reminders.filter((r) => r.reminder_status === status);
            if (items.length === 0) return null;
            return (
              <section key={status} className="space-y-3" aria-label={label}>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-faint)' }}>
                    {label}
                  </span>
                  <span className="text-[11px] font-mono" style={{ color: 'var(--ink-muted)' }}>
                    ({items.length})
                  </span>
                </div>
                <div className="space-y-3">{items.map((r, idx) => card(r, status === 'DRAFT' && idx === 0))}</div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
};
