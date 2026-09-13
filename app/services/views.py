"""Dashboard views: the derived figures each screen shows, computed here.

The browser renders these; it does not add them up. A dashboard that sums its
own invoice list will, sooner or later, disagree with the invoice PDF -- a
cancelled invoice counted, a currency mixed in, a page of results truncated --
and the user cannot tell a display bug from a ledger bug. So every total, count
and ratio a page shows is produced here, from the same ledger and the same
helpers the agent's reporting tools use.

Read-only. Nothing in this module writes.
"""

from __future__ import annotations

from datetime import date

from app.config import DEFAULT_CURRENCY
from app.database import get_db
from app.dates import InvalidDate, current_month_bounds, parse_date, today
from app.models import PAYMENT_SELECT, invoice_to_dict, payment_to_dict
from app.money import format_money
from app.security import scrub
from app.tools.clients import list_clients
from app.tools.reports import (
    _by_currency_totals,
    _fetch_invoices,
    get_financial_summary,
)

OPEN = "i.status IN ('UNPAID', 'PARTIALLY_PAID')"

MONTH_LABELS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


# --- small helpers ----------------------------------------------------------


def _payment_totals(payments: list[dict]) -> list[dict]:
    """Received per currency. Payments carry their invoice's currency."""
    return _by_currency_totals(payments, "amount_minor")


def _minor_in(totals: list[dict], currency: str) -> int:
    return next((t["total_minor"] for t in totals if t["currency"] == currency), 0)


def _oldest(overdue: list[dict]) -> dict | None:
    if not overdue:
        return None
    worst = max(overdue, key=lambda inv: inv["days_overdue"])
    return {
        "invoice_id": worst["invoice_id"],
        "invoice_number": worst["invoice_number"],
        "client_id": worst["client_id"],
        "client_name": worst["client_name"],
        "days_overdue": worst["days_overdue"],
    }


def _period(start_date: str | None, end_date: str | None) -> tuple[str, str]:
    default_start, default_end = current_month_bounds()
    try:
        start = parse_date(start_date or default_start, "start_date")
        end = parse_date(end_date or default_end, "end_date")
    except InvalidDate as exc:
        raise ValueError(str(exc)) from exc
    if end < start:
        raise ValueError(f"end_date {end} is before start_date {start}.")
    return start.isoformat(), end.isoformat()


def _payments_between(conn, start: str | None, end: str | None,
                      client_id: int | None = None,
                      invoice_id: int | None = None,
                      limit: int | None = None) -> list[dict]:
    where: list[str] = []
    args: list = []
    if start:
        where.append("p.payment_date >= ?")
        args.append(start)
    if end:
        where.append("p.payment_date <= ?")
        args.append(end)
    if client_id is not None:
        where.append("i.client_id = ?")
        args.append(client_id)
    if invoice_id is not None:
        where.append("p.invoice_id = ?")
        args.append(invoice_id)

    sql = PAYMENT_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.payment_date DESC, p.id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    return [payment_to_dict(r) for r in conn.execute(sql, args).fetchall()]


# --- the payments ledger ----------------------------------------------------


def payments_ledger(
    invoice_id: int | None = None,
    client_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> dict:
    """Payments, newest first, with the total for exactly this filter.

    The total is computed over every matching payment, not just the page the
    client asked for -- a "total received" that silently depends on a page
    size is exactly the kind of number this module exists to prevent.
    """
    try:
        start = parse_date(start_date, "start_date").isoformat() if start_date else None
        end = parse_date(end_date, "end_date").isoformat() if end_date else None
    except InvalidDate as exc:
        raise ValueError(str(exc)) from exc

    with get_db() as conn:
        matching = _payments_between(conn, start, end, client_id, invoice_id)

    page = matching[:limit]
    totals = _payment_totals(matching)
    return scrub(
        {
            "status": "ok",
            "count": len(matching),
            "payments": page,
            "received_total": totals,
            "total_received_minor": _minor_in(totals, DEFAULT_CURRENCY),
        }
    )


# --- a reporting period -----------------------------------------------------


def period_summary(start_date: str | None = None, end_date: str | None = None) -> dict:
    """The agent's financial summary, plus what the Reports screen needs.

    Extends rather than replaces get_financial_summary, so the dashboard and
    the agent report identical received/outstanding/overdue figures.
    """
    base = get_financial_summary(start_date=start_date, end_date=end_date)
    if base["status"] == "error":
        raise ValueError(base["error"])
    start, end = base["period_start"], base["period_end"]

    with get_db() as conn:
        issued = [
            invoice_to_dict(r)
            for r in _fetch_invoices(conn, None, "i.issue_date BETWEEN ? AND ?", (start, end))
        ]
        cancelled = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'CANCELLED' "
            "AND issue_date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]
        payment_count = conn.execute(
            "SELECT COUNT(*) FROM payments WHERE payment_date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]
        open_invoices = [invoice_to_dict(r) for r in _fetch_invoices(conn, None, OPEN)]

    overdue = [inv for inv in open_invoices if inv["is_overdue"]]

    return scrub(
        {
            **base,
            "invoiced_total": _by_currency_totals(issued, "amount_minor"),
            "payments_in_period": payment_count,
            "cancelled_in_period": cancelled,
            # Of the invoices issued in the period, how many are late today.
            # A qualifier on the partition above, never a peer of it.
            "overdue_in_period": sum(1 for inv in issued if inv["is_overdue"]),
            "open_invoice_count": len(open_invoices),
            "overdue_invoice_count": len(overdue),
            "oldest_overdue": _oldest(overdue),
        }
    )


# --- monthly series ---------------------------------------------------------


def _month_start(d: date, back: int) -> date:
    index = d.year * 12 + (d.month - 1) - back
    return date(index // 12, index % 12 + 1, 1)


def _nice_scale(max_minor: int, steps: int = 3) -> int:
    """Round a maximum up to `steps` clean gridline intervals.

    ₹1,47,250 becomes ₹1,50,000 (three steps of ₹50,000), so the axis reads in
    round numbers and the tallest bar still fills most of the plot.
    """
    if max_minor <= 0:
        return 0
    raw = -(-max_minor // steps)  # ceiling division, integers only
    magnitude = 1
    while magnitude * 10 <= raw:
        magnitude *= 10
    # 1, 2, 2.5, 5, 10 times the magnitude, as integer fractions.
    for numerator, denominator in ((1, 1), (2, 1), (5, 2), (5, 1), (10, 1)):
        step = magnitude * numerator // denominator
        if step >= raw:
            return step * steps
    return magnitude * 10 * steps  # pragma: no cover - loop always returns


def _axis_label(minor: int, currency: str) -> str:
    text = format_money(minor, currency)
    return text[:-3] if text.endswith(".00") else text


def monthly(months: int = 6, as_of: str | None = None) -> dict:
    """Invoiced against received, month by month, ending with the current month.

    Charted in the default currency; any other currency's activity is listed in
    `other_currencies` rather than being added into the same bars.
    """
    months = max(1, min(int(months), 24))
    end_day = parse_date(as_of or today())
    first = _month_start(end_day, months - 1)
    _, window_end = current_month_bounds(end_day)
    currency = DEFAULT_CURRENCY

    with get_db() as conn:
        issued = [
            invoice_to_dict(r)
            for r in _fetch_invoices(
                conn, None, "i.issue_date BETWEEN ? AND ?", (first.isoformat(), window_end)
            )
        ]
        received = _payments_between(conn, first.isoformat(), window_end)

    series = []
    others: set[str] = set()
    for back in range(months - 1, -1, -1):
        start = _month_start(end_day, back)
        key = f"{start.year:04d}-{start.month:02d}"
        month_invoices = [inv for inv in issued if inv["issue_date"].startswith(key)]
        month_payments = [p for p in received if p["payment_date"].startswith(key)]
        invoiced_totals = _by_currency_totals(month_invoices, "amount_minor")
        received_totals = _payment_totals(month_payments)
        others.update(t["currency"] for t in invoiced_totals + received_totals)

        invoiced_minor = _minor_in(invoiced_totals, currency)
        received_minor = _minor_in(received_totals, currency)
        series.append(
            {
                "month": key,
                "label": MONTH_LABELS[start.month - 1],
                "name": f"{MONTH_NAMES[start.month - 1]} {start.year}",
                "invoiced_minor": invoiced_minor,
                "received_minor": received_minor,
                "invoiced_display": format_money(invoiced_minor, currency),
                "received_display": format_money(received_minor, currency),
                "invoice_count": len(month_invoices),
                "payment_count": len(month_payments),
            }
        )

    peak = max(
        [m["invoiced_minor"] for m in series] + [m["received_minor"] for m in series],
        default=0,
    )
    scale = _nice_scale(peak)
    ticks = (
        [{"minor": scale * i // 3, "display": _axis_label(scale * i // 3, currency)}
         for i in range(0, 4)]
        if scale
        else []
    )

    return {
        "status": "ok",
        "currency": currency,
        "period_start": first.isoformat(),
        "period_end": window_end,
        "months": series,
        "scale_max_minor": scale,
        "ticks": ticks,
        "other_currencies": sorted(others - {currency}),
    }


# --- per-client breakdown ---------------------------------------------------


def client_breakdown(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Each client's billing, for the Clients grid and the Reports table.

    With no period, "invoiced" and "received" are all-time. With one, they are
    scoped to it. Outstanding and overdue are always as of today: money owed
    does not belong to the month it was invoiced in.
    """
    scoped = bool(start_date or end_date)
    start, end = _period(start_date, end_date) if scoped else (None, None)

    clients = list_clients(limit=200)["clients"]
    with get_db() as conn:
        every_invoice = [invoice_to_dict(r) for r in _fetch_invoices(conn, None)]
        payments = _payments_between(conn, start, end)

    rows = []
    for client in clients:
        cid = client["client_id"]
        theirs = [inv for inv in every_invoice if inv["client_id"] == cid]
        in_period = (
            [inv for inv in theirs if start <= inv["issue_date"] <= end]
            if scoped
            else theirs
        )
        open_invoices = [inv for inv in theirs if inv["outstanding_minor"] > 0]
        overdue = [inv for inv in open_invoices if inv["is_overdue"]]
        paid_to_them = [p for p in payments if p["client_id"] == cid]
        outstanding = _by_currency_totals(open_invoices, "outstanding_minor")

        rows.append(
            {
                "client_id": cid,
                "name": client["name"],
                "email": client["email"],
                "phone": client["phone"],
                "invoice_count": len(theirs),
                "paid_invoice_count": sum(
                    1 for inv in theirs if inv["invoice_status"] == "PAID"
                ),
                "open_invoice_count": len(open_invoices),
                "overdue_invoice_count": len(overdue),
                "invoiced_total": _by_currency_totals(in_period, "amount_minor"),
                "received_total": _payment_totals(paid_to_them),
                "outstanding_total": outstanding,
                "overdue_total": _by_currency_totals(overdue, "outstanding_minor"),
                "_sort": _minor_in(outstanding, DEFAULT_CURRENCY),
            }
        )

    rows.sort(key=lambda r: (-r["_sort"], r["name"].lower()))
    for row in rows:
        del row["_sort"]

    return scrub(
        {
            "status": "ok",
            "period_start": start,
            "period_end": end,
            "count": len(rows),
            "clients": rows,
        }
    )


# --- the overview screen ----------------------------------------------------


def _average_days_to_payment(conn) -> tuple[int | None, int]:
    """Mean days from issue to the payment that settled it, over paid invoices."""
    rows = conn.execute(
        """SELECT i.issue_date AS issued, MAX(p.payment_date) AS settled
             FROM invoices i
             JOIN payments p ON p.invoice_id = i.id
            WHERE i.status = 'PAID'
            GROUP BY i.id"""
    ).fetchall()
    if not rows:
        return None, 0
    spans = [
        max(0, (parse_date(r["settled"]) - parse_date(r["issued"])).days) for r in rows
    ]
    return round(sum(spans) / len(spans)), len(spans)


def _recent_activity(conn, limit: int) -> list[dict]:
    invoices = [invoice_to_dict(r) for r in _fetch_invoices(conn, None)]
    payments = _payments_between(conn, None, None, limit=limit)

    events = [
        {
            "kind": "invoice",
            "date": inv["issue_date"],
            "created_at": inv["created_at"],
            "invoice_id": inv["invoice_id"],
            "invoice_number": inv["invoice_number"],
            "client_id": inv["client_id"],
            "client_name": inv["client_name"],
            "amount_display": inv["amount_display"],
            "payment_id": None,
        }
        for inv in invoices
    ] + [
        {
            "kind": "payment",
            "date": p["payment_date"],
            "created_at": p["created_at"],
            "invoice_id": p["invoice_id"],
            "invoice_number": p["invoice_number"],
            "client_id": p["client_id"],
            "client_name": p["client_name"],
            "amount_display": p["amount_display"],
            "payment_id": p["payment_id"],
        }
        for p in payments
    ]
    events.sort(key=lambda e: (e["date"], e["created_at"] or ""), reverse=True)
    return events[:limit]


def overview(as_of: str | None = None) -> dict:
    """Everything the Overview screen shows, in one read."""
    day = parse_date(as_of or today())
    month_start, month_end = current_month_bounds(day)
    month = period_summary(month_start, month_end)
    currency = DEFAULT_CURRENCY

    with get_db() as conn:
        open_invoices = [invoice_to_dict(r) for r in _fetch_invoices(conn, None, OPEN)]
        client_count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        average_days, settled_count = _average_days_to_payment(conn)
        activity = _recent_activity(conn, limit=8)

    overdue = sorted(
        (inv for inv in open_invoices if inv["is_overdue"]),
        key=lambda inv: inv["days_overdue"],
        reverse=True,
    )

    invoiced_minor = _minor_in(month["invoiced_total"], currency)
    received_minor = _minor_in(month["received_total"], currency)
    collection_rate = (
        round(received_minor * 100 / invoiced_minor) if invoiced_minor else None
    )

    return scrub(
        {
            "status": "ok",
            "as_of": day.isoformat(),
            "currency": currency,
            "outstanding_total": _by_currency_totals(open_invoices, "outstanding_minor"),
            "overdue_total": _by_currency_totals(overdue, "outstanding_minor"),
            "open_invoice_count": len(open_invoices),
            "overdue_invoice_count": len(overdue),
            "oldest_overdue": _oldest(overdue),
            "client_count": client_count,
            "clients_with_balance": len({inv["client_id"] for inv in open_invoices}),
            "average_days_to_payment": average_days,
            "settled_invoice_count": settled_count,
            "month": {
                "name": f"{MONTH_NAMES[day.month - 1]} {day.year}",
                "start": month_start,
                "end": month_end,
                "invoiced_total": month["invoiced_total"],
                "received_total": month["received_total"],
                "invoices_issued": month["invoices_issued_in_period"],
                "payments_received": month["payments_in_period"],
                # received / invoiced in the same month. Can exceed 100 when
                # older invoices are settled this month -- that is real, not a bug.
                "collection_rate_percent": collection_rate,
            },
            "needs_attention": overdue[:5],
            "recent_activity": activity,
        }
    )
