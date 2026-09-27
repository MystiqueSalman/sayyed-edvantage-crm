"""Phase 4: CRM helpers — lead scoring, status transitions, lead creation hooks.

All functions are safe to call from request handlers; DB errors are left to
the caller (routes wrap user-facing flows in try/except where needed).
"""
from datetime import date

from . import db
from .models import Lead, LeadActivity


HIGH_INTENT_KEYWORDS = (
    "enroll", "enrol", "admission", "join now", "join", "pay", "payment",
    "call me", "contact me", "interested", "buy",
)


def create_lead(name="", phone="", email="", source=Lead.SOURCE_WEBSITE,
                course_id=None, actor_id=None, note=""):
    """Create a lead (dedup by phone) and log its creation."""
    phone = (phone or "").strip()
    lead = None
    if phone:
        lead = Lead.query.filter_by(phone=phone).first()
    if lead is None:
        lead = Lead(name=name.strip(), phone=phone, email=(email or "").strip(),
                    source=source, course_id=course_id)
        db.session.add(lead)
        db.session.flush()
        lead.log("system", f"Lead created via {source}." +
                 (f" {note}" if note else ""), actor_id=actor_id)
    return lead


def set_status(lead, new_status, actor_id=None, note=""):
    """Transition a lead's status, logging the change on its timeline."""
    new_status = (new_status or "").strip()
    if new_status not in Lead.PIPELINE:
        raise ValueError(f"invalid status: {new_status}")
    old = lead.status
    if old == new_status:
        return False
    lead.status = new_status
    old_label = Lead.LABELS.get(old, old)
    new_label = Lead.LABELS.get(new_status, new_status)
    text = f"Status: {old_label} → {new_label}." + (f" {note}" if note else "")
    lead.log("status", text, actor_id=actor_id)
    db.session.flush()
    return True


def add_note(lead, text, actor_id=None, follow_up=None):
    """Add a counsellor note; optionally (re)schedule the follow-up date."""
    lead.log("note", text, actor_id=actor_id)
    if follow_up:
        lead.follow_up_date = follow_up
        lead.log("followup", f"Follow-up set for {follow_up.isoformat()}.",
                 actor_id=actor_id)
    db.session.flush()


def score_lead(lead):
    """Rules-based Hot/Warm/Cold scoring.

    Hot: phone present AND a high-intent signal (keyword in notes/timeline,
    fee asked, or referral/chat origin with engagement).
    Warm: any engagement (note, follow-up set, status beyond New).
    Cold: everything else.
    """
    texts = " ".join(a.text.lower() for a in lead.activities).lower()
    has_phone = bool((lead.phone or "").strip())
    engaged = (lead.status != Lead.STATUS_NEW or lead.follow_up_date
               or any(a.kind in ("note", "followup") for a in lead.activities))
    hot_signal = (any(k in texts for k in HIGH_INTENT_KEYWORDS)
                  or "high-intent" in texts
                  or "fee" in texts and has_phone)
    if has_phone and hot_signal:
        return Lead.SCORE_HOT
    if engaged or has_phone:
        return Lead.SCORE_WARM
    return Lead.SCORE_COLD


def refresh_score(lead):
    """Recompute and persist the lead's score. Returns (old, new)."""
    old = lead.score
    new = score_lead(lead)
    if new != old:
        lead.score = new
        db.session.flush()
    return old, new


def todays_followups(user=None):
    """Leads with follow-up due today or overdue, optionally for one assignee."""
    q = Lead.query.filter(Lead.follow_up_date.isnot(None),
                          Lead.follow_up_date <= date.today(),
                          ~Lead.status.in_([Lead.STATUS_ENROLLED,
                                            Lead.STATUS_ADMITTED]))
    if user is not None:
        q = q.filter(Lead.assigned_to == user.id)
    return q.order_by(Lead.follow_up_date.asc()).all()


def funnel_stats():
    """Counts per pipeline stage + new→enrolled conversion %."""
    from sqlalchemy import func
    rows = (db.session.query(Lead.status, func.count(Lead.id))
            .group_by(Lead.status).all())
    counts = {s: 0 for s in Lead.PIPELINE}
    for status, n in rows:
        if status in counts:
            counts[status] = n
    new_n = counts[Lead.STATUS_NEW] or 1
    conversion = round(100 * counts[Lead.STATUS_ENROLLED] / max(
        1, sum(counts.values())), 1)
    return counts, conversion


def source_stats():
    from sqlalchemy import func
    rows = (db.session.query(Lead.source, func.count(Lead.id))
            .group_by(Lead.source).all())
    return {s or "unknown": n for s, n in rows}


def counsellor_stats():
    """Per-assignee lead counts + enrolled counts."""
    from sqlalchemy import func
    from .models import User
    rows = (db.session.query(User.id, User.name, func.count(Lead.id))
            .join(Lead, Lead.assigned_to == User.id)
            .group_by(User.id, User.name).all())
    out = []
    for uid, name, total in rows:
        enrolled = Lead.query.filter_by(assigned_to=uid,
                                        status=Lead.STATUS_ENROLLED).count()
        out.append({"id": uid, "name": name, "total": total,
                    "enrolled": enrolled})
    return sorted(out, key=lambda r: r["total"], reverse=True)


def referral_signup_lead(user, referrer_name=""):
    """Auto-create a CRM lead when a referral link drives a signup."""
    try:
        lead = create_lead(name=user.name, phone=user.phone or "",
                           email=user.email, source=Lead.SOURCE_REFERRAL,
                           note=f"Signed up via referral"
                           f"{' by ' + referrer_name if referrer_name else ''}.")
        if lead.score == Lead.SCORE_COLD:
            lead.score = Lead.SCORE_WARM
        lead.converted_user_id = user.id
        db.session.flush()
        return lead
    except Exception:
        return None
