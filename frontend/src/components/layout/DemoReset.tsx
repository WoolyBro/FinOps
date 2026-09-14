import React, { createContext, useContext, useState } from 'react';
import { api } from '../../lib/api';
import { ApiError } from '../../types';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { IconReset } from '../Icons';

/**
 * "Reset demo data": restores this browser's private copy of the sample
 * ledger. The button sits in every page heading; the confirmation and the
 * reset itself live once, in the app shell, which also clears the agent's
 * conversation and reloads whatever page is open.
 */
const DemoResetContext = createContext<(() => void) | null>(null);

export const ResetDemoButton: React.FC = () => {
  const open = useContext(DemoResetContext);
  if (!open) return null;
  return (
    <Button
      variant="default"
      icon={<IconReset size={14} />}
      onClick={open}
      title="Restore the sample data. Only this browser's copy is affected."
    >
      Reset demo data
    </Button>
  );
};

type ProviderProps = {
  /** Called after the server has restored the data, to reload the app state. */
  onReset: () => void;
  onError: (message: string) => void;
  children: React.ReactNode;
};

export const DemoResetProvider: React.FC<ProviderProps> = ({ onReset, onError, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setBusy(true);
    try {
      await api.resetSandbox();
      setIsOpen(false);
      onReset();
    } catch (err) {
      onError((err as ApiError).detail ?? 'The demo data could not be reset.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <DemoResetContext.Provider value={() => setIsOpen(true)}>
      {children}
      <Modal
        isOpen={isOpen}
        onClose={() => !busy && setIsOpen(false)}
        title="Reset demo data?"
        subtitle="Only the copy in this browser is reset. Nobody else's data changes."
        maxWidth={440}
      >
        <div className="space-y-4 text-[13.5px] leading-relaxed" style={{ color: 'var(--ink-body)' }}>
          <p className="m-0">
            Every client, invoice, payment and reminder goes back to the sample ledger, including
            Rahul Sharma's invoice FF-0005, unpaid again. Documents generated since are removed and
            the agent's conversation is cleared.
          </p>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="default" onClick={() => setIsOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirm} busy={busy} busyText="Resetting…">
              Reset demo data
            </Button>
          </div>
        </div>
      </Modal>
    </DemoResetContext.Provider>
  );
};
