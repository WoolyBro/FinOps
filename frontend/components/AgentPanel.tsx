"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  api,
  type AgentStatus,
  type ToolCall,
} from "@/lib/api";

type Message =
  | { role: "user"; text: string }
  | { role: "agent"; text: string; toolCalls: ToolCall[]; seconds: number }
  | { role: "error"; text: string };

const SUGGESTIONS = [
  "Who owes me money?",
  "Which invoices are overdue?",
  "How much have I made this month?",
  "Create a ₹40,000 website invoice for Rahul, due 15 September 2026.",
];

/**
 * The agent panel.
 *
 * When no model is configured this shows the configuration state and disables
 * the composer. It never produces a reply of its own -- an answer on this page
 * always came from a model that actually ran.
 */
export function AgentPanel({ onStateChange }: { onStateChange?: () => void }) {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [statusError, setStatusError] = useState<ApiError | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .agentStatus()
      .then(setStatus)
      .catch((err) => setStatusError(err as ApiError));
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, busy]);

  const available = status?.available === true;
  const canSend = available && !busy && draft.trim().length > 0;

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy || !available) return;

    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setDraft("");
    setBusy(true);

    try {
      const result = await api.chat(message, sessionId);
      setSessionId(result.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: result.reply,
          toolCalls: result.tool_calls,
          seconds: result.elapsed_seconds,
        },
      ]);
      // A turn may have changed invoices or payments; let the page refresh.
      if (result.tool_calls.length > 0) onStateChange?.();
    } catch (err) {
      const apiError = err as ApiError;
      setMessages((prev) => [
        ...prev,
        {
          role: "error",
          text:
            apiError.code === "agent_unavailable"
              ? "The agent is not configured, so nothing was run."
              : apiError.message,
        },
      ]);
      if (apiError.code === "agent_unavailable") {
        api.agentStatus().then(setStatus).catch(() => undefined);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel chat">
      <div className="panel-head">
        <h2>Agent</h2>
        <span className="hint">
          {available
            ? `${status?.provider} · ${status?.model_id}`
            : "not configured"}
        </span>
      </div>

      {statusError ? (
        <div className="panel-body">
          <div className="notice error">
            <h3>Cannot reach the API</h3>
            <div>{statusError.message}</div>
            <pre>uvicorn app.api.main:app --reload --port 8000</pre>
          </div>
        </div>
      ) : status && !available ? (
        <div className="panel-body">
          <div className="notice warn">
            <h3>The agent is not configured</h3>
            <div>
              No model provider is reachable, so the chat is disabled rather
              than answering with something no model produced. Your invoices,
              payments and reports below are unaffected.
            </div>
            {status.detail ? <pre>{status.detail}</pre> : null}
          </div>
        </div>
      ) : null}

      <div className="chat-log" ref={logRef}>
        {messages.length === 0 && available ? (
          <div className="empty">
            Tell the agent what happened, in your own words.
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} disabled={!available}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((message, index) => (
          <div key={index} className={`msg ${message.role}`}>
            <div className="bubble">{message.text}</div>
            {message.role === "agent" && message.toolCalls.length > 0 ? (
              <ToolTrace calls={message.toolCalls} seconds={message.seconds} />
            ) : null}
          </div>
        ))}

        {busy ? (
          <div className="msg agent">
            <div className="bubble faint">Working…</div>
          </div>
        ) : null}
      </div>

      <div className="composer">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) send(draft);
            }
          }}
          placeholder={
            available
              ? "Rahul paid me ₹15,000 today for the website project."
              : "Configure a model provider to use the agent."
          }
          disabled={!available || busy}
          rows={2}
        />
        <button
          className="btn primary"
          onClick={() => send(draft)}
          disabled={!canSend}
        >
          Send
        </button>
      </div>
    </div>
  );
}

/**
 * What the agent actually did. Shown because a billing answer you cannot audit
 * is not worth much -- the tool names and their results are the evidence.
 */
function ToolTrace({
  calls,
  seconds,
}: {
  calls: ToolCall[];
  seconds: number;
}) {
  return (
    <div className="tool-trace">
      <div className="trace-title">
        {calls.length} tool {calls.length === 1 ? "call" : "calls"} ·{" "}
        {seconds.toFixed(1)}s
      </div>
      <ol>
        {calls.map((call, index) => {
          const bad =
            call.error !== null ||
            (call.status !== null &&
              ["error", "not_found"].includes(call.status));
          return (
            <li key={index}>
              <code>{call.tool}</code>{" "}
              <span className={`trace-status ${bad ? "bad" : ""}`}>
                {call.error ?? call.status ?? "ok"}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
