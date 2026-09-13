import React, { useState } from 'react';
import { api } from '../../lib/api';
import { ApiError, Client } from '../../types';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

type AddClientModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onClientAdded: (client: Client) => void;
};

export const AddClientModal: React.FC<AddClientModalProps> = ({ isOpen, onClose, onClientAdded }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  // The server keeps one client per name (case- and space-insensitive), so a
  // match is offered for use rather than duplicated.
  const [existing, setExisting] = useState<{ client: Client; message: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const reset = () => {
    setName('');
    setEmail('');
    setPhone('');
    setAddress('');
    setExisting(null);
    setFormError(null);
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;

    setIsSubmitting(true);
    setFormError(null);
    try {
      const client = await api.postClient({
        name: name.trim(),
        email: email.trim() || null,
        phone: phone.trim() || null,
        address: address.trim() || null,
      });
      onClientAdded(client);
      onClose();
      reset();
    } catch (err) {
      const failure = err as ApiError;
      if (failure.error === 'already_exists' && failure.result?.client) {
        setExisting({ client: failure.result.client as Client, message: failure.detail });
      } else {
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
      title="Add new client"
      subtitle="Register an individual or company for billing"
      maxWidth={480}
    >
      <div className="space-y-4 text-[13.5px]">
        {formError && (
          <div
            role="alert"
            className="p-3 rounded-[6px] border text-[13px]"
            style={{ backgroundColor: 'var(--bad-bg)', borderColor: 'var(--bad-line)', color: 'var(--bad-ink)' }}
          >
            {formError}
          </div>
        )}

        {existing && (
          <div
            role="alert"
            className="p-3 rounded-[6px] border text-[13px] leading-relaxed"
            style={{ backgroundColor: 'var(--warn-bg)', borderColor: 'var(--warn-line)', color: 'var(--warn-ink)' }}
          >
            <div className="font-[600] mb-1">Already a client</div>
            <div className="mb-3">
              {existing.message} Each name is kept once, so invoices and payments never split across two
              records for the same person.
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="default" onClick={() => setExisting(null)}>
                Edit the name
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => {
                  onClientAdded(existing.client);
                  onClose();
                  reset();
                }}
              >
                Use existing
              </Button>
            </div>
          </div>
        )}

        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Client or company name <span style={{ color: 'var(--bad-ink)' }}>*</span>
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
            placeholder="e.g. Rahul Sharma or NexBuild Tech Pvt Ltd"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Email address
          </label>
          <input
            type="email"
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="e.g. accounts@nexbuild.in"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Phone number
          </label>
          <input
            type="text"
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="e.g. +91 98200 41122"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>

        <div>
          <label className="block font-[550] mb-1" style={{ color: 'var(--ink)' }}>
            Billing address
          </label>
          <textarea
            rows={2}
            className="w-full px-3 py-2 border rounded-[6px] transition-standard focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{
              borderColor: 'var(--line-strong)',
              backgroundColor: 'var(--surface)',
              color: 'var(--ink-strong)',
            }}
            placeholder="Office address, city, pin code…"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t" style={{ borderColor: 'var(--line)' }}>
          <Button type="button" variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            disabled={!name.trim()}
            busy={isSubmitting}
            busyText="Adding client…"
            onClick={handleSubmit}
          >
            Add client
          </Button>
        </div>
      </div>
    </Modal>
  );
};
