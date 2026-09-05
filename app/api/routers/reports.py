"""Reporting endpoints: the numbers the dashboard shows.

Every figure is derived at request time from invoices and payments. Nothing is
cached, so the dashboard cannot drift from the ledger.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.services import data_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def summary(
    start_date: str | None = Query(
        None, description="YYYY-MM-DD. Defaults to the first of this month."
    ),
    end_date: str | None = Query(
        None, description="YYYY-MM-DD. Defaults to the last of this month."
    ),
) -> dict:
    """Money received in the period, plus what is currently owed.

    Received and the invoice counts are period-scoped because they are flows.
    Outstanding and overdue are current totals across every open invoice: a
    balance owed does not belong to a calendar month.
    """
    try:
        return data_service.summary(start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": "invalid_request", "detail": str(exc)},
        ) from exc


@router.get("/overdue")
def overdue(client_id: int | None = None) -> dict:
    """Invoices past their due date with money still owed, most overdue first."""
    return data_service.overdue(client_id=client_id)


@router.get("/outstanding")
def outstanding(client_id: int | None = None) -> dict:
    """Every invoice with money owed, whether or not it is late yet."""
    return data_service.outstanding(client_id=client_id)
