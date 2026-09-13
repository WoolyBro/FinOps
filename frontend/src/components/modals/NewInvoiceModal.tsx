import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../lib/api';
import { formatDateProse, todayISO } from '../../lib/format';
import { ApiError, Client, Invoice } from '../../types';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { useToast } from '../ui/Toast';

/** Thirty days after `iso` — the usual net-30 terms. Date arithmetic only. */
function net30(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  const due = new Date(Date.UTC(y, m - 1, d + 30));
  return due.toISOString().slice(0, 10);
}

type NewInvoiceModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onInvoiceCreated: (invoice: Invoice) => void;
  preselectedClientId?: number;
};

export const NewInvoiceModal: React.FC<NewInvoiceModalProps> = ({
  isOpen,
  onClose,
  onInvoiceCreated,
  preselectedClientId,
}) => {
  const { addToast } = useToast();
  const [clients, setClients] = useState<Client[]>([]);
  const [clientSearch, setClientSearch] = useState('');
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isClientDropdownOpen, setIsClientDropdownOpen] = useState(false);

  const [project, setProject] = useState('');
  const [rawAmount, setRawAmount] = useState('');
  const [parsedDisplay, setParsedDisplay] = useState<string | null>(null);
  const [parsedMinor, setParsedMinor] = useState<number | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);

  const [issueDate, setIssueDate] = useState(todayISO());
  const [dueDate, setDueDate] = useState(net30(todayISO()));
  const [description, setDescription] = useState('');

  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<number | null>(null);

  // Load clients
  useEffect(() => {
    if (isOpen) {
      api
        .getClients()
        .then((res) => {
          setClients(res.clients);
          if (preselectedClientId) {
            const c = res.clients.find((cl) => cl.client_id === preselectedClientId);
            if (c) {
              setSelectedClient(c);
              setClientSearch(c.name);
            }
          }
        })
        .catch((err: ApiError) => setFormError(err.detail));
      // Reset form
      setDuplicateWarning(null);
      setFormError(null);
      setSelectedClient(null);
      setClientSearch('');
      setProject('');
      setRawAmount('');
      setParsedDisplay(null);
      setParsedMinor(null);
      setParseError(null);
      setDescription('');
      setIssueDate(todayISO());
      setDueDate(net30(todayISO()));
    }
  }, [isOpen, preselectedClientId]);

  // Debounced amount parse (300ms)
  useEffect(() => {
    if (!rawAmount.trim()) {
      setParsedDisplay(null);
      setParsedMinor(null);
      setParseError(null);
      return;
    }

    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }

    setIsParsing(true);
    debounceTimerRef.current = window.setTimeout(async () => {
      try {
        const res = await api.parseAmount(rawAmount);
        setParsedDisplay(res.amount_display);
        setParsedMinor(res.amount_minor);
        setParseError(null);
      } catch (err: any) {
        setParsedDisplay(null);
        setParsedMinor(null);
        setParseError(err.detail || 'Could not parse amount');
      } finally {
        setIsParsing(false);
      }
    }, 300);

    return () => {
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
    };
  }, [rawAmount]);

  const filteredClients = clients.filter((c) =>
    c.name.toLowerCase().includes(clientSearch.toLowerCase())
  );

  const handleCreateInlineClient = async (name: string) => {
    setFormError(null);
    let client: Client;
    try {
      client = await api.postClient({ name });
      setClients((prev) => [...prev, client]);
      addToast(`Added client ${client.name}`);
    } catch (err) {
      const failure = err as ApiError;
      // The server matches names case- and space-insensitively; use the match.
      if (failure.error === 'already_exists' && failure.result?.client) {
        client = failure.result.client as Client;
      } else {
        setFormError(failure.detail);
        return;
      }
    }
    setSelectedClient(client);
    setClientSearch(client.name);
    setIsClientDropdownOpen(false);
  };

  const handleSubmit = async (allowDuplicate = false) => {
    if (!selectedClient || !project.trim() || !parsedMinor) return;

    setIsSubmitting(true);
    setFormError(null);
    try {
      const created = await api.postInvoice({
        client_id: selectedClient.client_id,
        project: project.trim(),
        amount_minor: parsedMinor,
        issue_date: issueDate,
        due_date: dueDate || null,
        description: description.trim() || null,
        allow_duplicate: allowDuplicate,
      });
      onInvoiceCreated(created);
      onClose();
    } catch (err) {
      const failure = err as ApiError;
      const existing = failure.result?.existing_invoice as Invoice | undefined;
      if (failure.error === 'duplicate_suspected' && existing) {
        setDuplicateWarning(
          `${existing.invoice_number} was already issued to ${existing.client_name} on ${formatDateProse(existing.issue_date)} for ${existing.amount_display} (${existing.project}).`,
        );
      } else {
        // The server's wording: it names the field and the reason.
        setFormError(failure.detail);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="New invoice"
      subtitle="Issue a new invoice for client work"
      maxWidth={640}
    >
      <div className="space-y-4 text-[13.5px]">
        {/* Duplicate Warning per Section 5.3 */}
        {duplicateWarning && (
          <div
            className="p-3 rounded-[6px] border text-[13px] leading-relaxed"
            style={{
              backgroundColor: 'var(--warn-bg)',
              borderColor: 'var(--warn-ink)',
              color: 'var(--warn-ink)',
            }}
          >
            <div className="font-[600] mb-1">This looks like an invoice you already raised</div>
            <div className="mb-3">{duplicateWarning} Create a second one only if this is separate work.</div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="default"
                onClick={() => setDuplicateWarning(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => handleSubmit(true)}
                busy={isSubmitting}
                busyText="Creating…"
              >
                Create anyway
              </Button>
            </div>
          </div>
        )}

        {formError && (
          <div
            role="alert"
            className="p-3 rounded-[6px] border text-[13px]"
            style={{ backgroundColor: 'var(--bad-bg)', borderColor: 'var(--bad-line)', color: 'var(--bad-ink)' }}
          >
            {formError}
          </div>
        )}

        {/* Client Combobox */}
        <div className="relative" ref={dropdownRef}>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Client <span style={{ color: 'var(--bad-ink)' }}>*</span>
          </label>
          <input
            type="text"
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="Search clients or type a new name…"
            value={clientSearch}
            onChange={(e) => {
              setClientSearch(e.target.value);
              setSelectedClient(null);
              setIsClientDropdownOpen(true);
            }}
            onFocus={() => setIsClientDropdownOpen(true)}
          />

          {isClientDropdownOpen && (
            <div
              className="absolute left-0 right-0 mt-1 max-h-48 overflow-y-auto border rounded-[6px] z-50 transition-standard"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--line)',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              {filteredClients.map((client) => (
                <div
                  key={client.client_id}
                  className="px-3 py-2 cursor-pointer transition-standard hover:bg-[var(--surface-sunken)] flex justify-between items-center"
                  onClick={() => {
                    setSelectedClient(client);
                    setClientSearch(client.name);
                    setIsClientDropdownOpen(false);
                  }}
                >
                  <span className="font-[500]" style={{ color: 'var(--ink)' }}>
                    {client.name}
                  </span>
                  <span className="text-[12px]" style={{ color: 'var(--ink-muted)' }}>
                    {client.email || client.phone || ''}
                  </span>
                </div>
              ))}

              {/* Offer create new client if typed something not exactly matching */}
              {clientSearch.trim() &&
                !clients.some(
                  (c) => c.name.toLowerCase() === clientSearch.trim().toLowerCase()
                ) && (
                  <div
                    className="px-3 py-2 border-t cursor-pointer font-[500] hover:bg-[var(--accent-wash)]"
                    style={{
                      borderColor: 'var(--line)',
                      color: 'var(--accent-ink)',
                    }}
                    onClick={() => handleCreateInlineClient(clientSearch.trim())}
                  >
                    + Create &ldquo;{clientSearch.trim()}&rdquo; as a new client
                  </div>
                )}
            </div>
          )}
        </div>

        {/* Project */}
        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Project <span style={{ color: 'var(--bad-ink)' }}>*</span>
          </label>
          <input
            type="text"
            required
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="e.g. Brand identity refresh, Backend API build"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          />
        </div>

        {/* Amount with Shorthand & Live Parse */}
        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Amount <span style={{ color: 'var(--bad-ink)' }}>*</span>
          </label>
          <input
            type="text"
            required
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="e.g. 40k, 1.5 lakh, or 85000"
            value={rawAmount}
            onChange={(e) => setRawAmount(e.target.value)}
          />
          <div className="min-h-[20px] mt-1.5 text-[12.5px]">
            {isParsing && (
              <span style={{ color: 'var(--ink-faint)' }}>Parsing amount…</span>
            )}
            {!isParsing && parsedDisplay && (
              <span className="font-[600] tabular-nums" style={{ color: 'var(--ink-muted)' }}>
                Will bill: {parsedDisplay}
              </span>
            )}
            {!isParsing && parseError && (
              <span style={{ color: 'var(--bad-ink)' }}>{parseError}</span>
            )}
          </div>
        </div>

        {/* Dates row */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
              Issue date
            </label>
            <input
              type="date"
              className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)] tabular-nums"
              style={{
                borderColor: 'var(--line-strong)',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-strong)',
              }}
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
            />
          </div>
          <div>
            <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
              Due date (optional)
            </label>
            <input
              type="date"
              className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)] tabular-nums"
              style={{
                borderColor: 'var(--line-strong)',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-strong)',
              }}
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Description (optional)
          </label>
          <textarea
            rows={3}
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="Summary of deliverables or milestones covered by this invoice…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* Modal Actions */}
        <div className="flex justify-end gap-2 pt-3 border-t" style={{ borderColor: 'var(--line)' }}>
          <Button type="button" variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            disabled={!selectedClient || !project.trim() || !parsedMinor || !!parseError}
            busy={isSubmitting}
            busyText="Creating invoice…"
            onClick={() => handleSubmit(false)}
          >
            Create invoice
          </Button>
        </div>
      </div>
    </Modal>
  );
};
