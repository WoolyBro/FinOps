"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type AgentStatus } from "@/lib/api";

/** Line icons at 15px, matching the weight of the nav label beside them. */
const icons = {
  overview: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1.75" y="1.75" width="5" height="5" rx="1.25" />
      <rect x="9.25" y="1.75" width="5" height="5" rx="1.25" />
      <rect x="1.75" y="9.25" width="5" height="5" rx="1.25" />
      <rect x="9.25" y="9.25" width="5" height="5" rx="1.25" />
    </svg>
  ),
  agent: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h9A1.5 1.5 0 0 1 14 4.5v6a1.5 1.5 0 0 1-1.5 1.5H6l-3 2.5V12h-.5A1.5 1.5 0 0 1 2 10.5z" />
    </svg>
  ),
  invoices: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3.5 1.75h9v12.5l-2-1.25-2 1.25-2-1.25-2 1.25z" />
      <path d="M6 5.5h4M6 8.25h4" strokeLinecap="round" />
    </svg>
  ),
  clients: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="5.5" r="2.75" />
      <path d="M2.75 13.75a5.25 5.25 0 0 1 10.5 0" />
    </svg>
  ),
  payments: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1.75" y="3.25" width="12.5" height="9.5" rx="1.5" />
      <path d="M1.75 6.75h12.5" />
    </svg>
  ),
  overdue: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 4.75V8l2.25 1.5" strokeLinecap="round" />
    </svg>
  ),
  reminders: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 6.5a4 4 0 1 1 8 0c0 3 1.25 4 1.25 4H2.75S4 9.5 4 6.5" />
      <path d="M6.5 13a1.6 1.6 0 0 0 3 0" strokeLinecap="round" />
    </svg>
  ),
  reports: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2.25 13.75h11.5" strokeLinecap="round" />
      <rect x="3.25" y="8" width="2.5" height="4" rx="0.75" />
      <rect x="6.75" y="5" width="2.5" height="7" rx="0.75" />
      <rect x="10.25" y="2.5" width="2.5" height="9.5" rx="0.75" />
    </svg>
  ),
};

/** Grouped so the nav reads as the shape of the work, not a flat list. */
const GROUPS = [
  {
    label: null,
    links: [
      { href: "/", label: "Overview", icon: icons.overview },
      { href: "/agent", label: "Agent", icon: icons.agent },
    ],
  },
  {
    label: "Billing",
    links: [
      { href: "/invoices", label: "Invoices", icon: icons.invoices },
      { href: "/clients", label: "Clients", icon: icons.clients },
      { href: "/payments", label: "Payments", icon: icons.payments },
    ],
  },
  {
    label: "Collections",
    links: [
      { href: "/overdue", label: "Overdue", icon: icons.overdue },
      { href: "/reminders", label: "Reminders", icon: icons.reminders },
    ],
  },
  {
    label: "Insights",
    links: [{ href: "/reports", label: "Reports", icon: icons.reports }],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    api
      .agentStatus()
      .then(setStatus)
      .catch(() => setUnreachable(true));
  }, []);

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          F
        </span>
        <span className="brand-name">
          FreelanceFlow
          <small>Billing operations</small>
        </span>
      </div>

      <nav className="nav">
        {GROUPS.map((group, index) => (
          <div key={group.label ?? index} className="nav-group">
            {group.label ? (
              <div className="nav-label">{group.label}</div>
            ) : null}
            {group.links.map((link) => {
              // A detail page keeps its section highlighted.
              const active =
                pathname === link.href ||
                (link.href !== "/" && pathname.startsWith(`${link.href}/`));
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={active ? "active" : ""}
                  aria-current={active ? "page" : undefined}
                >
                  {link.icon}
                  {link.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="provider-badge">
        {unreachable ? (
          <>
            <strong>
              <span className="dot off" />
              API unreachable
            </strong>
            Start the backend on port 8000.
          </>
        ) : status === null ? (
          <>
            <span className="dot off" />
            Checking model…
          </>
        ) : status.available ? (
          <>
            <strong>
              <span className="dot on" />
              Agent ready
            </strong>
            {status.provider} · {status.model_id}
          </>
        ) : (
          <>
            <strong>
              <span className="dot off" />
              Agent not configured
            </strong>
            Invoices and payments work as normal.
          </>
        )}
      </div>
    </aside>
  );
}
