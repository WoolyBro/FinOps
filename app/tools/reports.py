"""Read-only reporting tools.

Every number here is derived at query time from invoices and payments -- there
is no stored `overdue`, `outstanding`, `monthly_revenue` or similar. Reopen the
app after three weeks away and these figures are exactly as correct as if it
had been running the whole time, because nothing was cached while it was closed.

Money is broken down per currency rather than summed across them. Adding 500
USD and 500 EUR into a single "1000" would be a real bug, not a simplification,
so a freelancer billing in more than one currency gets one line per currency
instead of a wrong total.
"""

from __future__ import annotations

from app.database import get_db
from app.dates import current_month_bounds, parse_date, InvalidDate
from app.models import INVOICE_SELECT, invoice_to_dict
from app.money import format_money
from strands import tool

OPEN_STATUSES = ("UNPAID", "PARTIALLY_PAID")


def _fetch_invoices(conn, client_id: int | None, extra_where: str = "", params=()):
    where = ["i.status != 'CANCELLED'"]
    args: list = []
    if client_id is not None:
        where.append("i.client_id = ?")
        args.append(client_id)
    if extra_where:
        where.append(extra_where)
        args.extend(params)
    sql = INVOICE_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY i.id"
    return conn.execute(sql, args).fetchall()


def _by_currency_totals(invoices: list[dict], amount_key: str) -> list[dict]:
    """Sum one field per currency, so amounts are never mixed across currencies."""
    totals: dict[str, int] = {}
    for inv in invoices:
        totals[inv["currency"]] = totals.get(inv["currency"], 0) + inv[amount_key]
    return [
        {
            "currency": currency,
            "total_minor": total,
            "total_display": format_money(total, currency),
        }
        for currency, total in sorted(totals.items())
    ]


@tool
def get_overdue_invoices(client_id: int | None = None) -> dict:
    """List invoices that are overdue right now: money is still owed and the
    due date has passed. Cancelled invoices and invoices with no due date are
    never overdue.

    This is read-only and changes nothing. Use it to answer "who is overdue"
    or "which invoices are late" -- do not infer overdue status from memory of
    an earlier conversation, since a payment may have landed since then.

    Args:
        client_id: Restrict to one client's invoices.

    Returns:
        status "ok" with the overdue invoices (most overdue first), a count,
        and the overdue total broken down by currency.
    """
    with get_db() as conn:
        rows = _fetch_invoices(conn, client_id)
        invoices = [invoice_to_dict(r) for r in rows]

    overdue = [inv for inv in invoices if inv["is_overdue"]]
    overdue.sort(key=lambda inv: inv["days_overdue"], reverse=True)

    return {
        "status": "ok",
        "count": len(overdue),
        "invoices": overdue,
        "overdue_total": _by_currency_totals(overdue, "outstanding_minor"),
    }


@tool
def get_outstanding_invoices(client_id: int | None = None) -> dict:
    """List every invoice that still has money owed on it, whether or not it
    is overdue yet. This is the broader query -- an invoice due next week and
    an invoice four days overdue are both outstanding, but only one is overdue.

    Use get_overdue_invoices for the narrower "who is late" question.

    Args:
        client_id: Restrict to one client's invoices.

    Returns:
        status "ok" with the outstanding invoices (soonest due date first,
        invoices with no due date last), a count, and the outstanding total
        broken down by currency.
    """
    with get_db() as conn:
        rows = _fetch_invoices(
            conn, client_id, "i.status IN ('UNPAID', 'PARTIALLY_PAID')"
        )
        invoices = [invoice_to_dict(r) for r in rows]

    invoices.sort(key=lambda inv: (inv["due_date"] is None, inv["due_date"] or ""))

    return {
        "status": "ok",
        "count": len(invoices),
        "invoices": invoices,
        "outstanding_total": _by_currency_totals(invoices, "outstanding_minor"),
    }


@tool
def get_client_balance(client_id: int) -> dict:
    """How much one client has been billed, has paid, and still owes.

    Use this to answer "does Rahul still owe me anything" or "how much has
    Priya paid so far" -- do not add up invoices from memory, since a payment
    may have landed since the numbers were last mentioned.

    Args:
        client_id: The client's numeric id, from find_client.

    Returns:
        status "ok" with per-currency totals (invoiced, paid, outstanding,
        overdue) and the invoice count by status. "not_found" if there is no
        such client.
    """
    with get_db() as conn:
        client = conn.execute(
            "SELECT id, name FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not client:
            return {"status": "not_found", "client_id": client_id}

        rows = _fetch_invoices(conn, client_id)
        invoices = [invoice_to_dict(r) for r in rows]

    overdue = [inv for inv in invoices if inv["is_overdue"]]

    status_counts = {"UNPAID": 0, "PARTIALLY_PAID": 0, "PAID": 0}
    for inv in invoices:
        status_counts[inv["invoice_status"]] = (
            status_counts.get(inv["invoice_status"], 0) + 1
        )

    return {
        "status": "ok",
        "client_id": client_id,
        "client_name": client["name"],
        "invoice_count": len(invoices),
        "invoice_counts_by_status": status_counts,
        "invoiced_total": _by_currency_totals(invoices, "amount_minor"),
        "paid_total": _by_currency_totals(invoices, "amount_paid_minor"),
        "outstanding_total": _by_currency_totals(invoices, "outstanding_minor"),
        "overdue_total": _by_currency_totals(overdue, "outstanding_minor"),
    }


@tool
def get_financial_summary(start_date: str | None = None, end_date: str | None = None) -> dict:
    """A financial snapshot: money received in a period, and where things
    stand right now.

    "Received" and the invoice/status counts are scoped to the period -- money
    that arrived, and invoices issued, between start_date and end_date.
    "Outstanding" and "overdue" are current totals across every open invoice
    regardless of when it was issued, because a balance owed does not belong
    to a calendar month -- an invoice from three months ago that is still
    unpaid is still relevant today.

    Args:
        start_date: YYYY-MM-DD. Defaults to the first day of the current month.
        end_date: YYYY-MM-DD. Defaults to the last day of the current month.

    Returns:
        status "ok" with the period, received/outstanding/overdue broken down
        by currency, and invoice counts for the period by status.
    """
    default_start, default_end = current_month_bounds()
    start = start_date or default_start
    end = end_date or default_end

    try:
        start_d = parse_date(start, "start_date")
        end_d = parse_date(end, "end_date")
    except InvalidDate as exc:
        return {"status": "error", "error": str(exc)}
    if end_d < start_d:
        return {
            "status": "error",
            "error": f"end_date {end} is before start_date {start}.",
        }
    start, end = start_d.isoformat(), end_d.isoformat()

    with get_db() as conn:
        # Money that moved in the period, regardless of which invoice or when
        # that invoice was issued -- this is a cash-flow figure.
        payment_rows = conn.execute(
            """SELECT i.currency AS currency, SUM(p.amount_minor) AS total
                 FROM payments p
                 JOIN invoices i ON i.id = p.invoice_id
                WHERE p.payment_date BETWEEN ? AND ?
                GROUP BY i.currency""",
            (start, end),
        ).fetchall()
        received_total = [
            {
                "currency": r["currency"],
                "total_minor": int(r["total"]),
                "total_display": format_money(int(r["total"]), r["currency"]),
            }
            for r in payment_rows
        ]

        # Invoices issued in the period -- a flow, like received.
        issued_rows = _fetch_invoices(
            conn, None, "i.issue_date BETWEEN ? AND ?", (start, end)
        )
        issued = [invoice_to_dict(r) for r in issued_rows]

        # Outstanding and overdue are current-state facts, not period-scoped.
        all_open_rows = _fetch_invoices(conn, None, "i.status IN ('UNPAID', 'PARTIALLY_PAID')")
        open_invoices = [invoice_to_dict(r) for r in all_open_rows]

    overdue_invoices = [inv for inv in open_invoices if inv["is_overdue"]]

    status_counts = {"UNPAID": 0, "PARTIALLY_PAID": 0, "PAID": 0}
    for inv in issued:
        status_counts[inv["invoice_status"]] = (
            status_counts.get(inv["invoice_status"], 0) + 1
        )

    return {
        "status": "ok",
        "period_start": start,
        "period_end": end,
        "received_total": received_total,
        "outstanding_total": _by_currency_totals(open_invoices, "outstanding_minor"),
        "overdue_total": _by_currency_totals(overdue_invoices, "outstanding_minor"),
        "invoices_issued_in_period": len(issued),
        "invoice_counts_in_period": status_counts,
    }
