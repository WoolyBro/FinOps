import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { AgentStatus, ApiError, ChatResultCard, Invoice, Payment, ToolCall } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { IconCheck, IconCross, IconDownload } from '../components/Icons';

/**
 * A conversation that shows its work.
 *
 * Everything on this page came back from POST /api/chat: the reply, the tool
 * calls in the order the agent made them, and the result card, which the
 * server builds from the tool's own result. Nothing is pre-seeded, simulated
 * while waiting, or invented when a call fails.
 */

type Turn = {
  id: string;
  userText: string;
  reply: string;
  toolCalls: ToolCall[];
  elapsedSeconds: number;
  resultCard: ChatResultCard | null;
  /** Set when the request itself failed — no agent turn happened. */
  failure?: ApiError;
};

// Tool statuses that mean "the tool declined", as opposed to succeeding.
// The agent reads these and should tell the user; so does the trace.
const REFUSALS = new Set([
  'error',
  'not_found',
  'duplicate_suspected',
  'ambiguous',
  'invalid_amount',
  'multiple_matches',
]);

// The conversation survives navigating away and back within this tab.
let saved: { sessionId: string | null; transcript: Turn[] } = { sessionId: null, transcript: [] };

/** Drop the remembered conversation, e.g. after the demo data is reset. */
export function forgetConversation() {
  saved = { sessionId: null, transcript: [] };
}

type AgentPageProps = {
  onNavigate: (path: string) => void;
  agentStatus: AgentStatus | null;
  backendOnline: boolean;
  prefilledQuery?: string;
  onClearPrefilled?: () => void;
  onViewInvoicePdf: (invoice: Invoice) => void;
  onViewReceiptPdf: (payment: Payment) => void;
  onLedgerChanged?: () => void;
};

const SUGGESTIONS = [
  'Rahul paid me ₹15,000 today',
  'Who owes me money?',
  'Create an invoice for Meera for 85k for the brand redesign',
  'Draft reminders for everything overdue',
];

export const AgentPage: React.FC<AgentPageProps> = ({
  onNavigate,
  agentStatus,
  backendOnline,
  prefilledQuery,
  onClearPrefilled,
  onViewInvoicePdf,
  onViewReceiptPdf,
  onLedgerChanged,
}) => {
  const [sessionId, setSessionId] = useState<string | null>(saved.sessionId);
  const [transcript, setTranscript] = useState<Turn[]>(saved.transcript);
  const [inputMessage, setInputMessage] = useState('');
  const [pending, setPending] = useState<{ text: string; startedAt: number } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [collapsedTraces, setCollapsedTraces] = useState<Record<string, boolean>>({});
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  const transcriptBottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const animatedTurns = useRef<Set<string>>(new Set(saved.transcript.map((t) => t.id)));

  const available = backendOnline && !!agentStatus?.available;

  useEffect(() => {
    saved = { sessionId, transcript };
    // Mark turns as seen after they have been committed with their entrance
    // animation, so a later re-render never replays it.
    const timer = window.setTimeout(() => {
      transcript.forEach((t) => animatedTurns.current.add(t.id));
    }, 600);
    return () => window.clearTimeout(timer);
  }, [sessionId, transcript]);

  // A live counter while waiting — a real measurement, not a fake progress bar.
  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(() => setElapsed((Date.now() - pending.startedAt) / 1000), 100);
    return () => window.clearInterval(timer);
  }, [pending]);

  // A query typed on the Overview page is sent once status is known.
  useEffect(() => {
    if (prefilledQuery && available && !pending) {
      handleSend(prefilledQuery);
      onClearPrefilled?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefilledQuery, available]);

  useEffect(() => {
    transcriptBottomRef.current?.scrollIntoView({ behavior: 'auto' });
  }, []);

  useEffect(() => {
    transcriptBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript, pending]);

  const handleSend = async (messageToSend?: string) => {
    const text = (messageToSend ?? inputMessage).trim();
    if (!text || pending || !available) return;

    setInputMessage('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setElapsed(0);
    setPending({ text, startedAt: Date.now() });

    const id = `turn-${Date.now()}`;
    try {
      const response = await api.postChat(text, sessionId);
      setSessionId(response.session_id);
      setTranscript((prev) => [
        ...prev,
        {
          id,
          userText: text,
          reply: response.reply,
          toolCalls: response.tool_calls,
          elapsedSeconds: response.elapsed_seconds,
          resultCard: response.result_card,
        },
      ]);
      if (response.result_card) onLedgerChanged?.();
    } catch (err) {
      const failure = err as ApiError;
      // A turn that failed mid-way still reports the operations that ran.
      const completed = (failure.result?.tool_calls as ToolCall[] | undefined) ?? [];
      setTranscript((prev) => [
        ...prev,
        {
          id,
          userText: text,
          reply: '',
          toolCalls: completed,
          elapsedSeconds: completed.reduce((sum, c) => sum + (c.duration_seconds ?? 0), 0),
          resultCard: null,
          failure,
        },
      ]);
      if (completed.length > 0) onLedgerChanged?.();
    } finally {
      setPending(null);
    }
  };

  const startNewConversation = async () => {
    if (sessionId) {
      // The server forgets the conversation; the ledger is untouched.
      await api.resetChat(sessionId).catch(() => undefined);
    }
    setSessionId(null);
    setTranscript([]);
    animatedTurns.current.clear();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputMessage(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden" style={{ height: '100dvh' }}>
      <div className="shrink-0 px-4 sm:px-8 pt-6 pb-2">
        <div className="max-w-[760px] mx-auto">
          <PageHeader
            title="Agent"
            actions={
              transcript.length > 0 ? (
                <Button variant="default" onClick={startNewConversation} disabled={!!pending}>
                  New conversation
                </Button>
              ) : undefined
            }
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 px-4 sm:px-8 pb-6" aria-live="polite">
        <div className="max-w-[760px] mx-auto space-y-6">
          {transcript.length === 0 && !pending && (
            <div className="pt-10 pb-4 text-center">
              <div className="text-[15px] font-[600]" style={{ color: 'var(--ink)' }}>
                Tell it what happened, in your own words.
              </div>
              <p className="mt-1.5 text-[13px] max-w-[46ch] mx-auto" style={{ color: 'var(--ink-muted)' }}>
                The agent looks things up and changes the ledger using the same operations as the rest
                of the app. Every operation it runs is listed under your message, with what it was
                given and what it got back.
              </p>
            </div>
          )}

          {transcript.map((turn) => {
            const isExpanded = !collapsedTraces[turn.id];
            const firstRender = !animatedTurns.current.has(turn.id);
            const toolSeconds = turn.toolCalls.reduce((sum, c) => sum + (c.duration_seconds ?? 0), 0);

            return (
              <div key={turn.id} className="space-y-3">
                <div className="flex justify-end">
                  <div
                    className="rounded-[6px] px-4 py-2.5 max-w-[85%] text-[14px] leading-relaxed select-text"
                    style={{ backgroundColor: 'var(--accent-wash)', color: 'var(--ink)' }}
                  >
                    {turn.userText}
                  </div>
                </div>

                <>
                    {turn.toolCalls.length > 0 && (
                      <div
                        className="rounded-[6px] border text-[12.5px] overflow-hidden"
                        style={{ backgroundColor: 'var(--surface-sunken)', borderColor: 'var(--line)' }}
                      >
                        <button
                          type="button"
                          className="w-full flex items-center justify-between px-3 py-2 border-b select-none text-left"
                          style={{ borderColor: 'var(--line)' }}
                          onClick={() => setCollapsedTraces((p) => ({ ...p, [turn.id]: !p[turn.id] }))}
                          aria-expanded={isExpanded}
                        >
                          <span className="font-[550]" style={{ color: 'var(--ink)' }}>
                            {turn.toolCalls.length} operation{turn.toolCalls.length > 1 ? 's' : ''}
                            <span className="font-[450]" style={{ color: 'var(--ink-muted)' }}>
                              {' '}· {toolSeconds.toFixed(2)}s in tools · {turn.elapsedSeconds.toFixed(1)}s total
                            </span>
                          </span>
                          <span className="text-[12px] font-mono" style={{ color: 'var(--ink-muted)' }}>
                            [{isExpanded ? 'hide' : 'show'}]
                          </span>
                        </button>

                        <div className={`trace-accordion ${isExpanded ? 'expanded' : ''}`}>
                          <div className="trace-accordion-inner divide-y" style={{ borderColor: 'var(--line)' }}>
                            {turn.toolCalls.map((call, idx) => {
                              const rowKey = `${turn.id}-${idx}`;
                              const isRowOpen = !!expandedRows[rowKey];
                              const raised = !!call.error;
                              const refused = !raised && REFUSALS.has(call.status ?? '');
                              const tone = raised ? 'var(--bad-ink)' : refused ? 'var(--warn-ink)' : 'var(--ink)';
                              // Share of the time spent in tools, so the slowest call reads as such.
                              const share =
                                toolSeconds > 0 && call.duration_seconds !== null
                                  ? Math.max(2, Math.min(100, (call.duration_seconds / toolSeconds) * 100))
                                  : 0;

                              return (
                                <div
                                  key={idx}
                                  className={`relative p-2.5 transition-standard hover:bg-[var(--surface)] ${firstRender ? 'trace-row-enter' : ''}`}
                                  style={firstRender ? { animationDelay: `${idx * 40}ms` } : undefined}
                                >
                                  {share > 0 && (
                                    <div
                                      className={`absolute left-0 top-1/2 -translate-y-1/2 pointer-events-none ${firstRender ? 'duration-bar-grow' : ''}`}
                                      style={{
                                        height: '6px',
                                        backgroundColor: 'var(--accent-wash)',
                                        borderRadius: '3px',
                                        width: `${share}%`,
                                        transformOrigin: 'left',
                                        animationDelay: `${idx * 40}ms`,
                                      }}
                                    />
                                  )}

                                  <button
                                    type="button"
                                    className="relative z-10 w-full flex items-center justify-between gap-3 select-none text-left"
                                    onClick={() => setExpandedRows((p) => ({ ...p, [rowKey]: !p[rowKey] }))}
                                    aria-expanded={isRowOpen}
                                  >
                                    <span className="flex items-center gap-2.5 min-w-0">
                                      <span className="inline-flex shrink-0" style={{ color: raised ? 'var(--bad-ink)' : refused ? 'var(--warn-ink)' : 'var(--ok-ink)' }}>
                                        {raised || refused ? <IconCross size={14} /> : <IconCheck size={14} />}
                                      </span>
                                      <span className="font-mono font-[600] shrink-0" style={{ color: tone }}>
                                        {call.tool}
                                      </span>
                                      <span className="font-mono text-[11.5px] truncate" style={{ color: 'var(--ink-muted)' }}>
                                        {JSON.stringify(call.arguments)}
                                      </span>
                                    </span>
                                    <span className="flex items-center gap-2 shrink-0">
                                      {call.status && (
                                        <span className="font-mono text-[11px]" style={{ color: refused ? 'var(--warn-ink)' : 'var(--ink-faint)' }}>
                                          {call.status}
                                        </span>
                                      )}
                                      {call.duration_seconds !== null && (
                                        <span className="font-mono text-[11.5px] tabular-nums" style={{ color: 'var(--ink-faint)' }}>
                                          {call.duration_seconds.toFixed(2)}s
                                        </span>
                                      )}
                                    </span>
                                  </button>

                                  <div className={`trace-accordion ${isRowOpen ? 'expanded' : ''}`}>
                                    <div className="trace-accordion-inner">
                                      <div
                                        className="mt-2 p-2 rounded-[4px] border font-mono text-[11.5px] overflow-x-auto whitespace-pre"
                                        style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--line)', color: 'var(--ink-strong)' }}
                                      >
                                        {JSON.stringify(call.arguments, null, 2)}
                                      </div>
                                    </div>
                                  </div>

                                  {raised && (
                                    <div className="relative z-10 mt-1.5 text-[12px] font-mono leading-relaxed" style={{ color: 'var(--bad-ink)' }}>
                                      {call.error}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    )}

                    {turn.failure ? (
                      <div
                        role="alert"
                        className="rounded-[6px] border px-3.5 py-3 text-[13px]"
                        style={{ backgroundColor: 'var(--bad-bg)', borderColor: 'var(--bad-line)', color: 'var(--bad-ink)' }}
                      >
                        <div className="font-[600] mb-0.5">
                          {turn.failure.status === 503 ? 'The agent is not available' : 'The agent stopped before replying'}
                        </div>
                        <div>{turn.failure.detail}</div>
                        <div className="mt-1 text-[12px]" style={{ color: 'var(--ink-muted)' }}>
                          {/* Only a refusal before the turn started is certain to have changed nothing.
                              A failure mid-turn can follow a tool that already wrote to the ledger. */}
                          {turn.failure.status === 503 || turn.failure.status === 422
                            ? 'Nothing was changed.'
                            : turn.toolCalls.length > 0
                              ? 'The operations above ran before it stopped. Anything they recorded is in the ledger.'
                              : 'No operations ran before it stopped.'}
                        </div>
                      </div>
                    ) : (
                      <div className="text-[14px] leading-relaxed whitespace-pre-line pl-1" style={{ color: 'var(--ink-strong)' }}>
                        <ReplyText text={turn.reply} />
                      </div>
                    )}

                    {turn.resultCard && (
                      <ResultCard
                        card={turn.resultCard}
                        onViewInvoicePdf={onViewInvoicePdf}
                        onViewReceiptPdf={onViewReceiptPdf}
                        onNavigate={onNavigate}
                      />
                    )}
                  </>
              </div>
            );
          })}

          {pending && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <div
                  className="rounded-[6px] px-4 py-2.5 max-w-[85%] text-[14px] leading-relaxed"
                  style={{ backgroundColor: 'var(--accent-wash)', color: 'var(--ink)' }}
                >
                  {pending.text}
                </div>
              </div>
              <div
                className="rounded-[6px] border text-[12.5px] px-3 py-2.5 flex items-center justify-between"
                style={{ backgroundColor: 'var(--surface-sunken)', borderColor: 'var(--line)' }}
              >
                <span className="flex items-center gap-2.5">
                  <span className="inline-block w-2 h-2 rounded-full inflight-dot-pulse" style={{ backgroundColor: 'var(--accent)' }} />
                  <span style={{ color: 'var(--ink-body)' }}>Working — operations are listed when the turn completes</span>
                </span>
                <span className="font-mono text-[11.5px] tabular-nums" style={{ color: 'var(--ink-faint)' }}>
                  {elapsed.toFixed(1)}s
                </span>
              </div>
            </div>
          )}

          <div ref={transcriptBottomRef} />
        </div>
      </div>

      <div className="shrink-0 border-t py-3 px-4 sm:px-8" style={{ borderColor: 'var(--line)', backgroundColor: 'var(--surface)' }}>
        <div className="max-w-[760px] mx-auto space-y-2.5">
          {available ? (
            <>
              {transcript.length === 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {SUGGESTIONS.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => handleSend(chip)}
                      disabled={!!pending}
                      className="rounded-[5px] border px-2.5 py-1 text-[11.5px] font-[500] text-left transition-standard hover:bg-[var(--surface-sunken)]"
                      style={{ backgroundColor: 'var(--canvas)', borderColor: 'var(--line)', color: 'var(--ink-muted)' }}
                    >
                      &ldquo;{chip}&rdquo;
                    </button>
                  ))}
                </div>
              )}

              <div
                className="border rounded-[8px] p-2.5 flex flex-col gap-2 transition-standard focus-within:ring-2 focus-within:ring-[var(--accent)]"
                style={{ backgroundColor: 'var(--canvas)', borderColor: 'var(--line-strong)', boxShadow: 'var(--shadow-xs)' }}
              >
                <textarea
                  ref={textareaRef}
                  rows={2}
                  value={inputMessage}
                  onChange={handleTextareaInput}
                  onKeyDown={handleKeyDown}
                  aria-label="Message the agent"
                  placeholder="Tell FreelanceFlow what happened… (e.g. Rahul paid me ₹15,000 today)"
                  className="w-full resize-none border-0 p-0 text-[13.5px] leading-normal outline-none bg-transparent"
                  style={{ color: 'var(--ink-strong)' }}
                />
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[11.5px]" style={{ color: 'var(--ink-faint)' }}>
                    Enter to send · Shift+Enter for newline
                  </span>
                  <Button
                    variant="primary"
                    disabled={!inputMessage.trim() || !!pending}
                    busy={!!pending}
                    busyText="Working…"
                    style={{ fontSize: '12px', padding: '4px 14px' }}
                    onClick={() => handleSend()}
                  >
                    Send
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-[6px] border p-4 text-[13.5px]" style={{ backgroundColor: 'var(--surface-sunken)', borderColor: 'var(--line)' }}>
              <div className="font-[600] mb-1" style={{ color: 'var(--ink)' }}>
                {!backendOnline ? 'Backend offline' : agentStatus === null ? 'Checking the agent…' : 'Agent unavailable'}
              </div>
              {(!backendOnline || agentStatus) && (
                <div className="mb-2 text-[13px]" style={{ color: 'var(--ink-muted)' }}>
                  {!backendOnline
                    ? 'The API on port 8000 is not responding.'
                    : agentStatus?.detail ?? 'No model provider is configured.'}
                </div>
              )}
              <div className="text-[13px]" style={{ color: 'var(--ink-body)' }}>
                Every operation remains available by hand — raise invoices in{' '}
                <button type="button" className="font-[600] underline" style={{ color: 'var(--accent-ink)' }} onClick={() => onNavigate('/invoices')}>
                  Invoices
                </button>{' '}
                and record money in{' '}
                <button type="button" className="font-[600] underline" style={{ color: 'var(--accent-ink)' }} onClick={() => onNavigate('/payments')}>
                  Payments
                </button>
                .
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/** The record the turn created, as the tool returned it. */
/**
 * Models write light Markdown. Render **bold** and `code` as elements, leave
 * everything else as plain text. React escapes every string, so nothing the
 * model writes can become markup beyond these two.
 */
const ReplyText: React.FC<{ text: string }> = ({ text }) => {
  const parts = text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
          return (
            <strong key={i} className="font-[600]" style={{ color: 'var(--ink)' }}>
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
          return (
            <code key={i} className="font-mono text-[12.5px]">
              {part.slice(1, -1)}
            </code>
          );
        }
        return <React.Fragment key={i}>{part}</React.Fragment>;
      })}
    </>
  );
};

const ResultCard: React.FC<{
  card: ChatResultCard;
  onViewInvoicePdf: (invoice: Invoice) => void;
  onViewReceiptPdf: (payment: Payment) => void;
  onNavigate: (path: string) => void;
}> = ({ card, onViewInvoicePdf, onViewReceiptPdf, onNavigate }) => {
  const label = (text: string) => (
    <div className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-faint)' }}>
      {text}
    </div>
  );
  const row = (name: string, value: React.ReactNode, mono = false) => (
    <div className="flex justify-between gap-4">
      <span style={{ color: 'var(--ink-muted)' }}>{name}</span>
      <span className={`font-[500] text-right ${mono ? 'font-mono tabular-nums' : ''}`}>{value}</span>
    </div>
  );
  const small = { fontSize: '11.5px', padding: '3px 8px' } as const;

  return (
    <div
      className="rounded-[8px] border p-4"
      style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--line)', boxShadow: 'var(--shadow-sm)', maxWidth: '460px' }}
    >
      {card.type === 'payment' && (
        <div className="space-y-3">
          <div className="flex justify-between items-start">
            <div>
              {label('Payment recorded')}
              <div className="text-[17px] font-[550] tabular-nums mt-0.5" style={{ color: 'var(--ok-ink)' }}>
                {card.payment.amount_display}
              </div>
            </div>
            <Badge status={card.invoice.invoice_status} />
          </div>
          <div className="text-[12.5px] space-y-1" style={{ color: 'var(--ink-body)' }}>
            {row('Client', card.payment.client_name)}
            {row('Invoice', `${card.invoice.invoice_number} · ${card.invoice.project}`)}
            {row('Invoice total', card.payment.invoice_amount_display, true)}
            {row('Paid to date', card.payment.paid_to_date_display, true)}
            {row('Left on invoice', card.payment.outstanding_after_display, true)}
            {row('Receipt', card.payment.receipt_number ?? 'Issued when first opened', !!card.payment.receipt_number)}
          </div>
          <div className="pt-2 border-t flex justify-end gap-2" style={{ borderColor: 'var(--line)' }}>
            <Button variant="default" style={small} onClick={() => onNavigate(`/invoices/${card.invoice.invoice_id}`)}>
              Open invoice
            </Button>
            <Button variant="default" style={small} onClick={() => onViewReceiptPdf(card.payment)}>
              View receipt
            </Button>
          </div>
        </div>
      )}

      {card.type === 'invoice' && (
        <div className="space-y-3">
          <div className="flex justify-between items-start">
            <div>
              {label('Invoice created')}
              <div className="text-[16px] font-mono font-[550] mt-0.5" style={{ color: 'var(--ink)' }}>
                {card.invoice.invoice_number}
              </div>
            </div>
            <Badge status={card.invoice.invoice_status} />
          </div>
          <div className="text-[12.5px] space-y-1" style={{ color: 'var(--ink-body)' }}>
            {row('Client', card.invoice.client_name)}
            {row('Project', card.invoice.project)}
            {row('Amount', card.invoice.amount_display, true)}
            {row('Due', card.invoice.due_date ?? 'No due date')}
          </div>
          <div className="pt-2 border-t flex justify-end gap-2" style={{ borderColor: 'var(--line)' }}>
            <Button variant="default" style={small} onClick={() => onNavigate(`/invoices/${card.invoice.invoice_id}`)}>
              Open invoice
            </Button>
            <Button variant="default" icon={<IconDownload size={12} />} style={small} onClick={() => onViewInvoicePdf(card.invoice)}>
              View PDF
            </Button>
          </div>
        </div>
      )}

      {card.type === 'reminder' && (
        <div className="space-y-3">
          <div className="flex justify-between items-start">
            <div>
              {label('Reminder drafted')}
              <div className="text-[14px] font-[550] mt-0.5" style={{ color: 'var(--ink)' }}>
                {card.reminder.client_name} · <span className="font-mono">{card.reminder.invoice_number}</span>
              </div>
            </div>
            <Badge status={card.reminder.reminder_status} />
          </div>
          <div
            className="text-[12.5px] leading-relaxed p-2.5 rounded-[6px] border whitespace-pre-line"
            style={{ backgroundColor: 'var(--surface-sunken)', borderColor: 'var(--line)', color: 'var(--ink-body)' }}
          >
            {card.reminder.message}
          </div>
          <div className="pt-2 border-t flex justify-end" style={{ borderColor: 'var(--line)' }}>
            <Button variant="default" style={small} onClick={() => onNavigate('/reminders')}>
              Review in Reminders
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
