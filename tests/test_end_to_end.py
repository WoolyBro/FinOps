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
