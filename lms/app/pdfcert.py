"""PDF certificate generation (reportlab)."""
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

NAVY = HexColor("#0a1628")
NAVY2 = HexColor("#101f3c")
GOLD = HexColor("#d4af37")
GOLD_LIGHT = HexColor("#f3d47c")
BLUE = HexColor("#2e86ff")
WHITE = HexColor("#ffffff")
MUTED = HexColor("#9fb3d1")


def generate_certificate_pdf(cert, out_path):
    """Render a premium dark/gold certificate PDF for a Certificate row."""
    w, h = landscape(A4)
    c = canvas.Canvas(out_path, pagesize=landscape(A4))

    # Background
    c.setFillColor(NAVY)
    c.rect(0, 0, w, h, stroke=0, fill=1)
    # subtle inner panel
    c.setFillColor(NAVY2)
    c.roundRect(28, 28, w - 56, h - 56, 18, stroke=0, fill=1)

    # Gold double border
    c.setStrokeColor(GOLD)
    c.setLineWidth(3)
    c.roundRect(40, 40, w - 80, h - 80, 12, stroke=1, fill=0)
    c.setStrokeColor(HexColor("#8a6d1f"))
    c.setLineWidth(1)
    c.roundRect(50, 50, w - 100, h - 100, 8, stroke=1, fill=0)

    cx = w / 2
    y = h - 120

    # SE monogram in gold circle (brand placeholder)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.circle(cx, y, 34, stroke=1, fill=0)
    c.setFillColor(GOLD_LIGHT)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(cx, y - 9, "SE")

    y -= 70
    c.setFillColor(GOLD_LIGHT)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(cx, y, "SAYYED EDVANTAGE")
    y -= 26
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawCentredString(cx, y, "EMPOWERING STUDENTS FOR SUCCESS")

    y -= 52
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(cx, y, "Certificate of Completion")

    y -= 40
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 12)
    c.drawCentredString(cx, y, "This certificate is proudly presented to")

    y -= 52
    c.setFillColor(GOLD_LIGHT)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(cx, y, cert.user.name)

    y -= 36
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 12)
    c.drawCentredString(cx, y, "for successfully completing the course")

    y -= 44
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(cx, y, cert.course.title)

    # gold divider
    y -= 30
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(cx - 120, y, cx + 120, y)

    y -= 34
    issued = cert.issued_at or datetime.utcnow()
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 11)
    c.drawCentredString(cx, y, f"Issued on {issued.strftime('%d %B %Y')}  •  Certificate ID: {cert.code}")

    # signature block
    y = 105
    c.setStrokeColor(MUTED)
    c.setLineWidth(1)
    c.line(cx - 170, y, cx - 20, y)
    c.line(cx + 20, y, cx + 170, y)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx - 95, y - 16, "Course Director")
    c.drawCentredString(cx + 95, y - 16, "Sayyed EdVantage")

    c.showPage()
    c.save()
    return out_path


def certificate_path(cert, upload_dir):
    d = os.path.join(upload_dir, "certificates")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"certificate_{cert.code}.pdf")
