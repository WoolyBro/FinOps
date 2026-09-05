"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type AgentStatus } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/agent", label: "Agent" },
  { href: "/invoices", label: "Invoices" },
  { href: "/clients", label: "Clients" },
  { href: "/payments", label: "Payments" },
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
        FreelanceFlow
        <small>Billing operations</small>
      </div>

      <nav className="nav">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={pathname === link.href ? "active" : ""}
          >
            {link.label}
          </Link>
        ))}
      </nav>

      <div className="provider-badge">
        {unreachable ? (
          <>
            <span className="dot off" />
            API unreachable
          </>
        ) : status === null ? (
          <>
            <span className="dot off" />
            Checking model…
          </>
        ) : status.available ? (
          <>
            <span className="dot on" />
            Agent ready
            <br />
            <span style={{ opacity: 0.8 }}>
              {status.provider} · {status.model_id}
            </span>
          </>
        ) : (
          <>
            <span className="dot off" />
            Agent not configured
            <br />
            <span style={{ opacity: 0.8 }}>Records remain readable</span>
          </>
        )}
      </div>
    </aside>
  );
}
