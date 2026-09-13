import React from 'react';
import { api } from '../../lib/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { IconDownload } from '../Icons';

/**
 * Shows the document the server rendered — the same PDF the client receives.
 *
 * It deliberately does not redraw an invoice in HTML: a second rendering is a
 * second place for a figure, a date or a tax detail to differ from the file
 * that actually goes out.
 */
export type ViewedDocument =
  | { type: 'invoice'; invoiceId: number; number: string; clientName: string }
  | { type: 'receipt'; paymentId: number; number: string | null; clientName: string }
  | null;

type DocumentViewerModalProps = {
  document: ViewedDocument;
  onClose: () => void;
};

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({ document, onClose }) => {
  if (!document) return null;

  const isInvoice = document.type === 'invoice';
  const url = isInvoice ? api.invoicePdfUrl(document.invoiceId) : api.receiptPdfUrl(document.paymentId);
  const title = isInvoice
    ? `Invoice ${document.number}`
    : document.number
      ? `Receipt ${document.number}`
      : 'Receipt';

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={title}
      subtitle={
        isInvoice
          ? `Issued to ${document.clientName}`
          : document.number
            ? `Payment from ${document.clientName}`
            : `Payment from ${document.clientName} · a receipt number is issued when this opens`
      }
      maxWidth={760}
    >
      <div className="space-y-3">
        <div
          className="rounded-[6px] border overflow-hidden"
          style={{ borderColor: 'var(--line)', backgroundColor: 'var(--surface-sunken)' }}
        >
          <iframe
            title={title}
            src={url}
            className="w-full block"
            style={{ height: 'min(68vh, 720px)', border: 0 }}
          />
        </div>

        <div className="flex items-center justify-between gap-2">
          <span className="text-[12px]" style={{ color: 'var(--ink-faint)' }}>
            Rendered by the server from the ledger.
          </span>
          <div className="flex gap-2">
            <Button variant="default" onClick={onClose}>
              Close
            </Button>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-[6px] px-3 py-[6px] text-[13px] font-[550] transition-standard"
              style={{ backgroundColor: 'var(--accent)', color: '#fff', boxShadow: 'var(--shadow-sm)' }}
            >
              <IconDownload size={15} />
              Open PDF
            </a>
          </div>
        </div>
      </div>
    </Modal>
  );
};
