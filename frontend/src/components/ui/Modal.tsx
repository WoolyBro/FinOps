import React, { useEffect, useRef, useState, useCallback } from 'react';
import { IconCross } from '../Icons';

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: number;
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  maxWidth = 480,
}) => {
  // One state, three phases. The previous version kept two booleans and a
  // timer inside an effect that depended on one of them: starting the exit
  // re-ran the effect, whose cleanup cancelled the unmount timer, leaving an
  // invisible full-screen backdrop that swallowed every click in the app.
  const [phase, setPhase] = useState<'open' | 'exiting' | 'closed'>(isOpen ? 'open' : 'closed');
  const modalRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  // The parent owns open/closed; this only animates the transition.
  useEffect(() => {
    setPhase((current) => (isOpen ? 'open' : current === 'closed' ? 'closed' : 'exiting'));
  }, [isOpen]);

  useEffect(() => {
    if (phase !== 'exiting') return;
    const timer = window.setTimeout(() => setPhase('closed'), 140); // --dur-fast
    return () => window.clearTimeout(timer);
  }, [phase]);

  const isRendered = phase !== 'closed';
  const isExiting = phase === 'exiting';

  // Every close — Escape, backdrop, the X — asks the parent; the exit
  // animation then runs off the isOpen change like any other close.
  const handleStartClose = useCallback(() => {
    if (phase === 'open') onClose();
  }, [phase, onClose]);

  useEffect(() => {
    if (phase === 'open') {
      triggerRef.current = document.activeElement;
      document.body.style.overflow = 'hidden';

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          handleStartClose();
        }
      };
      window.addEventListener('keydown', handleKeyDown);

      // Focus first input or button in modal
      const timer = setTimeout(() => {
        if (modalRef.current) {
          const focusable = modalRef.current.querySelector<HTMLElement>(
            'input, button, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusable) focusable.focus();
        }
      }, 50);

      return () => {
        clearTimeout(timer);
        window.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = '';
        if (triggerRef.current && (triggerRef.current as HTMLElement).focus) {
          (triggerRef.current as HTMLElement).focus();
        }
      };
    }
  }, [phase, handleStartClose]);

  if (!isRendered) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${
        isExiting ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      // While fading out, clicks must reach the page underneath.
      style={{ backgroundColor: 'rgba(10, 37, 64, 0.28)', pointerEvents: isExiting ? 'none' : undefined }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          handleStartClose();
        }
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={modalRef}
        className={`w-full rounded-[8px] border overflow-hidden ${
          isExiting ? 'modal-panel-exit' : 'modal-panel-enter'
        }`}
        style={{
          maxWidth: `${maxWidth}px`,
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--line)',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        <div
          className="flex items-start justify-between border-b"
          style={{ padding: '16px 20px', borderColor: 'var(--line)' }}
        >
          <div>
            <h2
              className="text-[16px] font-[600] leading-snug"
              style={{ color: 'var(--ink)' }}
            >
              {title}
            </h2>
            {subtitle && (
              <p
                className="text-[13px] mt-1"
                style={{ color: 'var(--ink-muted)' }}
              >
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={handleStartClose}
            aria-label="Close dialog"
            className="p-1 rounded-[6px] transition-standard hover:bg-[var(--surface-sunken)]"
            style={{ color: 'var(--ink-muted)' }}
          >
            <IconCross size={16} />
          </button>
        </div>
        <div className="p-[20px] max-h-[85vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  );
};
