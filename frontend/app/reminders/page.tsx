"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, api, type Reminder } from "@/lib/api";
import { Empty, LoadError, Loading, formatDate } from "@/components/common";

type Filter = "ALL" | "DRAFT" | "APPROVED";

/**
 * Reminders are drafted here and approved here. Nothing is sent.
 *
 * That is a deliberate product decision, not an unfinished feature, so the
 * page says so rather than dangling a Send button that does nothing.
 */
export default function RemindersPage() {
  const [reminders, setReminders] = useState<Reminder[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .reminders()
      .then((body) => {
        setReminders(body.reminders);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, []);

  useEffect(load, [load]);

  function flash(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3200);
  }

  async function approve(reminder: Reminder) {
    setBusyId(reminder.reminder_id);
    try {
      await api.approveReminder(reminder.reminder_id);
      load();
      flash(`Approved the reminder for ${reminder.client_name}`);
    } catch (err) {
      flash((err as ApiError).message);
    } finally {
      setBusyId(null);
    }
  }

  const shown = (reminders ?? []).filter(
    (reminder) => filter === "ALL" || reminder.reminder_status === filter,
  );

  const drafts = (reminders ?? []).filter((r) => r.reminder_status === "DRAFT");

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Reminders</h1>
          <p className="page-sub">
            Every figure in a reminder comes from its invoice, not from a
            template you have to keep in step. Draft one from an overdue
            invoice, read it, then approve it.
          </p>
        </div>
        <div className="actions">
          <Link className="btn primary" href="/overdue">
            Draft from overdue
          </Link>
        </div>
      </div>

      {error ? <LoadError error={error} /> : null}

      <div className="notice">
        <h3>Nothing here is sent</h3>
        There is no email or messaging integration yet, by design. Approving a
        reminder records that you reviewed and accepted the wording — sending
        stays a manual step until a delivery channel is wired up.
      </div>

      <div className="segmented" role="group" aria-label="Filter reminders">
        {(["ALL", "DRAFT", "APPROVED"] as Filter[]).map((option) => (
          <button
            key={option}
            aria-pressed={filter === option}
            onClick={() => setFilter(option)}
          >
            {option === "ALL"
              ? `All (${reminders?.length ?? 0})`
              : option === "DRAFT"
                ? `Awaiting review (${drafts.length})`
                : "Approved"}
          </button>
        ))}
      </div>

      {reminders === null && !error ? (
        <div className="panel">
          <Loading what="reminders" />
        </div>
      ) : shown.length === 0 ? (
        <div className="panel">
          <Empty>
            <strong>
              {reminders?.length === 0
                ? "No reminders drafted"
                : "Nothing in this state"}
            </strong>
            {reminders?.length === 0
              ? "Go to Overdue and draft one against a late invoice."
              : "Try a different filter."}
          </Empty>
        </div>
      ) : (
        <div className="reminder-list">
          {shown.map((reminder) => (
            <div className="panel reminder" key={reminder.reminder_id}>
              <div className="panel-head">
                <div className="cell-stack">
                  <span className="lead">
                    {reminder.client_name}
                    <span
                      className={`badge ${
                        reminder.reminder_status === "APPROVED"
                          ? "PAID"
                          : "PARTIALLY_PAID"
                      }`}
                      style={{ marginLeft: 8 }}
                    >
                      {reminder.reminder_status === "APPROVED"
                        ? "Approved"
                        : "Awaiting review"}
                    </span>
                  </span>
                  <span className="sub">
                    <Link className="link" href={`/invoices/${reminder.invoice_id}`}>
                      {reminder.invoice_number}
                    </Link>{" "}
                    · {reminder.project} · drafted{" "}
                    {formatDate(reminder.created_at.slice(0, 10))}
                  </span>
                </div>
                {reminder.reminder_status === "DRAFT" ? (
                  <button
                    className="btn primary"
                    onClick={() => approve(reminder)}
                    disabled={busyId === reminder.reminder_id}
                  >
                    {busyId === reminder.reminder_id ? "Approving…" : "Approve"}
                  </button>
                ) : null}
              </div>
              <div className="panel-body">
                <blockquote className="reminder-message">
                  {reminder.message}
                </blockquote>
                {reminder.client_email ? (
                  <p className="reminder-meta">
                    Would go to <strong>{reminder.client_email}</strong> once a
                    delivery channel exists.
                  </p>
                ) : (
                  <p className="reminder-meta">
                    This client has no email on file. Add one before sending
                    becomes possible.
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {toast ? <div className="toast">{toast}</div> : null}
    </>
  );
}
