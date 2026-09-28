"""Phase 13 - Stream 6 (parked pre-launch fixes).

Part A: hardened website-chat -> CRM lead capture used by /api/chat.

The old block wrapped the ENTIRE capture path in one bare
``except Exception: db.session.rollback()``. Any failure anywhere — a bogus
flag value, a transient DB error, an enrichment-step exception AFTER the lead
row was already added — rolled the lead row back too and left zero trace, so
on production leads silently never appeared.

The new path keeps the original semantics (same lead resolution, same
timeline texts, same scoring) but:

  1. validates name / phone / course BEFORE any write;
  2. commits the lead row in a TIGHT transaction first, so a later enrichment
     failure can never roll the lead back away again;
  3. logs every failure server-side with a "CHAT-LEAD" prefix via app.logger
     AND persists it to LeadCaptureLog13 (bounded to 30 days);
  4. updates (never duplicates) the lead that already owns the phone number.

capture_chat_lead() never raises; it returns the Lead or None.

Part B: admin-only diagnostics page /admin/diagnostics/chat-leads showing the
20 most recent website-chat leads (Lead.source == 'chat', set at creation)
plus the 20 most recent LeadCaptureLog13 errors.

Blueprint registration (coordinator: add to create_app() in app/__init__.py,
which this stream must not edit):

    from .parked13 import parked13_bp  # noqa: E402
    ...
    app.register_blueprint(parked13_bp)
"""
import re
import traceback
from datetime import date

from flask import Blueprint, current_app, render_template

from . import db
from .decorators import admin_required
from .models import Course, Lead
from .models13_parked import LeadCaptureLog13, log_capture_error

parked13_bp = Blueprint("parked13", __name__)

# Names that mean "we don't know the visitor's name yet".
PLACEHOLDER_NAMES = ("Chat visitor", "")

_PHONE_DIGITS_RE = re.compile(r"^([6-9]\d{9})$")


def normalize_chat_phone(raw):
    """Normalize a chat phone flag to 10 digits, or None when invalid.

    The chat regex already yields 10 digits, but production input has proved
    messier than the regex (spaces, dashes, stray +91/0 prefixes), so the
    write path normalizes defensively instead of trusting the flag.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    for prefix in ("91", "0"):
        if digits.startswith(prefix) and len(digits) == len(prefix) + 10:
            digits = digits[len(prefix):]
            break
    return digits if _PHONE_DIGITS_RE.match(digits) else None


def validate_chat_name(raw):
    """Strip/length-check the chat name flag; None when there is no real name."""
    name = (raw or "").strip()
    return name[:120] or None


def resolve_chat_course(course_id):
    """Return the Course for a chat flag course_id, or None.

    A bogus course_id used to ride straight into Lead(course_id=...) and could
    poison the write; now it is validated and the incident is logged.
    """
    if not course_id:
        return None
    try:
        course = Course.query.get(int(course_id))
    except (TypeError, ValueError):
        course = None
    if course is None:
        current_app.logger.warning(
            "CHAT-LEAD stage=validate unknown course_id=%r", course_id)
        log_capture_error(
            "validate", "",
            f"unknown course_id={course_id!r}; continuing without course",
            "")
    return course


def _payload_summary(conv, flags, phone=None):
    parts = [f"conv={conv.id[:8]}"]
    if phone:
        parts.append(f"phone={phone}")
    for key in ("name", "course_id", "fee_asked", "high_intent"):
        val = flags.get(key)
        if val not in (None, "", False):
            parts.append(f"{key}={str(val)[:40]}")
    return " ".join(parts)[:2000]


def _mark_name(lead, name):
    """Replace a placeholder name with the visitor's real name (timeline-logged)."""
    if name and (lead.name or "") in PLACEHOLDER_NAMES:
        lead.name = name
        lead.log("system", f"Visitor name updated to {name} via AI chat.")


def capture_chat_lead(conv, flags):
    """Hardened replacement for the /api/chat lead-capture block.

    Preserves the original semantics exactly; see module docstring for what
    changed. Never raises. Returns the Lead or None.
    """
    # Lazy imports: routes_crm imports this module inside the chat() view, so
    # module-level imports here would be circular.
    from .crm import create_lead, refresh_score
    from .routes_crm import _apply_chat_course, _sync_chat_transcript

    log = current_app.logger
    cid = conv.id
    flags = flags or {}

    # ---- stage: fee_asks intent counter (outside the lead transaction) ----
    try:
        if flags.get("fee_asked"):
            conv.fee_asks = (conv.fee_asks or 0) + 1
            db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("CHAT-LEAD stage=fee_asks conv=%s failed", cid[:8])
        log_capture_error("fee_asks", cid[:8], traceback.format_exc(limit=3),
                          _payload_summary(conv, flags))

    # ---- stage: validate BEFORE any write ----
    raw_phone = flags.get("phone")
    phone = normalize_chat_phone(raw_phone)
    if raw_phone and not phone:
        log.warning("CHAT-LEAD stage=validate conv=%s bad phone=%r",
                    cid[:8], raw_phone)
        log_capture_error(
            "validate", str(raw_phone)[:120],
            "phone failed validation (expected 10 digits starting 6-9)",
            _payload_summary(conv, flags))
    name = validate_chat_name(flags.get("name"))
    course = resolve_chat_course(flags.get("course_id"))
    course_id = course.id if course else None

    try:
        lead = conv.lead or None
    except Exception:
        log.exception("CHAT-LEAD stage=write conv=%s conv.lead lookup failed",
                      cid[:8])
        lead = None

    # ---- stage: write — tight transaction, the lead row lands HERE ----
    try:
        if phone:
            if lead is not None and not (lead.phone or "").strip():
                # Same visitor, same conversation: attach the number to the
                # already-linked lead instead of spawning a second lead.
                other = (Lead.query
                         .filter(Lead.phone == phone, Lead.id != lead.id)
                         .first())
                if other is not None:
                    # Number already belongs to another lead — adopt that lead
                    # so the transcript follows the phone-identified person.
                    lead.log("system",
                             f"Visitor shared number {phone}; chat moved to "
                             f"existing lead #{other.id}.")
                    conv.lead_id = other.id
                    lead = other
                else:
                    lead.phone = phone
                    lead.log("system",
                             f"Visitor shared number {phone} in AI chat.")
            if lead is None or (lead.phone or "").strip() != phone:
                note = "Shared number in AI chat."
                if course:
                    note += f" Interested: {course.title}."
                # create_lead dedups by phone: adopt whichever lead owns the
                # number so the transcript stays with the right person.
                lead = create_lead(name=name or "Chat visitor",
                                   phone=phone, source=Lead.SOURCE_CHAT,
                                   course_id=course_id, note=note)
                conv.lead_id = lead.id
        elif name and lead and (lead.name or "") in PLACEHOLDER_NAMES:
            _mark_name(lead, name)

        if flags.get("high_intent") or (conv.fee_asks or 0) >= 2:
            if lead is None:
                note = "High-intent chat visitor (no phone yet)."
                if course:
                    note += f" Interested: {course.title}."
                lead = create_lead(name=name or "Chat visitor",
                                   source=Lead.SOURCE_CHAT,
                                   course_id=course_id, note=note)
                if not conv.lead_id:
                    conv.lead_id = lead.id
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("CHAT-LEAD stage=write conv=%s phone=%s FAILED; "
                      "lead NOT saved", cid[:8], phone)
        log_capture_error("write", phone or cid[:8],
                          traceback.format_exc(limit=5),
                          _payload_summary(conv, flags, phone))
        return None

    try:
        lead_id = lead.id if lead is not None else None
    except Exception:
        lead_id = None
    log.info("CHAT-LEAD stage=write conv=%s ok lead_id=%s phone=%s",
             cid[:8], lead_id, phone)

    # ---- stage: enrich — must NEVER destroy the lead row ----
    try:
        fee_count = conv.fee_asks or 0
        wants_high_intent = bool(flags.get("high_intent")) or fee_count >= 2
        if phone and lead is not None:
            _mark_name(lead, name)
            _apply_chat_course(lead, course_id)
            lead.follow_up_date = date.today()
            lead.log("system", "AI chat flagged HIGH-INTENT (phone shared).")
            lead.score = Lead.SCORE_HOT
        if wants_high_intent and lead is not None:
            _mark_name(lead, name)
            _apply_chat_course(lead, course_id)
            lead.log("system", "AI chat flagged HIGH-INTENT.")
            lead.score = Lead.SCORE_HOT
            if not lead.follow_up_date:
                lead.follow_up_date = date.today()
        if lead is not None:
            refresh_score(lead)
        # Sync the website-chat transcript onto the lead timeline
        # (one entry per conversation, refreshed each message).
        if conv.lead_id:
            try:
                _sync_chat_transcript(conv)
            except Exception:
                log.exception("CHAT-LEAD stage=transcript conv=%s failed "
                              "(non-fatal)", cid[:8])
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("CHAT-LEAD stage=enrich conv=%s lead_id=%s FAILED "
                      "(lead row kept)", cid[:8], lead_id)
        log_capture_error("enrich", phone or cid[:8],
                          traceback.format_exc(limit=5),
                          _payload_summary(conv, flags, phone))
    return lead


# ============================================================ diagnostics UI


@parked13_bp.route("/admin/diagnostics/chat-leads")
@admin_required
def chat_leads_diagnostics():
    """Admin-only: the 20 most recent website-chat leads + the 20 most recent
    chat-lead capture errors. This is how the fix is verified on production."""
    leads = (Lead.query.filter(Lead.source == Lead.SOURCE_CHAT)
             .order_by(Lead.created_at.desc()).limit(20).all())
    errors = (LeadCaptureLog13.query
              .order_by(LeadCaptureLog13.created_at.desc()).limit(20).all())
    return render_template("admin_diagnostics_chat_leads.html",
                           leads=leads, errors=errors,
                           source_marker=Lead.SOURCE_CHAT)
