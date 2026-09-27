"""Phase 9 — Faculty & operations logic (§4.3, §4.6, §18.3, §18.4, §18.6, §11.4–11.5).

Central helpers for: audit logging, attendance, the granular permission
matrix, batches, invoices/finance, and calendar event aggregation.
"""
from datetime import datetime, timedelta

from . import db
from .models import (Assignment, AuditLog, Batch, BatchMember, Challenge,
                     Coupon, Course, Enrollment, Invoice, InvoiceSetting,
                     LiveSession, Module, Project, Quiz, Refund,
                     RolePermission, SessionAttendance, User)

# ---------------------------------------------------------------- audit logs (§18.6)

AUDIT_ACTIONS = (
    "user.role_change", "user.toggle",
    "coupon.create", "coupon.toggle", "coupon.delete",
    "batch.create", "batch.enroll", "batch.remove",
    "employer.approve", "employer.reject",
    "announcement.create", "announcement.toggle", "announcement.delete",
    "invoice.issue", "invoice.settings",
    "refund.request", "refund.approve", "refund.reject",
    "permissions.update",
    "course.delete", "quiz.delete", "live.delete",
    # Phase 10 — platform hardening
    "apikey.create", "apikey.revoke", "apikey.delete",
    "webhook.create", "webhook.toggle", "webhook.delete",
    "backup.create", "backup.restore", "backup.delete",
    "template.create", "template.toggle", "template.delete",
)


def audit(actor, action, target_type="", target_id=None, detail="", ip=""):
    """Write one audit-log row. Never raises (logging must not break flows)."""
    try:
        db.session.add(AuditLog(
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", "") or "",
            action=action, target_type=target_type or "",
            target_id=target_id, detail=detail or "", ip=ip or ""))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ---------------------------------------------------------------- attendance (§4.3)

LATE_GRACE_MIN = 10  # joining later than this after start => "late"


def auto_mark_attendance(session, user, now=None):
    """Mark a student present on joining via the LMS join link.

    Returns the SessionAttendance row (creates or updates the auto record;
    a faculty manual override is never overwritten).
    """
    now = now or datetime.utcnow()
    rec = SessionAttendance.query.filter_by(
        session_id=session.id, user_id=user.id).first()
    if rec and not rec.auto:
        return rec  # faculty manually marked — keep their decision
    late = now > session.starts_at + timedelta(minutes=LATE_GRACE_MIN)
    duration = max(0, int((session.ends_at - now).total_seconds() // 60))
    if rec is None:
        rec = SessionAttendance(session_id=session.id, user_id=user.id,
                                auto=True)
        db.session.add(rec)
    rec.status = (SessionAttendance.STATUS_LATE if late
                  else SessionAttendance.STATUS_PRESENT)
    rec.joined_at = now
    rec.duration_min = duration
    rec.auto = True
    db.session.commit()
    return rec


def manual_mark_attendance(session, user_id, status, marker, duration_min=None):
    """Faculty manual attendance marking/override."""
    if status not in SessionAttendance.STATUSES:
        raise ValueError(f"bad status {status!r}")
    rec = SessionAttendance.query.filter_by(
        session_id=session.id, user_id=user_id).first()
    if rec is None:
        rec = SessionAttendance(session_id=session.id, user_id=user_id)
        db.session.add(rec)
    rec.status = status
    rec.marked_by = marker.id
    rec.auto = False
    if duration_min is not None:
        rec.duration_min = max(0, int(duration_min))
    db.session.commit()
    return rec


def attendance_report(course_id):
    """Per-student attendance summary for a course's live sessions."""
    sessions = (LiveSession.query.filter_by(course_id=course_id)
                .order_by(LiveSession.starts_at).all())
    if not sessions:
        return {"sessions": [], "students": []}
    sids = [s.id for s in sessions]
    recs = SessionAttendance.query.filter(
        SessionAttendance.session_id.in_(sids)).all()
    by_user = {}
    for r in recs:
        by_user.setdefault(r.user_id, {})[r.session_id] = r.status
    enrolls = Enrollment.query.filter_by(course_id=course_id).all()
    students = []
    for e in enrolls:
        row = by_user.get(e.user_id, {})
        present = sum(1 for sid in sids
                      if row.get(sid) in ("present", "late"))
        students.append({
            "user": e.user, "records": row,
            "present": present, "total": len(sids),
            "percent": round(100.0 * present / len(sids), 1),
        })
    students.sort(key=lambda s: s["user"].name.lower())
    return {"sessions": sessions, "students": students}


# ---------------------------------------------------------------- batches (§18.4)

def enroll_in_batch(batch, user):
    """Enroll a student in a batch, respecting capacity.

    Returns (ok, message).
    """
    existing = BatchMember.query.filter_by(
        batch_id=batch.id, user_id=user.id).first()
    if existing:
        return False, "Already in this batch."
    count = BatchMember.query.filter_by(batch_id=batch.id).count()
    if batch.capacity and count >= batch.capacity:
        return False, f"Batch is full (capacity {batch.capacity})."
    db.session.add(BatchMember(batch_id=batch.id, user_id=user.id))
    # Batch membership implies course access: ensure an enrollment exists.
    new_enr = None
    enr = Enrollment.query.filter_by(
        user_id=user.id, course_id=batch.course_id).first()
    if not enr:
        new_enr = Enrollment(user_id=user.id, course_id=batch.course_id,
                             status="active")
        db.session.add(new_enr)
    db.session.commit()
    if new_enr is not None:
        # Phase 10: real event — enrollment created via batch (§25.2, §12.4)
        try:
            from . import hardening as _H
            _H.emit_enrollment(user, new_enr)
        except Exception:
            pass
    return True, f"{user.name} added to {batch.name}."


def batch_summary(batch):
    """Roster + attendance + progress summary for a batch detail page."""
    members = (BatchMember.query.filter_by(batch_id=batch.id)
               .order_by(BatchMember.added_at).all())
    rows = []
    for m in members:
        att = SessionAttendance.percent(m.user_id, batch.course_id)
        enr = Enrollment.query.filter_by(
            user_id=m.user_id, course_id=batch.course_id).first()
        rows.append({"user": m.user, "attendance": att,
                     "progress": enr.progress() if enr else 0,
                     "enrolled": bool(enr)})
    return {"batch": batch, "members": rows,
            "count": len(rows), "capacity": batch.capacity}


# ---------------------------------------------------------------- permissions (§18.3)

PERMISSION_MODULES = [
    "dashboard", "courses", "lessons", "quizzes", "question_bank",
    "assignments", "projects", "live_sessions", "attendance", "discussions",
    "announcements", "batches", "users", "coupons", "enrollments",
    "invoices", "refunds", "finance", "audit_logs", "permissions",
    "jobs", "employers", "leads", "applications", "referrals",
    "gamification", "challenges", "career", "certificates", "reports",
    "calendar", "marketing", "settings",
]

# (module, action) pairs denied per role; everything else follows the grant.
# Admin: granted everything. Manager: everything except users/coupons/system.
# Faculty: full on own-course content modules (course scoping still enforced
# by can_manage_course in routes), read on reports/calendar.
# Student: self-service modules only. Employer: own jobs only.
_F = {"view", "create", "edit", "delete"}
_MANAGER_DENY = {"users": _F, "coupons": _F, "permissions": _F,
                 "settings": _F, "audit_logs": {"create", "edit", "delete"}}
_FACULTY_GRANT = {"courses", "lessons", "quizzes", "question_bank",
                  "assignments", "projects", "live_sessions", "attendance",
                  "discussions", "batches", "challenges", "certificates"}
_FACULTY_VIEW = {"reports", "calendar", "dashboard", "enrollments"}
_STUDENT_VIEW = {"dashboard", "courses", "calendar", "certificates",
                 "career", "challenges", "gamification"}
_EMPLOYER_GRANT = {"jobs"}


def _default_for(role, module):
    if role == "admin":
        return {a: True for a in ("view", "create", "edit", "delete")}
    if role == "manager":
        denied = _MANAGER_DENY.get(module, set())
        return {a: (a not in denied) for a in ("view", "create", "edit",
                                               "delete")}
    if role == "faculty":
        if module in _FACULTY_GRANT:
            return {a: True for a in ("view", "create", "edit", "delete")}
        if module in _FACULTY_VIEW:
            return {"view": True, "create": False, "edit": False,
                    "delete": False}
        return {a: False for a in ("view", "create", "edit", "delete")}
    if role == "student":
        if module in _STUDENT_VIEW:
            return {"view": True, "create": False, "edit": False,
                    "delete": False}
        return {a: False for a in ("view", "create", "edit", "delete")}
    if role == "employer":
        if module in _EMPLOYER_GRANT:
            return {"view": True, "create": True, "edit": True,
                    "delete": False}
        return {a: False for a in ("view", "create", "edit", "delete")}
    # counsellor and unknown roles: nothing by default
    return {a: False for a in ("view", "create", "edit", "delete")}


def ensure_permission_defaults():
    """Seed the permission matrix for every role × module (idempotent)."""
    from .models import (ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_EMPLOYER,
                         ROLE_FACULTY, ROLE_MANAGER, ROLE_STUDENT)
    for role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_FACULTY, ROLE_STUDENT,
                 ROLE_COUNSELLOR, ROLE_EMPLOYER):
        for module in PERMISSION_MODULES:
            row = RolePermission.query.filter_by(
                role=role, module=module).first()
            if row:
                continue
            defaults = _default_for(role, module)
            db.session.add(RolePermission(
                role=role, module=module, can_view=defaults["view"],
                can_create=defaults["create"], can_edit=defaults["edit"],
                can_delete=defaults["delete"]))
    db.session.commit()


def has_permission(user, module, action):
    """True if the user's role grants `action` on `module`.

    Admins always pass. Falls back to the built-in defaults when no DB row
    exists (e.g. before the matrix is seeded).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user.role == "admin":
        return True
    row = RolePermission.query.filter_by(
        role=user.role, module=module).first()
    if row is None:
        return _default_for(user.role, module).get(action, False)
    return bool({"view": row.can_view, "create": row.can_create,
                 "edit": row.can_edit, "delete": row.can_delete
                 }.get(action, False))


# ---------------------------------------------------------------- invoices & finance (§11.4–11.5)

def invoice_breakdown(enrollment):
    """GST math for an enrollment. Course fee is excl. GST; SAC 999293."""
    settings = InvoiceSetting.get()
    course = enrollment.course
    base = int(course.fee or 0)
    discount = 0
    if enrollment.coupon_code:
        coupon = Coupon.query.filter_by(
            code=enrollment.coupon_code).first()
        if coupon:
            discount = round(base * (coupon.percent_off or 0) / 100)
    taxable = max(0, base - discount)
    gst = round(taxable * (settings.gst_rate or 0) / 100)
    total = taxable + gst
    return {"base_fee": base, "discount": int(discount),
            "taxable": int(taxable), "gst_amount": int(gst),
            "total": int(total), "gst_rate": settings.gst_rate or 0.0,
            "sac": settings.sac_code}


def issue_invoice(enrollment, issued_by=None):
    """Issue (or fetch the existing) invoice for a paid enrollment."""
    existing = Invoice.query.filter_by(
        enrollment_id=enrollment.id).first()
    if existing:
        return existing
    if not enrollment.paid:
        raise ValueError("Cannot invoice an unpaid enrollment.")
    settings = InvoiceSetting.get()
    year = datetime.utcnow().year
    number = (f"{settings.invoice_prefix}-{year}-"
              f"{settings.next_number:04d}")
    settings.next_number = (settings.next_number or 1) + 1
    br = invoice_breakdown(enrollment)
    inv = Invoice(
        number=number, enrollment_id=enrollment.id,
        user_id=enrollment.user_id, course_id=enrollment.course_id,
        base_fee=br["base_fee"], discount=br["discount"],
        taxable=br["taxable"], gst_amount=br["gst_amount"],
        total=br["total"],
        issued_by=getattr(issued_by, "id", None))
    db.session.add(inv)
    db.session.commit()
    return inv


def finance_summary():
    """Revenue, collections, pending fees, refunds, discounts, history."""
    paid = Enrollment.query.filter_by(paid=True).all()
    revenue = sum(e.amount_paid or 0 for e in paid)
    by_month = {}
    for e in paid:
        key = (e.enrolled_at or datetime.utcnow()).strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0) + (e.amount_paid or 0)
    pending = (Enrollment.query.filter(Enrollment.paid.is_(False)).all())
    pending_fees = sum((e.course.fee or 0) for e in pending if e.course)
    approved_refunds = Refund.query.filter_by(
        status=Refund.STATUS_APPROVED).all()
    refunds_total = sum(r.amount or 0 for r in approved_refunds)
    discounts = 0
    for e in paid:
        if e.coupon_code:
            coupon = Coupon.query.filter_by(code=e.coupon_code).first()
            if coupon and e.course:
                discounts += round((e.course.fee or 0) *
                                   (coupon.percent_off or 0) / 100)
    history = sorted(paid,
                     key=lambda e: e.enrolled_at or datetime.min,
                     reverse=True)
    return {
        "revenue": revenue,
        "paid_count": len(paid),
        "by_month": sorted(by_month.items()),
        "pending_count": len(pending),
        "pending_fees": pending_fees,
        "refunds_total": int(refunds_total),
        "refunds_count": len(approved_refunds),
        "discounts_total": int(discounts),
        "history": history,
    }


# ---------------------------------------------------------------- calendar (§4.6)

def calendar_events(user):
    """Unified event list for a student or faculty member.

    Aggregates live sessions, assignment due dates, exam (quiz) deadlines,
    project deadlines and challenge windows — no duplicate event tables.
    """
    events = []
    if user.role == "faculty":
        course_ids = [c.id for c in Course.query.filter_by(
            instructor_id=user.id).all()]
    else:
        course_ids = [e.course_id for e in
                      Enrollment.query.filter_by(user_id=user.id).all()]
    if not course_ids:
        return events
    now = datetime.utcnow()

    for s in LiveSession.query.filter(
            LiveSession.course_id.in_(course_ids)).all():
        events.append({"title": f"🔴 {s.title}", "start": s.starts_at.isoformat(),
                       "end": s.ends_at.isoformat(),
                       "url": f"/live/join/{s.id}" if user.role != "faculty"
                       else f"/manage/live/{s.id}/attendance",
                       "kind": "live", "course": s.course.title})
    for a in Assignment.query.filter(
            Assignment.course_id.in_(course_ids)).all():
        if a.due_date:
            events.append({"title": f"📝 {a.title} — due",
                           "start": a.due_date.isoformat(), "kind": "assignment",
                           "course": a.course.title,
                           "url": f"/assignments/{a.id}"})
    for q in Quiz.query.join(Module).filter(
            Module.course_id.in_(course_ids)).all():
        if q.deadline:
            events.append({"title": f"🧪 {q.title} — exam deadline",
                           "start": q.deadline.isoformat(), "kind": "exam",
                           "course": q.module.course.title,
                           "url": f"/quiz/{q.id}"})
    for p in Project.query.filter(
            Project.course_id.in_(course_ids),
            Project.is_active.is_(True)).all():
        if p.deadline:
            events.append({"title": f"📁 {p.title} — deadline",
                           "start": p.deadline.isoformat(), "kind": "project",
                           "course": p.course.title,
                           "url": f"/project/{p.id}"})
    for ch in Challenge.query.filter(Challenge.is_active.is_(True)).all():
        if ch.ends_at and ch.ends_at >= now and (
                not ch.course_id or ch.course_id in course_ids):
            events.append({"title": f"🏆 {ch.title}",
                           "start": ch.starts_at.isoformat(),
                           "end": ch.ends_at.isoformat(), "kind": "challenge",
                           "url": "/challenges"})
    events.sort(key=lambda e: e["start"])
    return events
