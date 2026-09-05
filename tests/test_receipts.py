"""Phase 3: receipts.

A receipt is a document issued against money that actually arrived. These tests
read the text back out of the generated file, and check that a payment can never
end up with two receipt numbers.
"""

import pytest
from pypdf import PdfReader

from app.database import get_db
from app.pdf_generator import create_receipt_pdf, format_receipt_number, resolve_fonts
from app.tools.clients import create_client
from app.tools.invoices import create_invoice
from app.tools.payments import generate_receipt, record_payment


def call(t, **kw):
    return t(**kw)


def rupees(amount: str) -> str:
    return f"₹{amount}" if resolve_fonts()[2] else f"Rs. {amount}"


def text_of(path):
    return PdfReader(str(path)).pages[0].extract_text()


@pytest.fixture
def out_dir(tmp_path):
    return tmp_path / "receipts"


@pytest.fixture
def invoice():
    client = call(
        create_client,
        name="Rahul Sharma",
        email="rahul@example.com",
        address="42 MG Road, Bengaluru 560001",
    )["client"]
    return call(
        create_invoice,
        client_id=client["client_id"],
        project="Website development",
        amount_minor=4_000_000,
        due_date="2026-09-15",
    )["invoice"]


@pytest.fixture
def payment(invoice):
    return call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
        method="UPI",
        reference="TXN-99881",
    )["payment"]


# --- numbering ------------------------------------------------------------


def test_receipt_number_format():
    assert format_receipt_number(1) == "RC-0001"
    assert format_receipt_number(4) == "RC-0004"


def test_first_receipt_is_rc_0001(payment, out_dir):
    result = create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    assert result["status"] == "created"
    assert result["receipt_number"] == "RC-0001"


def test_receipt_numbers_increment_across_payments(invoice, out_dir):
    first = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000
    )["payment"]
    second = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_000_000
    )["payment"]

    assert (
        create_receipt_pdf(first["payment_id"], output_dir=out_dir)["receipt_number"]
        == "RC-0001"
    )
    assert (
        create_receipt_pdf(second["payment_id"], output_dir=out_dir)["receipt_number"]
        == "RC-0002"
    )


def test_receipt_numbers_are_independent_of_invoice_numbers(payment, out_dir):
    result = create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    assert result["receipt_number"] == "RC-0001"
    assert result["invoice_number"] == "FF-0001"


# --- one receipt per payment, for life ------------------------------------


def test_second_call_returns_the_existing_receipt(payment, out_dir):
    first = create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    second = create_receipt_pdf(payment["payment_id"], output_dir=out_dir)

    assert second["status"] == "already_exists"
    assert second["receipt_number"] == first["receipt_number"]


def test_a_payment_never_gets_a_second_receipt_number(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)

    assert len(list(out_dir.glob("*.pdf"))) == 1
    with get_db() as conn:
        counter = conn.execute(
            "SELECT value FROM counters WHERE name = 'receipt'"
        ).fetchone()["value"]
    assert counter == 1


def test_regenerate_keeps_the_original_number(payment, out_dir):
    original = create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    again = create_receipt_pdf(
        payment["payment_id"], output_dir=out_dir, regenerate=True
    )
    assert again["status"] == "created"
    assert again["receipt_number"] == original["receipt_number"]
    assert len(list(out_dir.glob("*.pdf"))) == 1


def test_receipt_details_are_recorded_on_the_payment(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    with get_db() as conn:
        row = conn.execute(
            "SELECT receipt_number, receipt_path FROM payments WHERE id = ?",
            (payment["payment_id"],),
        ).fetchone()
    assert row["receipt_number"] == "RC-0001"
    assert row["receipt_path"].endswith("RC-0001.pdf")


# --- what the document says -----------------------------------------------


def test_receipt_file_is_created(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    path = out_dir / "RC-0001.pdf"
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")


def test_receipt_names_the_payer_and_the_work(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    text = text_of(out_dir / "RC-0001.pdf")

    assert "RC-0001" in text
    assert "Rahul Sharma" in text
    assert "Website development" in text
    assert "Invoice FF-0001" in text


def test_receipt_shows_the_amount_received(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    text = text_of(out_dir / "RC-0001.pdf")
    assert "Amount Received" in text
    assert rupees("15,000.00") in text


def test_receipt_shows_the_balance_as_it_stood(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    text = text_of(out_dir / "RC-0001.pdf")

    assert rupees("40,000.00") in text  # invoice total
    assert rupees("15,000.00") in text  # paid to date
    assert rupees("25,000.00") in text  # balance
    assert "Balance outstanding" in text


def test_receipt_records_the_payment_date_and_method(payment, out_dir):
    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    text = text_of(out_dir / "RC-0001.pdf")

    assert "Payment Date: September 5, 2026" in text
    assert "Method: UPI" in text
    assert "Reference: TXN-99881" in text


def test_final_receipt_says_the_invoice_is_settled(invoice, out_dir):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    final = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=2_500_000
    )["payment"]

    create_receipt_pdf(final["payment_id"], output_dir=out_dir)
    text = text_of(out_dir / "RC-0001.pdf")

    assert "settled in full" in text
    assert "Balance outstanding" not in text


def test_earlier_receipt_keeps_its_historical_balance(invoice, out_dir):
    """A receipt is a record of a moment, not a live view."""
    first = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000
    )["payment"]
    create_receipt_pdf(first["payment_id"], output_dir=out_dir)

    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=2_500_000)
    create_receipt_pdf(first["payment_id"], output_dir=out_dir, regenerate=True)

    text = text_of(out_dir / "RC-0001.pdf")
    assert rupees("25,000.00") in text  # the balance when RC-0001 was paid
    assert "settled in full" not in text


def test_receipt_uses_indian_grouping(invoice, out_dir):
    client = call(create_client, name="Studio X")["client"]
    big = call(
        create_invoice,
        client_id=client["client_id"],
        project="Brand system",
        amount_minor=30_000_000,
    )["invoice"]
    payment = call(
        record_payment, invoice_id=big["invoice_id"], amount_minor=15_000_000
    )["payment"]

    create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    text = text_of(out_dir / "RC-0001.pdf")
    assert rupees("1,50,000.00") in text
    assert "150,000.00" not in text


# --- failure --------------------------------------------------------------


def test_nonexistent_payment_fails_cleanly(out_dir):
    result = create_receipt_pdf(4242, output_dir=out_dir)
    assert result["status"] == "not_found"
    assert "receipt_number" not in result


def test_a_failed_render_returns_the_receipt_number(payment, out_dir, tmp_path):
    """A rolled-back render must not leave a gap in the receipt sequence."""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")

    failed = create_receipt_pdf(payment["payment_id"], output_dir=blocked)
    assert failed["status"] == "error"
    assert "receipt_path" not in failed

    # The payment is untouched, and the next receipt is still RC-0001.
    with get_db() as conn:
        row = conn.execute(
            "SELECT receipt_number FROM payments WHERE id = ?",
            (payment["payment_id"],),
        ).fetchone()
    assert row["receipt_number"] is None

    recovered = create_receipt_pdf(payment["payment_id"], output_dir=out_dir)
    assert recovered["receipt_number"] == "RC-0001"


# --- the tool wrapper -----------------------------------------------------


def test_tool_generates_into_the_configured_directory(payment, tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    result = call(generate_receipt, payment_id=payment["payment_id"])
    assert result["status"] == "created"
    assert (tmp_path / "receipts" / "RC-0001.pdf").exists()


def test_tool_reports_not_found_for_a_missing_payment(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    assert call(generate_receipt, payment_id=4242)["status"] == "not_found"


def test_tool_will_not_issue_a_second_receipt(payment, tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    call(generate_receipt, payment_id=payment["payment_id"])
    again = call(generate_receipt, payment_id=payment["payment_id"])
    assert again["status"] == "already_exists"
