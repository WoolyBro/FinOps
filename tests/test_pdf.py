"""Phase 2.8: deterministic invoice PDFs.

Assertions read the text back out of the generated file rather than trusting the
return value, so a PDF that reports success but prints the wrong balance fails.
"""

import pytest
from pypdf import PdfReader

from app.database import get_db
from app.pdf_generator import create_invoice_pdf, format_long_date, resolve_fonts
from app.tools.clients import create_client
from app.tools.invoices import create_invoice, generate_invoice_pdf


def call(t, **kw):
    return t(**kw)


@pytest.fixture
def out_dir(tmp_path):
    return tmp_path / "invoices"


@pytest.fixture
def client_id():
    return call(
        create_client,
        name="Rahul Sharma",
        email="rahul@example.com",
        address="42 MG Road, Bengaluru 560001",
    )["client"]["client_id"]


def make_invoice(client_id, **overrides):
    kwargs = dict(
        client_id=client_id,
        project="Website development",
        amount_minor=4_000_000,
        due_date="2026-09-15",
    )
    kwargs.update(overrides)
    return call(create_invoice, **kwargs)["invoice"]


def record_payment_directly(invoice_id, amount_minor, payment_date="2026-09-05"):
    """Insert into the ledger. Phase 3 replaces this with a real tool."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO payments (invoice_id, amount_minor, payment_date)
               VALUES (?, ?, ?)""",
            (invoice_id, amount_minor, payment_date),
        )


def text_of(pdf_path):
    return PdfReader(str(pdf_path)).pages[0].extract_text()


def rupees(amount: str) -> str:
    """The rupee sign when the machine can print it, 'Rs. ' when it cannot."""
    return f"₹{amount}" if resolve_fonts()[2] else f"Rs. {amount}"


# --- the file itself ------------------------------------------------------


def test_pdf_is_actually_created(client_id, out_dir):
    invoice = make_invoice(client_id)
    result = create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)

    assert result["status"] == "created"
    path = out_dir / "FF-0001.pdf"
    assert path.exists()
    assert path.stat().st_size > 0
    assert path.read_bytes().startswith(b"%PDF")


def test_pdf_is_named_after_the_invoice_number(client_id, out_dir):
    invoice = make_invoice(client_id)
    result = create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    assert result["pdf_path"].endswith("FF-0001.pdf")
    assert result["invoice_number"] == "FF-0001"


def test_pdf_path_is_recorded_on_the_invoice(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    with get_db() as conn:
        stored = conn.execute(
            "SELECT pdf_path FROM invoices WHERE id = ?", (invoice["invoice_id"],)
        ).fetchone()["pdf_path"]
    assert stored.endswith("FF-0001.pdf")


# --- what the page says ---------------------------------------------------


def test_invoice_number_appears(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    assert "FF-0001" in text_of(out_dir / "FF-0001.pdf")


def test_client_appears(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert "Rahul Sharma" in text
    assert "rahul@example.com" in text
    assert "42 MG Road" in text


def test_project_appears(client_id, out_dir):
    invoice = make_invoice(
        client_id, project="Brand identity", description="Logo, palette and type"
    )
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert "Brand identity" in text
    assert "Logo, palette and type" in text


def test_total_appears_with_indian_grouping(client_id, out_dir):
    invoice = make_invoice(client_id, amount_minor=15_000_000)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert rupees("1,50,000.00") in text
    assert "150,000.00" not in text


def test_due_date_appears_in_long_form(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert "September 15, 2026" in text


def test_status_appears_without_underscores(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    assert "Payment Status: UNPAID" in text_of(out_dir / "FF-0001.pdf")


def test_invoice_without_due_date_omits_the_line(client_id, out_dir):
    invoice = make_invoice(client_id, due_date=None)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    assert "Due Date:" not in text_of(out_dir / "FF-0001.pdf")


# --- figures come from the ledger, not from the caller --------------------


def test_unpaid_invoice_shows_the_full_amount_due(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert rupees("0.00") in text  # paid
    assert text.count(rupees("40,000.00")) == 2  # subtotal and amount due


def test_paid_amount_is_calculated_from_the_ledger(client_id, out_dir):
    invoice = make_invoice(client_id)
    record_payment_directly(invoice["invoice_id"], 1_500_000)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)

    text = text_of(out_dir / "FF-0001.pdf")
    assert rupees("40,000.00") in text  # subtotal
    assert rupees("15,000.00") in text  # paid
    assert rupees("25,000.00") in text  # outstanding


def test_multiple_payments_sum_on_the_document(client_id, out_dir):
    invoice = make_invoice(client_id)
    record_payment_directly(invoice["invoice_id"], 1_500_000)
    record_payment_directly(invoice["invoice_id"], 1_000_000)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)

    text = text_of(out_dir / "FF-0001.pdf")
    assert rupees("25,000.00") in text  # paid
    assert rupees("15,000.00") in text  # outstanding


def test_regenerating_after_a_payment_refreshes_the_balance(client_id, out_dir):
    invoice = make_invoice(client_id)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    assert rupees("0.00") in text_of(out_dir / "FF-0001.pdf")

    record_payment_directly(invoice["invoice_id"], 4_000_000)
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)

    text = text_of(out_dir / "FF-0001.pdf")
    assert text.count(rupees("40,000.00")) == 2  # subtotal and paid
    assert rupees("0.00") in text  # nothing due


# --- currency -------------------------------------------------------------


def test_usd_invoice_uses_western_grouping_and_dollar_sign(client_id, out_dir):
    invoice = make_invoice(client_id, amount_minor=15_000_000, currency="USD")
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert "$150,000.00" in text
    assert "1,50,000" not in text


def test_zero_decimal_currency_prints_no_decimals(client_id, out_dir):
    invoice = make_invoice(client_id, amount_minor=150_000, currency="JPY")
    create_invoice_pdf(invoice["invoice_id"], output_dir=out_dir)
    text = text_of(out_dir / "FF-0001.pdf")
    assert "¥150,000" in text
    assert "¥150,000.00" not in text


# --- failure --------------------------------------------------------------


def test_nonexistent_invoice_fails_cleanly(out_dir):
    result = create_invoice_pdf(9999, output_dir=out_dir)
    assert result["status"] == "not_found"
    assert "pdf_path" not in result
    assert not out_dir.exists() or not list(out_dir.glob("*.pdf"))


def test_unwritable_destination_reports_error_not_success(client_id, out_dir, tmp_path):
    invoice = make_invoice(client_id)
    # A file where the directory should be: the render must fail, and must not
    # claim a document exists.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")

    result = create_invoice_pdf(invoice["invoice_id"], output_dir=blocked)
    assert result["status"] == "error"
    assert "pdf_path" not in result
    assert result["error"]


# --- the tool wrapper -----------------------------------------------------


def test_tool_generates_into_the_configured_directory(client_id, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    invoice = make_invoice(client_id)

    result = call(generate_invoice_pdf, invoice_id=invoice["invoice_id"])
    assert result["status"] == "created"
    assert (tmp_path / "invoices" / "FF-0001.pdf").exists()


def test_tool_reports_not_found_for_a_missing_invoice(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    assert call(generate_invoice_pdf, invoice_id=4242)["status"] == "not_found"


# --- date rendering -------------------------------------------------------


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2026-09-05", "September 5, 2026"),
        ("2026-09-15", "September 15, 2026"),
        ("2026-01-01", "January 1, 2026"),
        ("2026-12-31", "December 31, 2026"),
    ],
)
def test_format_long_date(iso, expected):
    assert format_long_date(iso) == expected


def test_format_long_date_handles_absent_dates():
    assert format_long_date(None) == ""
