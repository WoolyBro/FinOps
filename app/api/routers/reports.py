"""Reporting endpoints: the numbers the dashboard shows.

Every figure is derived at request time from invoices and payments. Nothing is
cached, so the dashboard cannot drift from the ledger -- and nothing is left for
the browser to add up, so it cannot drift from the documents either.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.services import data_service, views

router = APIRouter(prefix="/reports", tags=["reports"])


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"error": "invalid_request", "detail": str(exc)},
    )


@router.get("/summary")
def summary(
    start_date: str | None = Query(
        None, description="YYYY-MM-DD. Defaults to the first of this month."
    ),
    end_date: str | None = Query(
        None, description="YYYY-MM-DD. Defaults to the last of this month."
    ),
) -> dict:
    """Money invoiced and received in the period, plus what is currently owed.

    Invoiced, received and the invoice counts are period-scoped because they
    are flows. Outstanding and overdue are current totals across every open
    invoice: a balance owed does not belong to a calendar month.
    """
    try:
        return data_service.summary(start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/overview")
def overview() -> dict:
    """Everything the Overview screen shows, derived in one read."""
    return views.overview()


@router.get("/monthly")
def monthly(months: int = Query(6, ge=1, le=24)) -> dict:
    """Invoiced against received per month, ending with the current month."""
    return views.monthly(months=months)


@router.get("/clients")
def clients(
    start_date: str | None = Query(None, description="YYYY-MM-DD. Omit for all-time."),
    end_date: str | None = Query(None, description="YYYY-MM-DD. Omit for all-time."),
) -> dict:
    """Each client's invoiced, received, outstanding and overdue, largest balance first."""
    try:
        return views.client_breakdown(start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/overdue")
def overdue(client_id: int | None = None) -> dict:
    """Invoices past their due date with money still owed, most overdue first."""
    return data_service.overdue(client_id=client_id)


@router.get("/outstanding")
def outstanding(client_id: int | None = None) -> dict:
    """Every invoice with money owed, whether or not it is late yet."""
    return data_service.outstanding(client_id=client_id)
