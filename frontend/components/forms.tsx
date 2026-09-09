"use client";

import { useEffect, useState } from "react";
import { ApiError, api, type Client, type Invoice } from "@/lib/api";
import { Field, FormError, Modal } from "@/components/Modal";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Amounts are typed the way people say them and converted by the server.
 *
 * The browser never multiplies by 100. It sends "40k" to the same parser the
 * agent uses and shows back what the server made of it, so what you confirm is
 * what will be stored.
 */
function useAmountPreview(text: string, currency: string) {
  const [preview, setPreview] = useState<{
    minor: number;
    display: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const trimmed = text.trim();
    if (!trimmed) {
      setPreview(null);
      setError(null);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .parseAmount(trimmed, currency)
        .then((parsed) => {
          if (cancelled) return;
          setPreview({ minor: parsed.amount_minor, display: parsed.amount_display });
          setError(null);
        })
        .catch((err: ApiError) => {
          if (cancelled) return;
          setPreview(null);
          setError(err.message);
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [text, currency]);

  return { preview, error };
}

function AmountInput({
  value,
  onChange,
  currency,
  autoFocus,
}: {
  value: string;
  onChange: (next: string) => void;
  currency: string;
  autoFocus?: boolean;
}) {
  const { preview, error } = useAmountPreview(value, currency);
  return (
    <>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="40k, 1.5 lakh, 40000"
        autoFocus={autoFocus}
      />
      <span className={`amount-preview ${error ? "bad" : ""}`}>
        {error ? error : preview ? `= ${preview.display}` : " "}
      </span>
    </>
  );
}

// --- new client -------------------------------------------------------------

export function NewClientForm({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.createClient({
        name: name.trim(),
        email: email.trim() || null,
        phone: phone.trim() || null,
        address: address.trim() || null,
      });
      if (result.status === "already_exists") {
        setError(`${result.client.name} is already on file — nothing was duplicated.`);
        setBusy(false);
        return;
      }
      onDone();
      onClose();
    } catch (err) {
      setError((err as ApiError).message);
      setBusy(false);
    }
  }

  return (
    <Modal title="New client" onClose={onClose}>
      <form onSubmit={submit}>
        <FormError message={error} />
        <Field label="Name" hint="Duplicate names are detected, not created twice.">
          <input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="Email">
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
        </Field>
        <Field label="Phone">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </Field>
        <Field label="Billing address" hint="Printed on their invoices.">
          <textarea
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            rows={2}
          />
        </Field>
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={!name.trim() || busy}>
            {busy ? "Saving…" : "Add client"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- new invoice ------------------------------------------------------------

export function NewInvoiceForm({
  clients,
  presetClientId,
  onClose,
  onDone,
}: {
  clients: Client[];
  presetClientId?: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const [clientId, setClientId] = useState<number | "">(
    presetClientId ?? clients[0]?.client_id ?? "",
  );
  const [project, setProject] = useState("");
  const [amountText, setAmountText] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [issueDate, setIssueDate] = useState(todayISO());
  const [dueDate, setDueDate] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent, allowDuplicate = false) {
    event.preventDefault();
    if (!clientId || !project.trim() || !amountText.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const parsed = await api.parseAmount(amountText.trim(), currency);
      await api.createInvoice({
        client_id: Number(clientId),
        project: project.trim(),
        amount_minor: parsed.amount_minor,
        currency: parsed.currency,
        issue_date: issueDate || null,
        due_date: dueDate || null,
        description: description.trim() || null,
        allow_duplicate: allowDuplicate,
      });
      onDone();
      onClose();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message);
      // The tool suspects a duplicate; offer to confirm rather than silently retry.
      setDuplicate(apiError.code === "duplicate_suspected");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="New invoice"
      subtitle="The invoice number is assigned by the database."
      onClose={onClose}
    >
      <form onSubmit={(e) => submit(e)}>
        <FormError message={error} />
        {duplicate ? (
          <div className="form-confirm">
            An identical invoice already exists for this client today.
            <button
              type="button"
              className="btn"
              onClick={(e) => submit(e as unknown as React.FormEvent, true)}
              disabled={busy}
            >
              Create it anyway
            </button>
          </div>
        ) : null}

        <Field label="Client">
          <select
            value={clientId}
            onChange={(e) => setClientId(Number(e.target.value))}
          >
            {clients.length === 0 ? <option value="">No clients yet</option> : null}
            {clients.map((client) => (
              <option key={client.client_id} value={client.client_id}>
                {client.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Project">
          <input
            value={project}
            onChange={(e) => setProject(e.target.value)}
            placeholder="Website development"
          />
        </Field>

        <div className="field-row">
          <Field label="Amount">
            <AmountInput
              value={amountText}
              onChange={setAmountText}
              currency={currency}
            />
          </Field>
          <Field label="Currency">
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {["INR", "USD", "EUR", "GBP", "AED", "JPY"].map((code) => (
                <option key={code}>{code}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="field-row">
          <Field label="Issue date">
            <input
              type="date"
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
            />
          </Field>
          <Field label="Due date" hint="Optional, but overdue needs one.">
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </Field>
        </div>

        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </Field>

        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn primary"
            disabled={!clientId || !project.trim() || !amountText.trim() || busy}
          >
            {busy ? "Creating…" : "Create invoice"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- record payment ---------------------------------------------------------

export function RecordPaymentForm({
  invoice,
  onClose,
  onDone,
}: {
  invoice: Invoice;
  onClose: () => void;
  onDone: () => void;
}) {
  const [amountText, setAmountText] = useState("");
  const [paymentDate, setPaymentDate] = useState(todayISO());
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent, allowDuplicate = false) {
    event.preventDefault();
    if (!amountText.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const parsed = await api.parseAmount(amountText.trim(), invoice.currency);
      await api.recordPayment({
        invoice_id: invoice.invoice_id,
        amount_minor: parsed.amount_minor,
        payment_date: paymentDate || null,
        method: method.trim() || null,
        reference: reference.trim() || null,
        allow_duplicate: allowDuplicate,
      });
      onDone();
      onClose();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message);
      setDuplicate(apiError.code === "duplicate_suspected");
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Record payment — ${invoice.invoice_number}`}
      subtitle={`${invoice.client_name} · ${invoice.outstanding_display} outstanding`}
      onClose={onClose}
    >
      <form onSubmit={(e) => submit(e)}>
        <FormError message={error} />
        {duplicate ? (
          <div className="form-confirm">
            An identical payment is already recorded on that date.
            <button
              type="button"
              className="btn"
              onClick={(e) => submit(e as unknown as React.FormEvent, true)}
              disabled={busy}
            >
              Record it anyway
            </button>
          </div>
        ) : null}

        <Field
          label="Amount received"
          hint={`More than ${invoice.outstanding_display} will be refused.`}
        >
          <AmountInput
            value={amountText}
            onChange={setAmountText}
            currency={invoice.currency}
            autoFocus
          />
        </Field>

        <button
          type="button"
          className="btn subtle"
          onClick={() => setAmountText(String(invoice.outstanding_minor / 100))}
        >
          Pay the full {invoice.outstanding_display}
        </button>

        <div className="field-row">
          <Field label="Date">
            <input
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
            />
          </Field>
          <Field label="Method">
            <input
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              placeholder="UPI, bank transfer"
            />
          </Field>
        </div>

        <Field label="Reference" hint="Transaction id or cheque number.">
          <input value={reference} onChange={(e) => setReference(e.target.value)} />
        </Field>

        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={!amountText.trim() || busy}>
            {busy ? "Recording…" : "Record payment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
