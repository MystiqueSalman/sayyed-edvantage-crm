"""Phase 9 — professional invoice/receipt PDF generation (reportlab, §11.4)."""
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

NAVY = HexColor("#0a1628")
NAVY2 = HexColor("#101f3c")
GOLD = HexColor("#d4af37")
GOLD_LIGHT = HexColor("#f3d47c")
WHITE = HexColor("#ffffff")
MUTED = HexColor("#9fb3d1")
INK = HexColor("#1a2332")


def inr(n):
    return f"Rs. {int(n):,}"


def generate_invoice_pdf(invoice, settings, out_path):
    """Render a tax invoice PDF for an Invoice row + InvoiceSetting row."""
    w, h = A4
    c = canvas.Canvas(out_path, pagesize=A4)

    # Header band
    c.setFillColor(NAVY)
    c.rect(0, h - 150, w, 150, stroke=0, fill=1)
    c.setFillColor(GOLD_LIGHT)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, h - 55, settings.business_name or "Sayyed EdVantage")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    y = h - 75
    for line in (settings.address or "",):
        for part in line.split("\n"):
            if part.strip():
                c.drawString(40, y, part.strip()[:80])
                y -= 13
    c.drawString(40, y, f"{settings.email or ''}  |  {settings.phone or ''}")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 26)
    c.drawRightString(w - 40, h - 60, "TAX INVOICE")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 40, h - 82, f"No: {invoice.number}")
    c.drawRightString(
        w - 40, h - 98,
        f"Date: {(invoice.issued_at or datetime.utcnow()).strftime('%d %b %Y')}")
    if settings.gstin:
        c.drawRightString(w - 40, h - 114, f"GSTIN: {settings.gstin}")

    # Billed to
    y = h - 195
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Billed To")
    c.setFont("Helvetica", 10)
    y -= 18
    c.drawString(40, y, invoice.user.name or "")
    y -= 15
    c.drawString(40, y, invoice.user.email or "")
    if invoice.user.phone:
        y -= 15
        c.drawString(40, y, invoice.user.phone)

    # Table
    y -= 40
    c.setFillColor(NAVY2)
    c.rect(40, y - 6, w - 80, 30, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y + 6, "Description")
    c.drawRightString(w - 50, y + 6, "Amount")
    y -= 30
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"{invoice.course.title} — course fee")
    c.drawRightString(w - 50, y, inr(invoice.base_fee))
    y -= 22
    if invoice.discount:
        c.drawString(50, y, "Less: discount (coupon)")
        c.drawRightString(w - 50, y, f"− {inr(invoice.discount)}")
        y -= 22
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Taxable value")
    c.drawRightString(w - 50, y, inr(invoice.taxable))
    y -= 22
    gst_rate = invoice_breakdown_rate(invoice)
    c.drawString(50, y, f"GST @ {gst_rate:g}% (SAC {settings.sac_code})")
    c.drawRightString(w - 50, y, inr(invoice.gst_amount))
    y -= 30
    c.setFillColor(NAVY)
    c.rect(40, y - 10, w - 80, 34, stroke=0, fill=1)
    c.setFillColor(GOLD_LIGHT)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y + 2, "Total (incl. GST)")
    c.drawRightString(w - 50, y + 2, inr(invoice.total))

    # Footer
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(40, 70, "This is a computer-generated invoice. "
                         "Coaching services — SAC 999293.")
    if settings.notes:
        c.drawString(40, 56, settings.notes[:100])
    c.drawRightString(w - 40, 70, "Empowering Students for Success")
    c.save()


def invoice_breakdown_rate(invoice):
    if invoice.taxable:
        return round(100.0 * invoice.gst_amount / invoice.taxable, 2)
    return 0.0
