"""Write endpoints: everything the dashboard can actually do.

These exist so the application is operable without a model. The agent is a
convenience, not the only way in -- and when Bedrock is unreachable, a
freelancer can still invoice a client and record a payment.

Every handler goes through the same tools the agent uses, so a refusal here is
the tool's refusal, worded by the tool. A duplicate invoice, an overpayment, a
due date before the issue date: all rejected identically whichever path asked.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services import write_service
from app.services.write_service import Rejected

router = APIRouter(tags=["commands"])


def _rejected(exc: Rejected) -> HTTPException:
    """A tool refusal becomes a 409, carrying the tool's own explanation.

    409 rather than 400: the request was well-formed, the *state* disallows it
    (already paid, duplicate suspected, nothing outstanding). The UI shows the
    detail verbatim, because the tools word these carefully already.
    """
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": exc.tool_status,
            "detail": exc.detail,
            "result": exc.payload,
        },
    )


# --- amounts ---------------------------------------------------------------


class AmountRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100, examples=["40k", "1.5 lakh"])
    default_currency: str = Field("INR", min_length=3, max_length=3)


@router.post("/amounts/parse")
def parse_amount(request: AmountRequest) -> dict:
    """Convert "40k" into minor units, using the same parser the agent uses."""
    try:
        return write_service.parse_amount(request.text, request.default_currency)
    except Rejected as exc:
        raise _rejected(exc) from exc


# --- clients ---------------------------------------------------------------


class ClientRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=2000)


@router.post("/clients", status_code=status.HTTP_201_CREATED)
def create_client(request: ClientRequest) -> dict:
    """Add a client. An existing name returns that client rather than a copy."""
    try:
        return write_service.add_client(
            name=request.name,
            email=request.email,
            phone=request.phone,
            address=request.address,
            notes=request.notes,
        )
    except Rejected as exc:
        raise _rejected(exc) from exc


class ClientFieldUpdate(BaseModel):
    field: str = Field(..., examples=["email"])
    value: str = Field(..., max_length=2000)


@router.patch("/clients/{client_id}")
def update_client(client_id: int, request: ClientFieldUpdate) -> dict:
    try:
        return write_service.edit_client(client_id, request.field, request.value)
    except Rejected as exc:
        raise _rejected(exc) from exc


# --- invoices --------------------------------------------------------------


class InvoiceRequest(BaseModel):
    client_id: int
    project: str = Field(..., min_length=1, max_length=300)
    amount_minor: int = Field(..., gt=0, description="Paise/cents, not rupees.")
    currency: str = Field("INR", min_length=3, max_length=3)
    issue_date: str | None = None
    due_date: str | None = None
    description: str | None = Field(None, max_length=2000)
    allow_duplicate: bool = False


@router.post("/invoices", status_code=status.HTTP_201_CREATED)
def create_invoice(request: InvoiceRequest) -> dict:
    """Raise an invoice. The number is assigned by the database."""
    try:
        return write_service.add_invoice(
            client_id=request.client_id,
            project=request.project,
            amount_minor=request.amount_minor,
            currency=request.currency,
            issue_date=request.issue_date,
            due_date=request.due_date,
            description=request.description,
            allow_duplicate=request.allow_duplicate,
        )
    except Rejected as exc:
        raise _rejected(exc) from exc


# --- payments --------------------------------------------------------------


class PaymentRequest(BaseModel):
    invoice_id: int
    amount_minor: int = Field(..., gt=0)
    payment_date: str | None = None
    method: str | None = Field(None, max_length=100)
    reference: str | None = Field(None, max_length=200)
    allow_duplicate: bool = False


@router.post("/payments", status_code=status.HTTP_201_CREATED)
def record_payment(request: PaymentRequest) -> dict:
    """Record money received. The balance and status come back recalculated."""
    try:
        return write_service.add_payment(
            invoice_id=request.invoice_id,
            amount_minor=request.amount_minor,
            payment_date=request.payment_date,
            method=request.method,
            reference=request.reference,
            allow_duplicate=request.allow_duplicate,
        )
    except Rejected as exc:
        raise _rejected(exc) from exc


# --- reminders -------------------------------------------------------------


class ReminderRequest(BaseModel):
    invoice_id: int
    force: bool = False


@router.post("/reminders", status_code=status.HTTP_201_CREATED)
def create_reminder(request: ReminderRequest) -> dict:
    """Draft a reminder. Nothing is sent -- there is no send capability."""
    try:
        return write_service.draft_reminder(request.invoice_id, force=request.force)
    except Rejected as exc:
        raise _rejected(exc) from exc


@router.post("/reminders/{reminder_id}/approve")
def approve_reminder(reminder_id: int) -> dict:
    """Mark a drafted reminder as reviewed and approved."""
    try:
        return write_service.approve(reminder_id)
    except Rejected as exc:
        raise _rejected(exc) from exc


@router.post("/reminders/{reminder_id}/cancel")
def cancel_reminder(reminder_id: int) -> dict:
    """Withdraw a reminder. It stays on record, marked CANCELLED."""
    try:
        return write_service.cancel(reminder_id)
    except Rejected as exc:
        raise _rejected(exc) from exc
