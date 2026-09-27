"""Phase 7 — ATS-friendly resume PDF (reportlab).

Clean single-column layout, standard fonts, real data only (assembled by
app/career.py from verified records). Subtle Sayyed EdVantage gold accent.
"""
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                Spacer)

NAVY = HexColor("#0a1628")
GOLD = HexColor("#b8912a")
DARK = HexColor("#1a1a1a")
GREY = HexColor("#555555")
LIGHT_GREY = HexColor("#888888")

_H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22,
                     textColor=NAVY, spaceAfter=2)
_HEADLINE = ParagraphStyle("headline", fontName="Helvetica", fontSize=11,
                           textColor=GREY, spaceAfter=4)
_CONTACT = ParagraphStyle("contact", fontName="Helvetica", fontSize=9,
                          textColor=GREY, spaceAfter=6)
_SEC = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=12,
                      textColor=NAVY, spaceBefore=10, spaceAfter=4)
_ITEM_T = ParagraphStyle("itemt", fontName="Helvetica-Bold", fontSize=10,
                         textColor=DARK, spaceBefore=4, spaceAfter=1)
_ITEM = ParagraphStyle("item", fontName="Helvetica", fontSize=9.5,
                       textColor=DARK, leading=13, spaceAfter=2)
_META = ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5,
                       textColor=LIGHT_GREY, spaceAfter=1)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5,
                       textColor=DARK, leading=13, spaceAfter=4)


def _esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_resume_pdf(sections, out_path):
    """Render the resume PDF from career.resume_sections() output."""
    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)
    story = []
    r = sections["resume"]

    story.append(Paragraph(_esc(sections["name"]), _H1))
    if sections["headline"]:
        story.append(Paragraph(_esc(sections["headline"]), _HEADLINE))
    contact = " &nbsp;|&nbsp; ".join(
        x for x in [sections["email"], sections["phone"]] if x)
    links = sections.get("links", {})
    for label in ("github", "linkedin", "website"):
        if links.get(label):
            contact += f" &nbsp;|&nbsp; {_esc(label.title())}: {_esc(links[label])}"
    if contact:
        story.append(Paragraph(contact, _CONTACT))
    story.append(HRFlowable(width="100%", thickness=1.2, color=GOLD,
                            spaceAfter=6))

    if sections["summary"]:
        story.append(Paragraph("PROFESSIONAL SUMMARY", _SEC))
        story.append(Paragraph(_esc(sections["summary"]), _BODY))

    skills = sections["verified_skills"] + [s for s in sections["self_skills"]
                                            if s.lower() not in
                                            [x.lower() for x in sections["verified_skills"]]]
    if skills:
        story.append(Paragraph("SKILLS", _SEC))
        story.append(Paragraph(_esc(", ".join(skills)), _BODY))

    if sections["courses"]:
        story.append(Paragraph("COURSES", _SEC))
        for c in sections["courses"]:
            badge = " ✓ Verified" if c["completed"] else ""
            story.append(Paragraph(
                f"{_esc(c['title'])}<font color=\"#b8912a\" size=\"8\">"
                f"{badge}</font>", _ITEM_T))
            story.append(Paragraph(
                f"Sayyed EdVantage — {c['status'].title()}, "
                f"{c['progress']}% complete", _META))

    if sections["projects"]:
        story.append(Paragraph("PROJECTS", _SEC))
        for p in sections["projects"]:
            story.append(Paragraph(
                f"{_esc(p['title'])}<font color=\"#b8912a\" size=\"8\">"
                f" ✓ Verified</font>", _ITEM_T))
            if p["skills"]:
                story.append(Paragraph(
                    f"Skills: {_esc(', '.join(p['skills']))}", _META))
            if p["url"]:
                story.append(Paragraph(f"Link: {_esc(p['url'])}", _META))

    if sections["certificates"]:
        story.append(Paragraph("CERTIFICATIONS", _SEC))
        for c in sections["certificates"]:
            story.append(Paragraph(
                f"{_esc(c['course'])}<font color=\"#b8912a\" size=\"8\">"
                f" ✓ Verified</font>", _ITEM_T))
            story.append(Paragraph(
                f"Sayyed EdVantage — Certificate { _esc(c['code'])} "
                f"({c['issued']})", _META))

    if sections["experience"]:
        story.append(Paragraph("EXPERIENCE", _SEC))
        for e in sections["experience"]:
            story.append(Paragraph(
                f"{_esc(e.get('title', ''))} — {_esc(e.get('org', ''))}",
                _ITEM_T))
            if e.get("period"):
                story.append(Paragraph(_esc(e["period"]), _META))
            if e.get("details"):
                story.append(Paragraph(_esc(e["details"]), _ITEM))

    if sections["education"]:
        story.append(Paragraph("EDUCATION", _SEC))
        for e in sections["education"]:
            story.append(Paragraph(
                f"{_esc(e.get('degree', ''))} — {_esc(e.get('school', ''))}",
                _ITEM_T))
            if e.get("year"):
                story.append(Paragraph(_esc(e["year"]), _META))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"Generated by Sayyed EdVantage on "
        f"{datetime.utcnow().strftime('%d %B %Y')}", _META))

    doc.build(story)
    return out_path


def resume_path(user_id, upload_dir):
    d = os.path.join(upload_dir, "resumes")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"resume_{user_id}.pdf")
