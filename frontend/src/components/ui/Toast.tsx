import React, { createContext, useContext, useState, useCallback, useRef, useLayoutEffect } from 'react';

type ToastItem = {
  id: string;
  text: string;
  isExiting?: boolean;
};

type ToastContextType = {
  addToast: (text: string) => void;
};

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastDomMap = useRef<Map<string, HTMLDivElement>>(new Map());
  const prevPositions = useRef<Map<string, number>>(new Map());

  // FLIP layout effect: smooth transform shift for remaining toasts when one leaves
  useLayoutEffect(() => {
    toastDomMap.current.forEach((el, id) => {
      const oldTop = prevPositions.current.get(id);
      if (oldTop !== undefined && el) {
        const newTop = el.getBoundingClientRect().top;
        const deltaY = oldTop - newTop;
        if (Math.abs(deltaY) > 0.5) {
          el.style.transform = `translateY(${deltaY}px)`;
          el.style.transition = 'none';
          // Force reflow
          void el.offsetHeight;
          el.style.transition = 'transform var(--dur-base) var(--ease-move)';
          el.style.transform = 'translateY(0)';
        }
      }
    });

    // Record new positions
    const newPositions = new Map<string, number>();
    toastDomMap.current.forEach((el, id) => {
      if (el) {
        newPositions.set(id, el.getBoundingClientRect().top);
      }
    });
    prevPositions.current = newPositions;
  }, [toasts]);

  const addToast = useCallback((text: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, text, isExiting: false }]);

    // Start exit after 2800ms
    setTimeout(() => {
      setToasts((prev) =>
        prev.map((t) => (t.id === id ? { ...t, isExiting: true } : t))
      );

      // Remove after exit duration (--dur-fast: 140ms)
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        toastDomMap.current.delete(id);
        prevPositions.current.delete(id);
      }, 140);
    }, 2800);
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none"
        style={{ maxWidth: '380px' }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            ref={(el) => {
              if (el) {
                toastDomMap.current.set(toast.id, el);
              } else {
                toastDomMap.current.delete(toast.id);
              }
            }}
            className={`pointer-events-auto rounded-[6px] border px-4 py-3 text-[13.5px] font-[500] ${
              toast.isExiting ? 'toast-exit' : 'toast-enter'
            }`}
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--line)',
              color: 'var(--ink-strong)',
              boxShadow: 'var(--shadow-md)',
            }}
          >
            {toast.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextType => {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
};
