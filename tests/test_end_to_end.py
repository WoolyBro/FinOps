"""The whole deterministic invoice workflow, end to end.

This is the path the agent will drive once a model is connected:

    find/create client -> parse_amount -> create_invoice -> PDF -> retrieve

Every step here is a real tool call against a real database producing a real
file. No model is involved, which is the point: the business layer has to be
correct before the model is allowed anywhere near it.
"""

from pypdf import PdfReader

from app.pdf_generator import resolve_fonts
from app.tools.amounts import parse_amount
from app.tools.clients import find_client
from app.tools.clients import create_client
from app.tools.invoices import create_invoice, generate_invoice_pdf, get_invoice
from app.tools.payments import generate_receipt, list_payments, record_payment


def rupees(amount: str) -> str:
    return f"₹{amount}" if resolve_fonts()[2] else f"Rs. {amount}"


def test_invoice_workflow_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")

    # 1. The client is not on file yet, and the lookup says so rather than
    #    inventing one.
    missing = find_client(name="Rahul")
    assert missing["status"] == "not_found"

    # 2. Create them.
    client = create_client(name="Rahul Sharma", email="rahul@example.com")["client"]
    assert client["name"] == "Rahul Sharma"

    # 3. "40k" becomes minor units in Python, not in the model's head.
    amount = parse_amount(text="40k")
    assert amount["status"] == "ok"
    assert amount["amount_minor"] == 4_000_000
    assert amount["currency"] == "INR"

    # 4. The invoice, with its number assigned by the database.
    created = create_invoice(
        client_id=client["client_id"],
        project="Website development",
        amount_minor=amount["amount_minor"],
        currency=amount["currency"],
        due_date="2026-09-15",
    )
    assert created["status"] == "created"
    invoice = created["invoice"]
    assert invoice["invoice_number"] == "FF-0001"
    assert invoice["invoice_status"] == "UNPAID"
    assert invoice["outstanding_minor"] == 4_000_000

    # 5. The document.
    pdf = generate_invoice_pdf(invoice_id=invoice["invoice_id"])
    assert pdf["status"] == "created"
    path = tmp_path / "invoices" / "FF-0001.pdf"
    assert path.exists()

    text = PdfReader(str(path)).pages[0].extract_text()
    assert "FF-0001" in text
    assert "Rahul Sharma" in text
    assert "Website development" in text
    assert rupees("40,000.00") in text
    assert "September 15, 2026" in text
    assert "Payment Status: UNPAID" in text

    # 6. Reading it back gives the same figures, with the path recorded.
    fetched = get_invoice(invoice_number="FF-0001")
    assert fetched["status"] == "found"
    assert fetched["invoice"]["amount_minor"] == 4_000_000
    assert fetched["invoice"]["amount_display"] == "₹40,000.00"
    assert fetched["invoice"]["pdf_path"].endswith("FF-0001.pdf")
    assert fetched["invoice"]["client_name"] == "Rahul Sharma"


def test_a_second_invoice_for_the_same_client_gets_the_next_number(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")

    client = create_client(name="Studio X")["client"]
    first = create_invoice(
        client_id=client["client_id"],
        project="Landing page",
        amount_minor=parse_amount(text="Rs 25,000")["amount_minor"],
    )["invoice"]
    second = create_invoice(
        client_id=client["client_id"],
        project="Explainer video",
        amount_minor=parse_amount(text="1.5 lakh")["amount_minor"],
    )["invoice"]

    assert first["invoice_number"] == "FF-0001"
    assert second["invoice_number"] == "FF-0002"
    assert second["amount_display"] == "₹1,50,000.00"

    for invoice in (first, second):
        assert generate_invoice_pdf(invoice_id=invoice["invoice_id"])["status"] == "created"

    assert (tmp_path / "invoices" / "FF-0001.pdf").exists()
    assert (tmp_path / "invoices" / "FF-0002.pdf").exists()


def test_full_financial_lifecycle(tmp_path, monkeypatch):
    """Invoice -> partial payment -> receipt -> final payment -> paid -> receipt.

    The first moment FreelanceFlow behaves like a billing system rather than a
    pile of tools. Every balance below is read back from the ledger.
    """
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")

    # --- an invoice for Rs 40,000 -----------------------------------------
    client = create_client(name="Rahul Sharma", email="rahul@example.com")["client"]
    invoice = create_invoice(
        client_id=client["client_id"],
        project="Website development",
        amount_minor=parse_amount(text="40k")["amount_minor"],
        due_date="2026-09-15",
    )["invoice"]

    assert invoice["invoice_number"] == "FF-0001"
    assert invoice["invoice_status"] == "UNPAID"
    assert invoice["outstanding_display"] == "₹40,000.00"
    assert generate_invoice_pdf(invoice_id=invoice["invoice_id"])["status"] == "created"

    # --- Rs 15,000 arrives -------------------------------------------------
    first = record_payment(
        invoice_id=invoice["invoice_id"],
        amount_minor=parse_amount(text="15k")["amount_minor"],
        payment_date="2026-09-05",
        method="UPI",
    )
    assert first["status"] == "recorded"
    assert first["invoice"]["invoice_status"] == "PARTIALLY_PAID"
    assert first["invoice"]["amount_paid_minor"] == 1_500_000
    assert first["invoice"]["outstanding_minor"] == 2_500_000
    assert first["invoice"]["outstanding_display"] == "₹25,000.00"

    # --- and gets a receipt ------------------------------------------------
    receipt = generate_receipt(payment_id=first["payment"]["payment_id"])
    assert receipt["status"] == "created"
    assert receipt["receipt_number"] == "RC-0001"

    first_receipt = tmp_path / "receipts" / "RC-0001.pdf"
    assert first_receipt.exists()
    text = PdfReader(str(first_receipt)).pages[0].extract_text()
    assert "Rahul Sharma" in text
    assert rupees("15,000.00") in text
    assert rupees("25,000.00") in text
    assert "Invoice FF-0001" in text
    assert "Balance outstanding" in text

    # --- the invoice PDF now reflects the partial payment ------------------
    assert generate_invoice_pdf(invoice_id=invoice["invoice_id"])["status"] == "created"
    invoice_text = (
        PdfReader(str(tmp_path / "invoices" / "FF-0001.pdf")).pages[0].extract_text()
    )
    assert "Payment Status: PARTIALLY PAID" in invoice_text
    assert rupees("25,000.00") in invoice_text

    # --- the remaining Rs 25,000 ------------------------------------------
    final = record_payment(
        invoice_id=invoice["invoice_id"],
        amount_minor=parse_amount(text="25k")["amount_minor"],
        payment_date="2026-09-12",
        method="bank transfer",
    )
    assert final["status"] == "recorded"
    assert final["invoice"]["invoice_status"] == "PAID"
    assert final["invoice"]["outstanding_minor"] == 0
    assert final["invoice"]["outstanding_display"] == "₹0.00"
    assert final["invoice"]["is_overdue"] is False

    # --- and its receipt ---------------------------------------------------
    final_receipt = generate_receipt(payment_id=final["payment"]["payment_id"])
    assert final_receipt["receipt_number"] == "RC-0002"

    final_text = (
        PdfReader(str(tmp_path / "receipts" / "RC-0002.pdf")).pages[0].extract_text()
    )
    assert rupees("25,000.00") in final_text
    assert "settled in full" in final_text

    # --- the ledger is the whole story ------------------------------------
    history = list_payments(invoice_id=invoice["invoice_id"])
    assert history["count"] == 2
    assert history["total_received_minor"] == 4_000_000

    settled = get_invoice(invoice_number="FF-0001")["invoice"]
    assert settled["invoice_status"] == "PAID"
    assert settled["amount_paid_minor"] == 4_000_000
    assert settled["outstanding_minor"] == 0

    # No further money is accepted against it.
    assert record_payment(invoice_id=invoice["invoice_id"], amount_minor=100)[
        "status"
    ] == "error"


def test_receipts_are_never_issued_without_a_payment(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")

    client = create_client(name="Studio X")["client"]
    invoice = create_invoice(
        client_id=client["client_id"],
        project="Landing page",
        amount_minor=1_000_000,
    )["invoice"]

    # An invoice exists, but nothing has been received, so there is nothing to
    # issue a receipt against and no receipt number is consumed.
    assert generate_receipt(payment_id=1)["status"] == "not_found"
    assert not (tmp_path / "receipts").exists() or not list(
        (tmp_path / "receipts").glob("*.pdf")
    )

    payment = record_payment(invoice_id=invoice["invoice_id"], amount_minor=1_000_000)
    assert generate_receipt(payment_id=payment["payment"]["payment_id"])[
        "receipt_number"
    ] == "RC-0001"
