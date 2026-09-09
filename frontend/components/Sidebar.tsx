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
};

const LINKS = [
  { href: "/", label: "Overview", icon: icons.overview },
  { href: "/agent", label: "Agent", icon: icons.agent },
  { href: "/invoices", label: "Invoices", icon: icons.invoices },
  { href: "/clients", label: "Clients", icon: icons.clients },
  { href: "/payments", label: "Payments", icon: icons.payments },
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
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={pathname === link.href ? "active" : ""}
            aria-current={pathname === link.href ? "page" : undefined}
          >
            {link.icon}
            {link.label}
          </Link>
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
