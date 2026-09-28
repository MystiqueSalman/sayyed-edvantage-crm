"""Phase 13 Stream 3 — rules-based at-risk detection (§13.3.3).

NO machine learning, NO auto-messaging. Rules run on existing LMS data:
attendance (Phase 9 SessionAttendance), missed assignment deadlines
(Assignment/Submission), and quiz-score trend (QuizAttempt).

GUARANTEE: flags are visible to staff only (counsellor/admin/manager).
Students are never notified automatically — outreach is a manual,
human decision. This guarantee is also rendered as a banner on the
/counsellor/at-risk page.
"""
from datetime import date, datetime

from . import db
from .models import (Assignment, Enrollment, QuizAttempt, SessionAttendance,
                     Submission, User)
from .models13_ai import AtRiskFlag13

ATTENDANCE_PCT_THRESHOLD = 60.0   # below this => low attendance
QUIZ_DROP_POINTS = 15.0            # last-3 vs first-3 avg drop => declining


def compute_reasons(user_id):
    """Return a list of reason strings for a student, e.g.
    ["low_attendance:Data Science:42%", "missed_deadlines:3",
     "quiz_trend:down:21.5pts"]. Empty list => not at risk."""
    reasons = []
    enrollments = Enrollment.query.filter_by(user_id=user_id).all()

    # -- low attendance per enrolled course ------------------------------
    for en in enrollments:
        pct = SessionAttendance.percent(user_id, en.course_id)
        if pct is not None and pct < ATTENDANCE_PCT_THRESHOLD:
            title = en.course.title if en.course else f"course#{en.course_id}"
            reasons.append(f"low_attendance:{title}:{pct}%")

    # -- missed assignment deadlines --------------------------------------
    if enrollments:
        course_ids = [e.course_id for e in enrollments]
        past_due = (Assignment.query
                    .filter(Assignment.course_id.in_(course_ids),
                            Assignment.due_date.isnot(None),
                            Assignment.due_date < date.today())
                    .all())
        if past_due:
            submitted = {s.assignment_id for s in
                         Submission.query.filter_by(user_id=user_id).all()}
            missed = [a for a in past_due if a.id not in submitted]
            if missed:
                reasons.append(f"missed_deadlines:{len(missed)}")

    # -- declining quiz trend ----------------------------------------------
    attempts = (QuizAttempt.query
                .filter(QuizAttempt.user_id == user_id,
                        QuizAttempt.submitted_at.isnot(None),
                        QuizAttempt.total > 0)
                .order_by(QuizAttempt.taken_at.asc()).all())
    if len(attempts) >= 4:
        first3 = attempts[:3]
        last3 = attempts[-3:]
        avg_first = sum(a.percent for a in first3) / 3.0
        avg_last = sum(a.percent for a in last3) / 3.0
        drop = avg_first - avg_last
        if drop > QUIZ_DROP_POINTS:
            reasons.append(f"quiz_trend:down:{round(drop, 1)}pts")

    return reasons


def recompute_all():
    """Recompute flags for every student.

    Creates a new unresolved flag when reasons exist and none is open;
    refreshes reasons on the open flag; auto-resolves open flags whose
    reasons cleared. Returns (new_flags, total_open).
    """
    students = User.query.filter_by(role="student", is_active=True).all()
    new_flags = 0
    for s in students:
        reasons = compute_reasons(s.id)
        flag = (AtRiskFlag13.query
                .filter_by(user_id=s.id, resolved=False)
                .order_by(AtRiskFlag13.created_at.desc()).first())
        if reasons:
            if flag:
                flag.reasons = reasons  # keep history-light: latest reasons
            else:
                db.session.add(AtRiskFlag13(user_id=s.id, reasons=reasons))
                new_flags += 1
        elif flag:
            flag.resolved = True
            flag.resolved_at = datetime.utcnow()
    db.session.commit()
    total_open = AtRiskFlag13.query.filter_by(resolved=False).count()
    return new_flags, total_open


def resolve_flag(flag_id):
    flag = db.session.get(AtRiskFlag13, flag_id)
    if not flag:
        return False
    flag.resolved = True
    flag.resolved_at = datetime.utcnow()
    db.session.commit()
    return True
