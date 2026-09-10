"""Clients, invoices and payments: the financial state, read-only."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.services import data_service
from app.services.data_service import DocumentUnavailable, NotFound

router = APIRouter(tags=["records"])


def _not_found(exc: NotFound) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "detail": str(exc)},
    )


def _document_unavailable(exc: DocumentUnavailable) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"error": "document_unavailable", "detail": str(exc)},
    )


# --- clients ---------------------------------------------------------------


@router.get("/clients")
def get_clients(limit: int = Query(100, ge=1, le=200)) -> dict:
    """Every client on file, most recently added first."""
    return data_service.clients(limit=limit)


@router.get("/clients/{client_id}")
def get_client(client_id: int) -> dict:
    """One client with their balance, invoices and payment history."""
    try:
        return data_service.client_detail(client_id)
    except NotFound as exc:
        raise _not_found(exc) from exc


# --- invoices --------------------------------------------------------------


@router.get("/invoices")
def get_invoices(
    client_id: int | None = None,
    invoice_status: str | None = Query(
        None,
        alias="status",
        description="UNPAID, PARTIALLY_PAID, PAID or CANCELLED.",
    ),
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    """Invoices, newest first, each carrying its derived balance."""
    try:
        return data_service.invoices(
            client_id=client_id, status=invoice_status, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": "invalid_request", "detail": str(exc)},
        ) from exc


@router.get("/invoices/{invoice_id}")
def get_one_invoice(invoice_id: int) -> dict:
    """One invoice with the payments recorded against it."""
    try:
        return data_service.invoice_detail(invoice_id)
    except NotFound as exc:
        raise _not_found(exc) from exc


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: int) -> FileResponse:
    """The invoice document, rendered from current state if not already on disk."""
    try:
        path = data_service.invoice_pdf(invoice_id)
    except NotFound as exc:
        raise _not_found(exc) from exc
    except DocumentUnavailable as exc:
        raise _document_unavailable(exc) from exc

    return FileResponse(path, media_type="application/pdf", filename=path.name)


# --- payments --------------------------------------------------------------


@router.get("/payments")
def get_payments(
    invoice_id: int | None = None,
    client_id: int | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    """Payments received, newest first."""
    return data_service.payments(
        invoice_id=invoice_id, client_id=client_id, limit=limit
    )


@router.get("/payments/{payment_id}")
def get_one_payment(payment_id: int) -> dict:
    try:
        return data_service.payment_detail(payment_id)
    except NotFound as exc:
        raise _not_found(exc) from exc


@router.get("/payments/{payment_id}/receipt")
def get_receipt_pdf(payment_id: int) -> FileResponse:
    """The receipt for a payment. A payment keeps one receipt number for life."""
    try:
        path = data_service.receipt_pdf(payment_id)
    except NotFound as exc:
        raise _not_found(exc) from exc
    except DocumentUnavailable as exc:
        raise _document_unavailable(exc) from exc

    return FileResponse(path, media_type="application/pdf", filename=path.name)


# --- reminders -------------------------------------------------------------


@router.get("/reminders")
def get_reminders(
    invoice_id: int | None = None,
    client_id: int | None = None,
    reminder_status: str | None = Query(
        None, alias="status", description="DRAFT, APPROVED, SENT or CANCELLED."
    ),
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    """Reminders that have been drafted. Nothing here has been sent."""
    try:
        return data_service.reminders(
            invoice_id=invoice_id,
            client_id=client_id,
            status=reminder_status,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": "invalid_request", "detail": str(exc)},
        ) from exc
