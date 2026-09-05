"use client";

import { AgentPanel } from "@/components/AgentPanel";

export default function AgentPage() {
  return (
    <>
      <h1 className="page-title">Agent</h1>
      <p className="page-sub">
        Tell it what happened. It uses the same tools the dashboard reads from,
        so anything it records shows up in your invoices and payments
        immediately.
      </p>
      <div className="agent-layout">
        <AgentPanel />
      </div>
    </>
  );
}
