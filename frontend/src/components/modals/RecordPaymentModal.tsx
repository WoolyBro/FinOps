import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../lib/api';
import { formatDateProse, todayISO } from '../../lib/format';
import { ApiError, Invoice, Payment } from '../../types';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

type RecordPaymentModalProps = {
  isOpen: boolean;
  onClose: () => void;
  invoice: Invoice | null;
  onPaymentRecorded: (result: { payment: Payment; invoice: Invoice }) => void;
};

export const RecordPaymentModal: React.FC<RecordPaymentModalProps> = ({
  isOpen,
  onClose,
  invoice,
  onPaymentRecorded,
}) => {
  const [rawAmount, setRawAmount] = useState('');
  const [parsedDisplay, setParsedDisplay] = useState<string | null>(null);
  const [parsedMinor, setParsedMinor] = useState<number | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [paymentDate, setPaymentDate] = useState(todayISO());
  // Blank unless the user says: a method or reference the freelancer did not
  // enter would be printed on the receipt as if it were fact.
  const [method, setMethod] = useState('');
  const [reference, setReference] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const parseSeq = useRef(0);

  useEffect(() => {
    if (isOpen && invoice) {
      setErrorMessage(null);
      setDuplicate(null);
      setParseError(null);
      setPaymentDate(todayISO());
      setMethod('');
      setReference('');
      // Start from the full balance — the common case is being paid in full.
      setRawAmount(invoice.outstanding_display.replace(/[^\d.]/g, ''));
      setParsedDisplay(invoice.outstanding_display);
      setParsedMinor(invoice.outstanding_minor);
    }
  }, [isOpen, invoice]);

  const handleAmountChange = (val: string) => {
    setRawAmount(val);
    setErrorMessage(null);
    setDuplicate(null);
    const seq = ++parseSeq.current;
    if (!val.trim()) {
      setParsedDisplay(null);
      setParsedMinor(null);
      setParseError(null);
      return;
    }
    window.setTimeout(async () => {
      if (seq !== parseSeq.current) return; // a newer keystroke superseded this one
      try {
        const res = await api.parseAmount(val);
        if (seq !== parseSeq.current) return;
        setParsedDisplay(res.amount_display);
        setParsedMinor(res.amount_minor);
        setParseError(null);
      } catch (err) {
        if (seq !== parseSeq.current) return;
        setParsedDisplay(null);
        setParsedMinor(null);
        setParseError((err as ApiError).detail);
      }
    }, 250);
  };

  const submit = async (allowDuplicate: boolean) => {
    if (!invoice || !parsedMinor) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const result = await api.postPayment({
        invoice_id: invoice.invoice_id,
        amount_minor: parsedMinor,
        payment_date: paymentDate,
        method: method || null,
        reference: reference.trim() || null,
        allow_duplicate: allowDuplicate,
      });
      onPaymentRecorded(result);
      onClose();
    } catch (err) {
      const failure = err as ApiError;
      const existing = failure.result?.existing_payment as Payment | undefined;
      if (failure.error === 'duplicate_suspected' && existing) {
        setDuplicate(
          `${existing.amount_display} from ${existing.client_name} on ${formatDateProse(existing.payment_date)} is already recorded against ${existing.invoice_number}${
            existing.reference ? ` (ref ${existing.reference})` : ''
          }.`,
        );
      } else {
        // The server's own wording — it names the amount and the balance.
        setErrorMessage(failure.detail);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit(false);
  };

  if (!invoice) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Record incoming payment"
      subtitle={`Against invoice ${invoice.invoice_number} · ${invoice.client_name}`}
      maxWidth={480}
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-[13.5px]">
        {errorMessage && (
          <div
            role="alert"
            className="p-3 rounded-[6px] border text-[13px]"
            style={{ backgroundColor: 'var(--bad-bg)', borderColor: 'var(--bad-line)', color: 'var(--bad-ink)' }}
          >
            {errorMessage}
          </div>
        )}

        {duplicate && (
          <div
            role="alert"
            className="p-3 rounded-[6px] border text-[13px] leading-relaxed"
            style={{ backgroundColor: 'var(--warn-bg)', borderColor: 'var(--warn-line)', color: 'var(--warn-ink)' }}
          >
            <div className="font-[600] mb-1">This looks like a payment you already recorded</div>
            <div className="mb-3">{duplicate} Record a second one only if the money really arrived twice.</div>
            <div className="flex gap-2">
              <Button type="button" variant="default" onClick={() => setDuplicate(null)}>
                Cancel
              </Button>
              <Button type="button" variant="primary" onClick={() => submit(true)} busy={isSubmitting} busyText="Recording…">
                Record anyway
              </Button>
            </div>
          </div>
        )}

        <div
          className="p-3 rounded-[6px] border flex justify-between items-center"
          style={{
            backgroundColor: 'var(--surface-sunken)',
            borderColor: 'var(--line)',
          }}
        >
          <div>
            <div className="text-[12px]" style={{ color: 'var(--ink-muted)' }}>
              Outstanding on {invoice.invoice_number}
            </div>
            <div
              className="text-[16px] font-[620] tabular-nums"
              style={{ color: 'var(--ink)' }}
            >
              {invoice.outstanding_display}
            </div>
          </div>
          <div className="text-right text-[12px]" style={{ color: 'var(--ink-faint)' }}>
            Total: {invoice.amount_display}
          </div>
        </div>

        {/* Amount to record */}
        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Amount received <span style={{ color: 'var(--bad-ink)' }}>*</span>
          </label>
          <input
            type="text"
            required
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)] tabular-nums"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="e.g. 15000 or 15k"
            value={rawAmount}
            onChange={(e) => handleAmountChange(e.target.value)}
          />
          {parsedDisplay && !parseError && (
            <div className="text-[12px] font-[550] mt-1 tabular-nums" style={{ color: 'var(--ok-ink)' }}>
              Recording: {parsedDisplay}
            </div>
          )}
          {parseError && (
            <div className="text-[12px] mt-1" style={{ color: 'var(--bad-ink)' }}>
              {parseError}
            </div>
          )}
        </div>

        {/* Payment Date */}
        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Payment date
          </label>
          <input
            type="date"
            required
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)] tabular-nums"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            value={paymentDate}
            onChange={(e) => setPaymentDate(e.target.value)}
          />
        </div>

        {/* Method & Reference */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
              Payment method
            </label>
            <select
              className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              style={{
                borderColor: 'var(--line-strong)',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-strong)',
              }}
              value={method}
              onChange={(e) => setMethod(e.target.value)}
            >
              <option value="">Not specified</option>
              <option value="UPI">UPI</option>
              <option value="NEFT">NEFT</option>
              <option value="IMPS">IMPS</option>
              <option value="Bank transfer">Bank transfer</option>
              <option value="Cheque">Cheque</option>
            </select>
          </div>
          <div>
            <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
              Reference / UTR
            </label>
            <input
              type="text"
              className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)] font-mono text-[12.5px]"
              style={{
                borderColor: 'var(--line-strong)',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-strong)',
              }}
              placeholder="e.g. UPI/523901147722"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t" style={{ borderColor: 'var(--line)' }}>
          <Button type="button" variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!parsedMinor || parsedMinor <= 0 || !!parseError || !!duplicate}
            busy={isSubmitting}
            busyText="Recording…"
          >
            Record payment
          </Button>
        </div>
      </form>
    </Modal>
  );
};
