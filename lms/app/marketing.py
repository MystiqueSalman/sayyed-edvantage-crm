"""Phase 11 — Marketing suite logic (§20).

Attribution cookies, enrollment attribution, affiliate commission,
campaign helpers and email-campaign sending. Public landing pages live
in routes_marketing.py; this module holds the pure logic so tests can
drive it directly.
"""
import secrets
from datetime import datetime

from flask import request

from . import db
from .models import (Affiliate, AffiliateClick, AffiliateEarning,
                     AffiliatePayout, Course, EmailCampaign, EmailSettings,
                     Enrollment, LandingPage, Lead, MessageTemplate, PageView,
                     User)

AFF_COOKIE = "se_aff"
CAMP_COOKIE = "se_camp"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# ---------------------------------------------------------------- attribution helpers

def _get_cookie(name):
    try:
        return (request.cookies.get(name) or "").strip() or None
    except Exception:
        return None


def get_attribution():
    """Read affiliate/campaign attribution from the current request cookies."""
    return {"affiliate_code": _get_cookie(AFF_COOKIE),
            "campaign_id": _get_cookie(CAMP_COOKIE)}


def resolve_affiliate(code):
    if not code:
        return None
    aff = Affiliate.query.filter_by(code=code.upper(), active=True).first()
    return aff


def attribute_enrollment(enrollment):
    """Stamp source/campaign/affiliate on a paid (or free) enrollment.

    Priority: affiliate cookie > campaign cookie > lead match.
    Idempotent — never overwrites an existing attribution.
    """
    if enrollment.source:
        return enrollment
    aff = resolve_affiliate(_get_cookie(AFF_COOKIE))
    camp_id = _get_cookie(CAMP_COOKIE)
    if aff:
        enrollment.affiliate_id = aff.id
        enrollment.source = Lead.SOURCE_AFFILIATE
    elif camp_id:
        enrollment.campaign_id = int(camp_id)
        enrollment.source = Lead.SOURCE_CAMPAIGN
    else:
        # Fall back to the student's most recent lead for this course.
        lead = (Lead.query.filter_by(converted_user_id=enrollment.user_id,
                                     course_id=enrollment.course_id)
                .order_by(Lead.created_at.desc()).first())
        if lead:
            enrollment.source = lead.source or ""
            enrollment.campaign_id = lead.campaign_id
            enrollment.affiliate_id = lead.affiliate_id
    return enrollment


def record_affiliate_earning(enrollment):
    """Create the commission row for a paid affiliate-attributed enrollment.

    Called once the enrollment is paid. Returns the earning or None.
    """
    if not enrollment.paid or not enrollment.affiliate_id:
        return None
    if AffiliateEarning.query.filter_by(
            enrollment_id=enrollment.id).first():
        return None  # already recorded
    aff = db.session.get(Affiliate, enrollment.affiliate_id)
    if not aff or not aff.active:
        return None
    earning = AffiliateEarning(
        affiliate_id=aff.id, enrollment_id=enrollment.id,
        amount=aff.commission_for(enrollment.amount_paid or 0))
    db.session.add(earning)
    db.session.commit()
    return earning


def new_affiliate_code(prefix="AF"):
    for _ in range(20):
        code = prefix + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not Affiliate.query.filter_by(code=code).first():
            return code
    raise RuntimeError("could not generate unique affiliate code")


# ---------------------------------------------------------------- landing pages

BLOCK_TYPES = ("hero", "course_cards", "testimonials", "faq", "countdown",
               "cta")


def starter_blocks():
    """Template starter blocks so Salman can launch a page in minutes."""
    return [
        {"type": "hero", "heading": "Learn Job-Ready IT Skills",
         "text": "Live online courses with mentorship, projects and "
                 "placement support.",
         "button_text": "Book Free Demo", "button_link": "#lead-form"},
        {"type": "course_cards", "heading": "Popular Courses",
         "course_ids": []},
        {"type": "testimonials", "heading": "Student Stories",
         "items": [{"name": "Your student", "text": "Add a real testimonial "
                                                    "here."}]},
        {"type": "faq", "heading": "FAQs",
         "items": [{"q": "Are classes live?", "a": "Yes — live online with "
                                                     "recordings."}]},
        {"type": "countdown", "heading": "Offer ends in",
         "ends_at": "", "text": "Limited seats per batch."},
        {"type": "cta", "heading": "Get a callback",
         "text": "Share your details and our counsellor will call you.",
         "button_text": "Request Callback"},
    ]


def record_page_view(page, campaign_id=None):
    db.session.add(PageView(landing_page_id=page.id,
                             campaign_id=campaign_id))
    page.views = (page.views or 0) + 1
    db.session.commit()


def create_lead_from_landing(form, page, campaign_id=None, affiliate=None):
    """Create a CRM lead from a landing-page form. Never invents data."""
    name = (form.get("name") or "").strip()
    phone = (form.get("phone") or "").strip()
    email = (form.get("email") or "").strip()
    course_id = form.get("course_id") or None
    try:
        course_id = int(course_id) if course_id else None
    except (TypeError, ValueError):
        course_id = None
    if not name or not phone:
        return None, "Please share your name and phone number."
    source = Lead.SOURCE_LANDING
    if campaign_id:
        source = Lead.SOURCE_CAMPAIGN
    elif affiliate:
        source = Lead.SOURCE_AFFILIATE
    lead = Lead(name=name, phone=phone, email=email, source=source,
                course_id=course_id,
                campaign_id=campaign_id,
                affiliate_id=affiliate.id if affiliate else None,
                follow_up_date=None)
    db.session.add(lead)
    db.session.flush()
    lead.log("system",
             f"Landing page: {page.title} (/{page.slug})"
             + (f" · campaign #{campaign_id}" if campaign_id else "")
             + (f" · affiliate {affiliate.code}" if affiliate else ""))
    db.session.commit()
    try:
        from .hardening import emit_lead_created  # webhook lead.created
        emit_lead_created(lead)
    except Exception:
        pass
    return lead, None


# ---------------------------------------------------------------- email campaigns (§20.5)

def email_gate_ok():
    """Mirror of the Phase 2 SMTP gate: host + from + enabled."""
    s = EmailSettings.get()
    return bool(s and s.enabled and s.smtp_host and s.from_email)


def campaign_recipients(campaign):
    """Resolve recipient emails from the segment. Leads + students."""
    seg = campaign.segment or {}
    audience = seg.get("audience", "leads")
    out = []
    if audience == "leads":
        q = Lead.query.filter(Lead.email != "")
        if seg.get("course_id"):
            q = q.filter(Lead.course_id == int(seg["course_id"]))
        if seg.get("status"):
            q = q.filter(Lead.status == seg["status"])
        out = [(l.name, l.email) for l in q.all()]
    else:
        q = User.query.filter(User.role == "student",
                              User.email != "")
        if seg.get("course_id"):
            q = q.join(Enrollment,
                       Enrollment.user_id == User.id).filter(
                Enrollment.course_id == int(seg["course_id"]))
        out = [(u.name, u.email) for u in q.all()]
    # de-dupe by email
    seen, uniq = set(), []
    for name, email in out:
        key = email.strip().lower()
        if key and key not in seen:
            seen.add(key)
            uniq.append((name, email))
    return uniq


def render_campaign_body(campaign, name):
    tpl = campaign.template
    if not tpl:
        return "", ""
    from .hardening import render_template_string  # Phase 10 sandboxed renderer
    subject = render_template_string(tpl.subject or campaign.name,
                                     {"name": name})
    body = render_template_string(tpl.body or "",
                                  {"name": name,
                                   "campaign": campaign.name})
    return subject, body


def send_email_campaign(campaign):
    """Send the campaign. Refuses when SMTP is not configured (gate)."""
    if campaign.status == "sent":
        return False, "Campaign already sent."
    if not email_gate_ok():
        return False, ("Email is not configured — enable SMTP in Email "
                        "Automation first.")
    from .emailer import send_email_async
    recipients = campaign_recipients(campaign)
    for name, email in recipients:
        subject, body = render_campaign_body(campaign, name or "there")
        try:
            send_email_async(email, subject, body)
        except Exception:
            continue  # one bad address must not stop the blast
    campaign.status = "sent"
    campaign.sent_count = len(recipients)
    campaign.sent_at = datetime.utcnow()
    db.session.commit()
    return True, f"Sent to {len(recipients)} recipient(s)."
