"""Date handling for invoices, due dates and overdue calculation.

All dates are stored and exchanged as ISO 8601 date strings (YYYY-MM-DD).
`today()` is a function rather than a constant so tests can freeze it and so a
long-running process cannot cache yesterday.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


class InvalidDate(ValueError):
    """Raised when a date string cannot be trusted."""


def today() -> date:
    return date.today()


def today_iso() -> str:
    return today().isoformat()


def parse_date(value, field: str = "date") -> date:
    """Parse an ISO date string. Raises InvalidDate on anything else."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        raise InvalidDate(f"{field} must be a date in YYYY-MM-DD form.")
    text = value.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidDate(
            f"'{value}' is not a valid {field}. Use YYYY-MM-DD, e.g. 2026-09-15."
        ) from None


def add_days(start, days: int) -> str:
    return (parse_date(start) + timedelta(days=days)).isoformat()


def days_between(earlier, later) -> int:
    """Whole days from `earlier` to `later`. Negative if later is in the past."""
    return (parse_date(later) - parse_date(earlier)).days


def is_overdue(due_date, outstanding_minor: int, as_of=None) -> bool:
    """Overdue means money is still owed and the due date has passed.

    Derived on every read -- never stored, so it cannot go stale.
    """
    if not due_date or outstanding_minor <= 0:
        return False
    return parse_date(due_date) < parse_date(as_of or today())
