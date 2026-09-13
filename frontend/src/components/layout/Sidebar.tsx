import React, { useRef, useState, useLayoutEffect, useEffect } from 'react';
import {
  IconOverview,
  IconAgent,
  IconInvoices,
  IconClients,
  IconPayments,
  IconOverdue,
  IconReminders,
  IconReports,
} from '../Icons';
import { AgentStatus } from '../../types';

type SidebarProps = {
  currentPath: string;
  onNavigate: (path: string) => void;
  /** Null while the first status check is in flight. */
  agentStatus: AgentStatus | null;
  /** False when the API itself could not be reached. */
  backendOnline: boolean;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
};

/**
 * Bedrock ids carry a region and vendor prefix: "apac.amazon.nova-pro-v1:0"
 * reads as "nova-pro". Other providers' names are shown as they are — a local
 * model like "llama3.1" has a dot that is part of its name.
 */
function shortModel(provider: string | null, modelId: string | null): string {
  if (!modelId) return '';
  if (provider !== 'bedrock') return modelId;
  const tail = modelId.split('.').pop() ?? modelId;
  return tail.replace(/-v\d+(:\d+)?$/, '').replace(/:\d+$/, '');
}

const PROVIDER_NAMES: Record<string, string> = {
  bedrock: 'Amazon Bedrock',
  gemini: 'Google Gemini',
  ollama: 'Ollama (local)',
};

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath,
  onNavigate,
  agentStatus,
  backendOnline,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  const navRef = useRef<HTMLElement>(null);
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicatorTop, setIndicatorTop] = useState<number | null>(null);
  const [indicatorHeight, setIndicatorHeight] = useState<number>(34);
  const [isMoving, setIsMoving] = useState(false);
  const isInitialMount = useRef(true);
  const moveTimerRef = useRef<number | null>(null);

  // Navigation structure
  const navGroups = [
    {
      label: null,
      items: [
        { path: '/', label: 'Overview', icon: <IconOverview size={16} /> },
        { path: '/agent', label: 'Agent', icon: <IconAgent size={16} /> },
      ],
    },
    {
      label: 'Billing',
      items: [
        { path: '/invoices', label: 'Invoices', icon: <IconInvoices size={16} /> },
        { path: '/clients', label: 'Clients', icon: <IconClients size={16} /> },
        { path: '/payments', label: 'Payments', icon: <IconPayments size={16} /> },
      ],
    },
    {
      label: 'Collections',
      items: [
        { path: '/overdue', label: 'Overdue', icon: <IconOverdue size={16} /> },
        { path: '/reminders', label: 'Reminders', icon: <IconReminders size={16} /> },
      ],
    },
    {
      label: 'Insights',
      items: [
        { path: '/reports', label: 'Reports', icon: <IconReports size={16} /> },
      ],
    },
  ];

  // Helper to test if a path is active, including detail pages
  const isItemActive = (path: string) => {
    if (path === '/') return currentPath === '/';
    if (path === '/invoices') return currentPath.startsWith('/invoices');
    if (path === '/clients') return currentPath.startsWith('/clients');
    return currentPath === path;
  };

  // Find the currently active item's path
  const allItems = navGroups.flatMap((g) => g.items);
  const activeItem = allItems.find((item) => isItemActive(item.path));
  const activePath = activeItem?.path;

  // Update sliding indicator position
  useLayoutEffect(() => {
    if (!activePath) return;
    const el = itemRefs.current[activePath];
    const nav = navRef.current;
    if (el && nav) {
      const navRect = nav.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      const top = elRect.top - navRect.top + nav.scrollTop;
      const height = elRect.height;

      if (isInitialMount.current) {
        setIndicatorTop(top);
        setIndicatorHeight(height);
        isInitialMount.current = false;
      } else {
        setIsMoving(true);
        setIndicatorTop(top);
        setIndicatorHeight(height);

        if (moveTimerRef.current) window.clearTimeout(moveTimerRef.current);
        moveTimerRef.current = window.setTimeout(() => {
          setIsMoving(false);
        }, 220); // remove will-change after --dur-base (200ms) completes
      }
    }
  }, [activePath]);

  useEffect(() => {
    return () => {
      if (moveTimerRef.current) window.clearTimeout(moveTimerRef.current);
    };
  }, []);

  const handleLinkClick = (path: string) => {
    onNavigate(path);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-[rgba(10,37,64,0.28)] lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col w-[232px] border-r transition-standard lg:static lg:translate-x-0 ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--line)',
          height: '100vh',
        }}
      >
        {/* Brand Section */}
        <div
          className="flex items-center gap-3 px-4 pt-5 pb-4 cursor-pointer"
          onClick={() => handleLinkClick('/')}
        >
          <div
            className="flex items-center justify-center w-[28px] h-[28px] rounded-[7px] text-white font-[700] text-[15px] select-none shrink-0"
            style={{
              background: 'linear-gradient(160deg, #635bff, #4b45c6)',
            }}
          >
            F
          </div>
          <div className="flex flex-col">
            <span
              className="text-[14.5px] font-[600] leading-none tracking-[-0.01em]"
              style={{ color: 'var(--ink)' }}
            >
              FreelanceFlow
            </span>
            <span
              className="text-[11.5px] font-[400] mt-1 leading-none"
              style={{ color: 'var(--ink-faint)' }}
            >
              Billing operations
            </span>
          </div>
        </div>

        {/* Grouped Navigation */}
        <nav ref={navRef} className="relative flex-1 px-3 py-2 space-y-4 overflow-y-auto">
          {/* Sliding 2px accent indicator on the left edge */}
          {indicatorTop !== null && (
            <div
              aria-hidden="true"
              className="absolute left-0 w-[2px] rounded-r-[1px] pointer-events-none"
              style={{
                backgroundColor: 'var(--accent)',
                height: `${indicatorHeight}px`,
                transform: `translateY(${indicatorTop}px)`,
                transition: isInitialMount.current
                  ? 'none'
                  : 'transform var(--dur-base) var(--ease-move), height var(--dur-base) var(--ease-move)',
                willChange: isMoving ? 'transform' : 'auto',
                zIndex: 10,
              }}
            />
          )}

          {navGroups.map((group, gIdx) => (
            <div key={gIdx} className="space-y-1">
              {group.label && (
                <div
                  className="px-2 pb-1 text-[11px] font-[600] uppercase tracking-[0.06em] select-none"
                  style={{ color: 'var(--ink-faint)' }}
                >
                  {group.label}
                </div>
              )}
              {group.items.map((item) => {
                const active = isItemActive(item.path);
                return (
                  <button
                    key={item.path}
                    ref={(el) => {
                      itemRefs.current[item.path] = el;
                    }}
                    type="button"
                    aria-current={active ? 'page' : undefined}
                    onClick={() => handleLinkClick(item.path)}
                    className="w-full flex items-center gap-2.5 text-[13.5px] rounded-[6px] text-left"
                    style={{
                      padding: '7px 8px',
                      fontWeight: active ? 600 : 500,
                      backgroundColor: active
                        ? 'var(--accent-wash)'
                        : 'transparent',
                      color: active ? 'var(--accent-ink)' : 'var(--ink-body)',
                      transition: 'background-color var(--dur-fast) ease, color var(--dur-fast) ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        e.currentTarget.style.backgroundColor =
                          'var(--surface-sunken)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }
                    }}
                  >
                    <span
                      className="inline-flex items-center justify-center shrink-0"
                      style={{ opacity: active ? 1 : 0.75 }}
                    >
                      {item.icon}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Provider status, read from the API — never toggled or assumed. */}
        {(() => {
          const ready = backendOnline && !!agentStatus?.available;
          const heading = !backendOnline
            ? 'Backend offline'
            : agentStatus === null
              ? 'Checking agent…'
              : agentStatus.available
                ? 'Agent ready'
                : 'Agent unavailable';
          const detail = !backendOnline
            ? 'Could not reach the API on port 8000'
            : agentStatus === null
              ? ''
              : agentStatus.available
                ? [PROVIDER_NAMES[agentStatus.provider ?? ''] ?? agentStatus.provider, shortModel(agentStatus.provider, agentStatus.model_id)]
                    .filter(Boolean)
                    .join(' · ')
                : agentStatus.detail ?? 'No model provider is configured';
          return (
            <div
              className="mt-auto px-4 py-3 border-t select-none"
              style={{ borderColor: 'var(--line)' }}
              title={agentStatus?.model_id ?? undefined}
              aria-live="polite"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="inline-block w-[6px] h-[6px] rounded-full shrink-0"
                  style={{
                    backgroundColor: ready ? '#0e9f6e' : 'var(--ink-faint)',
                    boxShadow: ready
                      ? '0 0 0 2.5px rgba(14, 159, 110, 0.2)'
                      : '0 0 0 2.5px rgba(135, 146, 162, 0.2)',
                  }}
                />
                <span className="text-[12.5px] font-[600]" style={{ color: 'var(--ink)' }}>
                  {heading}
                </span>
              </div>
              {detail && (
                <div
                  className="text-[11.5px] leading-tight"
                  style={{ color: 'var(--ink-muted)', overflowWrap: 'anywhere' }}
                >
                  {detail}
                </div>
              )}
            </div>
          );
        })()}
      </aside>
    </>
  );
};
