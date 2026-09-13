"""Deterministic invoice PDF generation.

Nothing in this module is negotiable by the model. The agent calls a tool with
an invoice id; every figure on the page is read from SQLite and formatted by
`format_money`. The layout is fixed code. The model does not choose wording,
placement, or a single number.

Font note: the rupee sign U+20B9 is absent from the PDF core fonts, so an
embeddable system font carrying that glyph is located and embedded. When no
such font exists on the machine, INR falls back to "Rs. " rather than printing
a black box or silently dropping the symbol.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from app.config import (
    BUSINESS_ADDRESS,
    BUSINESS_EMAIL,
    BUSINESS_NAME,
    BUSINESS_PHONE,
    INVOICES_DIR,
    RECEIPT_PREFIX,
    RECEIPTS_DIR,
    ensure_dirs,
)
from app import workspaces
from app.database import get_db, next_counter
from app.dates import parse_date
from app.models import (
    INVOICE_SELECT,
    PAYMENT_SELECT,
    invoice_to_dict,
    payment_to_dict,
)
from app.money import format_money

RUPEE = 0x20B9

# Candidate (regular, bold) font pairs, in preference order, across the
# platforms this app is expected to run on -- including a Linux container,
# which is where an AgentCore deployment would render.
FONT_CANDIDATES: list[tuple[str, str]] = [
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
]

# (regular name, bold name, whether the rupee sign is printable)
_resolved_fonts: tuple[str, str, bool] | None = None


def _font_has_rupee(path: str) -> bool:
    try:
        return RUPEE in TTFont("probe", path).face.charToGlyph
    except Exception:
        return False


def resolve_fonts() -> tuple[str, str, bool]:
    """Find and register a font pair that can print the rupee sign.

    Falls back to the Helvetica core fonts, which cannot, in which case the
    caller renders INR amounts with an ASCII prefix instead.
    """
    global _resolved_fonts
    if _resolved_fonts is not None:
        return _resolved_fonts

    for regular, bold in FONT_CANDIDATES:
        if not Path(regular).exists() or not _font_has_rupee(regular):
            continue
        bold_path = bold if Path(bold).exists() else regular
        try:
            pdfmetrics.registerFont(TTFont("FFSans", regular))
            pdfmetrics.registerFont(TTFont("FFSans-Bold", bold_path))
        except Exception:
            continue
        _resolved_fonts = ("FFSans", "FFSans-Bold", True)
        return _resolved_fonts

    _resolved_fonts = ("Helvetica", "Helvetica-Bold", False)
    return _resolved_fonts


def format_long_date(value) -> str:
    """Render a date the way an invoice reads: 'September 5, 2026'."""
    if not value:
        return ""
    d = parse_date(value)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _draw_labelled_block(
    c, x: float, y: float, label: str, lines: list[str], fonts, width: float
) -> float:
    """Draw a titled block of text and return the y below it."""
    regular, bold, _ = fonts
    c.setFont(bold, 8)
    c.setFillGray(0.45)
    c.drawString(x, y, label.upper())
    c.setFillGray(0)
    y -= 6 * mm
    for i, line in enumerate(lines):
        if not line:
            continue
        c.setFont(bold if i == 0 else regular, 11 if i == 0 else 9.5)
        c.setFillGray(0 if i == 0 else 0.3)
        for wrapped in _wrap(line, c, width, bold if i == 0 else regular,
                             11 if i == 0 else 9.5):
            c.drawString(x, y, wrapped)
            y -= 4.8 * mm
    c.setFillGray(0)
    return y


def _wrap(text: str, c, width: float, font: str, size: float) -> list[str]:
    """Greedy wrap so a long address cannot run off the page."""
    words = str(text).split()
    if not words:
        return []
    lines, current = [], words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if c.stringWidth(trial, font, size) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_invoice_pdf(invoice: dict, path: Path) -> Path:
    """Draw one invoice to `path`. Every figure comes from `invoice`."""
    regular, bold, has_rupee = resolve_fonts()
    fonts = (regular, bold, has_rupee)
    ascii_symbol = not has_rupee

    def money(minor: int) -> str:
        return format_money(minor, invoice["currency"], ascii_symbol=ascii_symbol)

    page_width, page_height = A4
    margin = 20 * mm
    right = page_width - margin
    column = (page_width - 2 * margin - 10 * mm) / 2

    path.parent.mkdir(parents=True, exist_ok=True)
    c = pdfcanvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Invoice {invoice['invoice_number']}")
    c.setAuthor(BUSINESS_NAME)
    c.setSubject(invoice["project"])

    y = page_height - margin

    # --- masthead ---------------------------------------------------------
    c.setFont(bold, 13)
    c.drawString(margin, y, "FREELANCEFLOW")
    c.setFont(bold, 22)
    c.drawRightString(right, y + 1 * mm, "INVOICE")
    c.setFont(regular, 11)
    c.setFillGray(0.35)
    c.drawRightString(right, y - 7 * mm, f"#{invoice['invoice_number']}")
    c.setFillGray(0)

    y -= 14 * mm
    c.setLineWidth(0.75)
    c.line(margin, y, right, y)
    y -= 10 * mm

    # --- parties ----------------------------------------------------------
    from_lines = [BUSINESS_NAME, BUSINESS_EMAIL, BUSINESS_PHONE, BUSINESS_ADDRESS]
    bill_lines = [
        invoice["client_name"],
        invoice.get("client_email") or "",
        invoice.get("client_phone") or "",
        invoice.get("client_address") or "",
    ]
    left_y = _draw_labelled_block(c, margin, y, "From", from_lines, fonts, column)
    right_y = _draw_labelled_block(
        c, margin + column + 10 * mm, y, "Bill To", bill_lines, fonts, column
    )
    y = min(left_y, right_y) - 6 * mm

    # --- project ----------------------------------------------------------
    project_lines = [invoice["project"]]
    if invoice.get("description"):
        project_lines.append(invoice["description"])
    y = _draw_labelled_block(
        c, margin, y, "Project", project_lines, fonts, page_width - 2 * margin
    )
    y -= 6 * mm

    # --- totals -----------------------------------------------------------
    c.setLineWidth(0.5)
    c.line(margin, y, right, y)
    y -= 8 * mm

    rows = [
        ("Subtotal", money(invoice["amount_minor"])),
        ("Paid", money(invoice["amount_paid_minor"])),
    ]
    for label, value in rows:
        c.setFont(regular, 10.5)
        c.setFillGray(0.3)
        c.drawString(margin, y, label)
        c.setFillGray(0)
        c.drawRightString(right, y, value)
        y -= 6.5 * mm

    y -= 1 * mm
    c.setLineWidth(0.5)
    c.line(page_width / 2, y, right, y)
    y -= 7 * mm
    c.setFont(bold, 12)
    c.drawString(margin, y, "Amount Due")
    c.drawRightString(right, y, money(invoice["outstanding_minor"]))
    y -= 6 * mm
    c.setLineWidth(0.75)
    c.line(margin, y, right, y)
    y -= 12 * mm

    # --- dates and status -------------------------------------------------
    c.setFont(regular, 10)
    c.setFillGray(0.3)
    c.drawString(margin, y, f"Issue Date: {format_long_date(invoice['issue_date'])}")
    y -= 5.5 * mm
    if invoice.get("due_date"):
        c.drawString(margin, y, f"Due Date: {format_long_date(invoice['due_date'])}")
        y -= 5.5 * mm

    c.setFillGray(0)
    c.setFont(bold, 10)
    status = str(invoice["invoice_status"]).replace("_", " ")
    c.drawString(margin, y, f"Payment Status: {status}")
    if invoice.get("is_overdue"):
        c.setFont(regular, 10)
        c.drawRightString(right, y, f"Overdue by {invoice['days_overdue']} days")

    # --- footer -----------------------------------------------------------
    c.setFont(regular, 8)
    c.setFillGray(0.5)
    c.drawCentredString(
        page_width / 2, margin - 4 * mm, f"Invoice {invoice['invoice_number']}"
    )

    c.showPage()
    c.save()
    return path


def create_invoice_pdf(invoice_id: int, output_dir: Path | None = None) -> dict:
    """Generate the PDF for one invoice.

    Reads the invoice and its client from SQLite, computes the balance from the
    payment ledger, and writes data/invoices/<number>.pdf. Re-running it
    regenerates the file, so a PDF can be refreshed after a payment lands.

    Returns status "created" with the path, or "not_found" / "error".
    """
    ensure_dirs()
    with get_db() as conn:
        row = conn.execute(
            INVOICE_SELECT + " WHERE i.id = ?", (invoice_id,)
        ).fetchone()
        if not row:
            return {"status": "not_found", "invoice_id": invoice_id}

        invoice = invoice_to_dict(row)
        invoice.update(
            {
                "client_email": row["client_email"],
                "client_phone": row["client_phone"],
                "client_address": row["client_address"],
            }
        )

        directory = Path(output_dir) if output_dir else (workspaces.invoices_dir() or INVOICES_DIR)
        path = directory / f"{invoice['invoice_number']}.pdf"

        try:
            render_invoice_pdf(invoice, path)
        except Exception as exc:  # a failed render must not claim success
            return {
                "status": "error",
                "invoice_id": invoice_id,
                "invoice_number": invoice["invoice_number"],
                "error": f"Could not generate the PDF: {exc}",
            }

        conn.execute(
            "UPDATE invoices SET pdf_path = ? WHERE id = ?", (str(path), invoice_id)
        )

    return {
        "status": "created",
        "invoice_id": invoice_id,
        "invoice_number": invoice["invoice_number"],
        "pdf_path": str(path),
    }


# --- receipts -------------------------------------------------------------


class ReceiptRenderFailed(Exception):
    """Raised inside the transaction so a failed render returns the number."""

    def __init__(self, receipt_number: str, cause: Exception):
        self.receipt_number = receipt_number
        self.cause = cause
        super().__init__(str(cause))


def format_receipt_number(sequence: int) -> str:
    """Render a counter value as a receipt number, e.g. 4 becomes RC-0004."""
    return f"{RECEIPT_PREFIX}-{sequence:04d}"


def render_receipt_pdf(payment: dict, receipt_number: str, path: Path) -> Path:
    """Draw one receipt to `path`. Every figure comes from `payment`."""
    regular, bold, has_rupee = resolve_fonts()
    fonts = (regular, bold, has_rupee)
    ascii_symbol = not has_rupee

    def money(minor: int) -> str:
        return format_money(minor, payment["currency"], ascii_symbol=ascii_symbol)

    page_width, page_height = A4
    margin = 20 * mm
    right = page_width - margin
    column = (page_width - 2 * margin - 10 * mm) / 2

    path.parent.mkdir(parents=True, exist_ok=True)
    c = pdfcanvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Receipt {receipt_number}")
    c.setAuthor(BUSINESS_NAME)
    c.setSubject(f"Payment for invoice {payment['invoice_number']}")

    y = page_height - margin

    # --- masthead ---------------------------------------------------------
    c.setFont(bold, 13)
    c.drawString(margin, y, "FREELANCEFLOW")
    c.setFont(bold, 22)
    c.drawRightString(right, y + 1 * mm, "RECEIPT")
    c.setFont(regular, 11)
    c.setFillGray(0.35)
    c.drawRightString(right, y - 7 * mm, f"#{receipt_number}")
    c.setFillGray(0)

    y -= 14 * mm
    c.setLineWidth(0.75)
    c.line(margin, y, right, y)
    y -= 10 * mm

    # --- parties ----------------------------------------------------------
    received_from = [
        payment["client_name"],
        payment.get("client_email") or "",
        payment.get("client_phone") or "",
        payment.get("client_address") or "",
    ]
    received_by = [BUSINESS_NAME, BUSINESS_EMAIL, BUSINESS_PHONE, BUSINESS_ADDRESS]
    left_y = _draw_labelled_block(
        c, margin, y, "Received From", received_from, fonts, column
    )
    right_y = _draw_labelled_block(
        c, margin + column + 10 * mm, y, "Received By", received_by, fonts, column
    )
    y = min(left_y, right_y) - 6 * mm

    # --- what it was for --------------------------------------------------
    y = _draw_labelled_block(
        c,
        margin,
        y,
        "For",
        [payment["project"], f"Invoice {payment['invoice_number']}"],
        fonts,
        page_width - 2 * margin,
    )
    y -= 6 * mm

    # --- the amount received ----------------------------------------------
    c.setLineWidth(0.75)
    c.line(margin, y, right, y)
    y -= 9 * mm
    c.setFont(bold, 12)
    c.drawString(margin, y, "Amount Received")
    c.drawRightString(right, y, money(payment["amount_minor"]))
    y -= 6 * mm
    c.setLineWidth(0.75)
    c.line(margin, y, right, y)
    y -= 11 * mm

    # --- where that leaves the invoice ------------------------------------
    for label, value in (
        ("Invoice Total", money(payment["invoice_amount_minor"])),
        ("Paid to Date", money(payment["paid_to_date_minor"])),
        ("Balance", money(payment["outstanding_after_minor"])),
    ):
        c.setFont(regular, 10.5)
        c.setFillGray(0.3)
        c.drawString(margin, y, label)
        c.setFillGray(0)
        c.drawRightString(right, y, value)
        y -= 6.5 * mm

    y -= 5 * mm

    # --- how it arrived ---------------------------------------------------
    c.setFont(regular, 10)
    c.setFillGray(0.3)
    c.drawString(margin, y, f"Payment Date: {format_long_date(payment['payment_date'])}")
    y -= 5.5 * mm
    if payment.get("method"):
        c.drawString(margin, y, f"Method: {payment['method']}")
        y -= 5.5 * mm
    if payment.get("reference"):
        c.drawString(margin, y, f"Reference: {payment['reference']}")
        y -= 5.5 * mm

    c.setFillGray(0)
    c.setFont(bold, 10)
    if payment["outstanding_after_minor"] <= 0:
        c.drawString(margin, y, "Invoice settled in full. Thank you.")
    else:
        balance = money(payment["outstanding_after_minor"])
        c.drawString(margin, y, f"Balance outstanding: {balance}")

    # --- footer -----------------------------------------------------------
    c.setFont(regular, 8)
    c.setFillGray(0.5)
    c.drawCentredString(
        page_width / 2,
        margin - 4 * mm,
        f"Receipt {receipt_number} for invoice {payment['invoice_number']}",
    )

    c.showPage()
    c.save()
    return path


def create_receipt_pdf(
    payment_id: int, output_dir: Path | None = None, regenerate: bool = False
) -> dict:
    """Generate the receipt document for a recorded payment.

    A receipt exists only against a real payment row, and a payment keeps one
    receipt number for life. The number is reserved in the same transaction as
    the render, so a failed render gives it back rather than leaving a gap.
    """
    ensure_dirs()
    try:
        with get_db() as conn:
            row = conn.execute(
                PAYMENT_SELECT + " WHERE p.id = ?", (payment_id,)
            ).fetchone()
            if not row:
                return {"status": "not_found", "payment_id": payment_id}

            payment = payment_to_dict(row)
            payment.update(
                {
                    "client_email": row["client_email"],
                    "client_phone": row["client_phone"],
                    "client_address": row["client_address"],
                }
            )

            existing_number = payment["receipt_number"]
            if existing_number and not regenerate:
                return {
                    "status": "already_exists",
                    "payment_id": payment_id,
                    "invoice_number": payment["invoice_number"],
                    "receipt_number": existing_number,
                    "receipt_path": payment["receipt_path"],
                    "hint": (
                        "This payment already has a receipt. Pass regenerate "
                        "only to redraw that same receipt number."
                    ),
                }

            receipt_number = existing_number or format_receipt_number(
                next_counter(conn, "receipt")
            )
            directory = Path(output_dir) if output_dir else (workspaces.receipts_dir() or RECEIPTS_DIR)
            path = directory / f"{receipt_number}.pdf"

            try:
                render_receipt_pdf(payment, receipt_number, path)
            except Exception as exc:
                raise ReceiptRenderFailed(receipt_number, exc) from exc

            conn.execute(
                "UPDATE payments SET receipt_number = ?, receipt_path = ? WHERE id = ?",
                (receipt_number, str(path), payment_id),
            )
    except ReceiptRenderFailed as failure:
        return {
            "status": "error",
            "payment_id": payment_id,
            "error": f"Could not generate the receipt: {failure.cause}",
        }

    return {
        "status": "created",
        "payment_id": payment_id,
        "invoice_number": payment["invoice_number"],
        "receipt_number": receipt_number,
        "receipt_path": str(path),
    }
