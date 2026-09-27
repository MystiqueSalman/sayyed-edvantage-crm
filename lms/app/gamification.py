"""Phase 8 — Gamification & engagement engine (§15).

Central place for points, streaks, badges and challenges. All point awards
go through ``award_points()`` which writes an audit row in PointTransaction
(totals are always recomputable), updates the denormalized GameProfile,
extends the daily streak, runs the badge criteria engine and refreshes
challenge progress — idempotently, so re-calling for the same activity is a
no-op.
"""
import json
from datetime import datetime, date, timedelta

from . import db
from .models import (
    Badge, Challenge, ChallengeEnrollment, Course, Discussion,
    DiscussionReply, Enrollment, GameProfile, GamificationSetting, Lesson,
    LessonProgress, MockInterview, Module, PointSetting, PointTransaction,
    Project, ProjectSubmission, Quiz, QuizAttempt, Resume, Submission, User,
    UserBadge,
)

try:
    from zoneinfo import ZoneInfo
    _KOLKATA = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - very old Pythons
    _KOLKATA = None


def kolkata_today():
    """Current date on Asia/Kolkata day boundaries (§15.3)."""
    if _KOLKATA is not None:
        return datetime.now(_KOLKATA).date()
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()


def kolkata_date(dt):
    if dt is None:
        return None
    if _KOLKATA is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=_KOLKATA) - timedelta(hours=5, minutes=30)
        # naive UTC datetimes: shift to IST
        return (dt + timedelta(hours=5, minutes=30)).date() \
            if dt.tzinfo is None else dt.date()
    if _KOLKATA is not None:
        return dt.astimezone(_KOLKATA).date()
    return (dt + timedelta(hours=5, minutes=30)).date()


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
POINT_DEFAULTS = {
    # action: (points, label, counts_for_streak)
    "lesson_complete": (10, "Lesson completed", True),
    "quiz_attempt": (5, "Quiz attempted", True),
    "quiz_score_bonus": (0, "Quiz score bonus (scaled by %)", True),
    "assignment_submit": (15, "Assignment submitted", True),
    "project_submit": (20, "Project submitted", True),
    "project_evaluated": (0, "Project evaluation bonus (scaled by %)", True),
    "daily_login": (2, "Daily login", False),
    "discussion_post": (5, "Discussion post / reply", True),
    "mock_interview_complete": (25, "Mock interview completed", True),
    "challenge_reward": (50, "Challenge reward", False),
}

# bonus rates (points per percent)
QUIZ_BONUS_RATE_SETTING = "quiz_bonus_rate"      # default 0.2 → 90% = 18 pts
PROJECT_BONUS_RATE_SETTING = "project_bonus_rate"  # default 0.3

SYSTEM_BADGES = [
    # (name, icon, description, criterion, threshold)
    ("Pioneer", "🌱", "One of our earliest learners.", "pioneer", 1),
    ("First Steps", "👣", "Complete your first lesson.", "lessons_completed", 1),
    ("Bookworm", "📚", "Complete 25 lessons.", "lessons_completed", 25),
    ("Scholar", "🎓", "Complete 100 lessons.", "lessons_completed", 100),
    ("Quiz Whiz", "🧠", "Score 90% or more on any quiz.", "quiz_mastery", 90),
    ("Sharpshooter", "🎯", "Attempt 10 quizzes.", "quizzes_attempted", 10),
    ("Graduate", "🎉", "Complete your first course.", "courses_completed", 1),
    ("Project Star", "⭐", "Score 85%+ on an evaluated project.", "project_star", 85),
    ("Consistent", "🔥", "Keep a 7-day learning streak.", "streak_days", 7),
    ("Unstoppable", "⚡", "Keep a 30-day learning streak.", "streak_days", 30),
    ("Debater", "💬", "Make 10 discussion posts.", "discussion_posts", 10),
    ("Interview Ready", "🎤", "Complete a mock interview.", "interviews_completed", 1),
    ("Polished", "📄", "Complete your resume.", "resume_complete", 1),
    ("Century Club", "💯", "Earn 500 points.", "points_total", 500),
]


# ---------------------------------------------------------------------------
# Setup / defaults
# ---------------------------------------------------------------------------
def ensure_gamification_defaults():
    """Idempotent: point settings, bonus rates and system badges."""
    for action, (points, label, streak) in POINT_DEFAULTS.items():
        row = PointSetting.query.filter_by(action=action).first()
        if not row:
            db.session.add(PointSetting(action=action, points=points,
                                        label=label,
                                        counts_for_streak=streak))
    for action, default in ((QUIZ_BONUS_RATE_SETTING, 0.2),
                            (PROJECT_BONUS_RATE_SETTING, 0.3)):
        if not PointSetting.query.filter_by(action=action).first():
            db.session.add(PointSetting(action=action, points=0,
                                        label=f"rate:{default}"))
    for name, icon, desc, criterion, threshold in SYSTEM_BADGES:
        if not Badge.query.filter_by(name=name, is_system=True).first():
            db.session.add(Badge(name=name, icon=icon, description=desc,
                                 criterion=criterion, threshold=threshold,
                                 is_system=True, is_active=True))
    db.session.commit()


def get_profile(user_id):
    profile = GameProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = GameProfile(user_id=user_id)
        db.session.add(profile)
        db.session.flush()
    return profile


def point_value(action):
    row = PointSetting.query.filter_by(action=action).first()
    if row:
        return row.points
    return POINT_DEFAULTS.get(action, (0, "", True))[0]


def bonus_rate(setting_action, default):
    row = PointSetting.query.filter_by(action=setting_action).first()
    if row and row.label.startswith("rate:"):
        try:
            return float(row.label.split(":", 1)[1])
        except ValueError:
            return default
    return default


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------
def award_points(user_id, action, ref_type="", ref_id="", points=None,
                 counts_for_streak=None, _commit=True):
    """Award points for one activity. Idempotent via the ledger's unique key.

    Returns (points_awarded, [newly awarded Badge objects]).
    """
    ref_id = str(ref_id or "")
    existing = PointTransaction.query.filter_by(
        user_id=user_id, action=action, ref_type=ref_type,
        ref_id=ref_id).first()
    if existing:
        return 0, []
    value = point_value(action) if points is None else int(points)
    if value <= 0:
        return 0, []
    db.session.add(PointTransaction(user_id=user_id, action=action,
                                    ref_type=ref_type, ref_id=ref_id,
                                    points=value))
    profile = get_profile(user_id)
    profile.points_total = (profile.points_total or 0) + value
    new_badges = []
    setting = PointSetting.query.filter_by(action=action).first()
    streak_ok = (setting.counts_for_streak if setting
                 else POINT_DEFAULTS.get(action, (0, "", True))[2])
    if counts_for_streak is not None:
        streak_ok = counts_for_streak
    if streak_ok:
        record_activity(user_id)
        new_badges.extend(check_badges(user_id))
    update_challenges(user_id)
    if _commit:
        db.session.commit()
    else:
        db.session.flush()
    return value, new_badges


def recompute_points_total(user_id):
    """Recompute a student's total from the ledger (audit)."""
    total = db.session.query(
        db.func.coalesce(db.func.sum(PointTransaction.points), 0)).filter_by(
        user_id=user_id).scalar() or 0
    profile = get_profile(user_id)
    profile.points_total = int(total)
    db.session.commit()
    return int(total)


# ---------------------------------------------------------------------------
# Streaks (§15.3)
# ---------------------------------------------------------------------------
def record_activity(user_id, on_date=None):
    """Extend the daily learning streak (Asia/Kolkata day boundaries)."""
    profile = get_profile(user_id)
    today = on_date or kolkata_today()
    last = profile.last_active_date
    if last == today:
        return profile.current_streak or 0
    if last == today - timedelta(days=1):
        profile.current_streak = (profile.current_streak or 0) + 1
    else:
        profile.current_streak = 1  # reset after a missed day
    profile.longest_streak = max(profile.longest_streak or 0,
                                 profile.current_streak)
    profile.last_active_date = today
    db.session.flush()
    return profile.current_streak


# ---------------------------------------------------------------------------
# Badges (§15.1)
# ---------------------------------------------------------------------------
def _criterion_met(user_id, badge, profile):
    c, t = badge.criterion, badge.threshold or 0
    if c == "pioneer":
        return False  # backfill-only
    if c == "lessons_completed":
        n = LessonProgress.query.filter_by(user_id=user_id).count()
        if badge.course_id:
            lesson_ids = [l.id for l in Lesson.query.join(
                Lesson.module).join(Course).filter(
                Course.id == badge.course_id).all()]
            n = LessonProgress.query.filter(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id.in_(lesson_ids)).count() \
                if lesson_ids else 0
        return n >= t
    if c == "quizzes_attempted":
        return QuizAttempt.query.filter_by(user_id=user_id).filter(
            QuizAttempt.submitted_at.isnot(None)).count() >= t
    if c == "quiz_mastery":
        return QuizAttempt.query.filter_by(user_id=user_id).filter(
            QuizAttempt.submitted_at.isnot(None),
            QuizAttempt.total > 0,
            (QuizAttempt.score / QuizAttempt.total * 100) >= t).count() > 0
    if c == "courses_completed":
        return Enrollment.query.filter_by(
            user_id=user_id, status=Enrollment.STATUS_COMPLETED).count() >= t
    if c == "project_star":
        subs = ProjectSubmission.query.filter_by(
            user_id=user_id, status="evaluated").all()
        return any((s.percent or 0) >= t for s in subs)
    if c == "projects_evaluated":
        return ProjectSubmission.query.filter_by(
            user_id=user_id, status="evaluated").count() >= t
    if c == "streak_days":
        return (profile.longest_streak or 0) >= t
    if c == "discussion_posts":
        d = Discussion.query.filter_by(user_id=user_id).count()
        r = DiscussionReply.query.filter_by(user_id=user_id).count()
        return (d + r) >= t
    if c == "interviews_completed":
        return MockInterview.query.filter_by(
            user_id=user_id, status=MockInterview.STATUS_DONE).count() >= t
    if c == "resume_complete":
        r = Resume.query.filter_by(user_id=user_id).first()
        return bool(r and r.is_complete())
    if c == "points_total":
        return (profile.points_total or 0) >= t
    return False


def check_badges(user_id):
    """Award every badge whose criteria are now met. Returns new badges."""
    profile = get_profile(user_id)
    earned_ids = {ub.badge_id for ub in
                  UserBadge.query.filter_by(user_id=user_id).all()}
    new_badges = []
    for badge in Badge.query.filter_by(is_active=True).all():
        if badge.id in earned_ids:
            continue
        try:
            met = _criterion_met(user_id, badge, profile)
        except Exception:
            continue
        if met:
            db.session.add(UserBadge(user_id=user_id, badge_id=badge.id))
            new_badges.append(badge)
    if new_badges:
        db.session.flush()
    return new_badges


# ---------------------------------------------------------------------------
# Challenges (§15.5)
# ---------------------------------------------------------------------------
def challenge_progress(user_id, challenge, since):
    """Return 0..100 progress for a student's challenge enrollment."""
    t = challenge.target
    crit = challenge.criterion
    if crit == "lessons":
        need = int(t.get("count", 1) or 1)
        q = LessonProgress.query.filter(
            LessonProgress.user_id == user_id,
            LessonProgress.completed_at >= since)
        if challenge.course_id:
            lesson_ids = [l.id for m in Module.query.filter_by(
                course_id=challenge.course_id).all() for l in m.lessons]
            q = q.filter(LessonProgress.lesson_id.in_(lesson_ids)) \
                if lesson_ids else q.filter(False)
        have = q.count()
        return min(100.0, 100.0 * have / need)
    if crit == "quiz_score":
        need_pct = float(t.get("percent", 80) or 80)
        quiz_id = t.get("quiz_id")
        q = QuizAttempt.query.filter(
            QuizAttempt.user_id == user_id,
            QuizAttempt.submitted_at.isnot(None),
            QuizAttempt.submitted_at >= since,
            QuizAttempt.total > 0)
        if quiz_id:
            q = q.filter(QuizAttempt.quiz_id == int(quiz_id))
        best = 0.0
        for a in q.all():
            best = max(best, 100.0 * (a.score or 0) / (a.total or 1))
        return 100.0 if best >= need_pct else min(99.0, best)
    if crit == "points":
        need = int(t.get("points", 50) or 50)
        earned = db.session.query(
            db.func.coalesce(db.func.sum(PointTransaction.points), 0)).filter(
            PointTransaction.user_id == user_id,
            PointTransaction.action != "challenge_reward",
            PointTransaction.created_at >= since).scalar() or 0
        return min(100.0, 100.0 * earned / need)
    if crit == "project":
        q = ProjectSubmission.query.filter(
            ProjectSubmission.user_id == user_id,
            ProjectSubmission.status == "evaluated",
            ProjectSubmission.evaluated_at >= since)
        if challenge.course_id:
            pids = [p.id for p in Project.query.filter_by(
                course_id=challenge.course_id).all()]
            q = q.filter(ProjectSubmission.project_id.in_(pids)) \
                if pids else q.filter(False)
        return 100.0 if q.count() > 0 else 0.0
    if crit == "course":
        q = Enrollment.query.filter(
            Enrollment.user_id == user_id,
            Enrollment.status == Enrollment.STATUS_COMPLETED)
        if challenge.course_id:
            q = q.filter(Enrollment.course_id == challenge.course_id)
        return 100.0 if q.count() > 0 else 0.0
    return 0.0


def update_challenges(user_id):
    """Refresh progress for the student's live challenge enrollments.

    Returns the newly completed ChallengeEnrollment objects (rewards are
    awarded with a per-enrollment idempotency key).
    """
    now = datetime.utcnow()
    completed = []
    enrollments = (ChallengeEnrollment.query.filter_by(user_id=user_id,
                                                       completed=False)
                   .join(Challenge)
                   .filter(Challenge.is_active.is_(True)).all())
    for enr in enrollments:
        ch = enr.challenge
        if not ch or not ch.is_live:
            continue
        since = enr.joined_at or ch.starts_at or now
        enr.progress = round(challenge_progress(user_id, ch, since), 1)
        if enr.progress >= 100.0:
            enr.completed = True
            enr.completed_at = now
            completed.append(enr)
            db.session.flush()
            award_points(user_id, "challenge_reward",
                         ref_type="challenge", ref_id=enr.id,
                         points=ch.reward_points or 0,
                         counts_for_streak=False, _commit=False)
    if enrollments or completed:
        db.session.flush()
    return completed


# ---------------------------------------------------------------------------
# Backfill (§15 — one-time, from real historical activity only)
# ---------------------------------------------------------------------------
def _activity_dates(user_id):
    """Distinct Asia/Kolkata dates of real historical learning activity."""
    dates = set()
    for model, col in ((LessonProgress, LessonProgress.completed_at),
                       (QuizAttempt, QuizAttempt.submitted_at),
                       (Submission, Submission.submitted_at),
                       (ProjectSubmission, ProjectSubmission.submitted_at),
                       (Discussion, Discussion.created_at),
                       (DiscussionReply, DiscussionReply.created_at),
                       (MockInterview, MockInterview.completed_at)):
        rows = db.session.query(col).filter(
            model.user_id == user_id, col.isnot(None)).all()
        for (dt,) in rows:
            d = kolkata_date(dt)
            if d:
                dates.add(d)
    return dates


def run_backfill(force=False):
    """One-time backfill for pre-Phase-8 students.

    Awards points computed from real historical records, the Pioneer badge,
    and rebuilds streaks from real activity dates. Guarded so it runs once.
    """
    settings = GamificationSetting.get()
    if settings.backfill_done and not force:
        return {"skipped": True}
    ensure_gamification_defaults()
    quiz_rate = bonus_rate(QUIZ_BONUS_RATE_SETTING, 0.2)
    proj_rate = bonus_rate(PROJECT_BONUS_RATE_SETTING, 0.3)
    pioneer = Badge.query.filter_by(name="Pioneer", is_system=True).first()
    stats = {"users": 0, "transactions": 0, "badges": 0}

    def _add(uid, action, ref_type, ref_id, points):
        ref_id = str(ref_id or "")
        if points <= 0:
            return
        exists = PointTransaction.query.filter_by(
            user_id=uid, action=action, ref_type=ref_type,
            ref_id=ref_id).first()
        if exists:
            return
        db.session.add(PointTransaction(
            user_id=uid, action=action, ref_type=ref_type, ref_id=ref_id,
            points=int(points)))
        stats["transactions"] += 1

    students = User.query.filter_by(role="student").all()
    for u in students:
        stats["users"] += 1
        for lp in LessonProgress.query.filter_by(user_id=u.id).all():
            _add(u.id, "lesson_complete", "lesson", lp.lesson_id,
                 point_value("lesson_complete"))
        for a in QuizAttempt.query.filter_by(user_id=u.id).filter(
                QuizAttempt.submitted_at.isnot(None)).all():
            _add(u.id, "quiz_attempt", "attempt", a.id,
                 point_value("quiz_attempt"))
            if a.total:
                pct = 100.0 * (a.score or 0) / a.total
                _add(u.id, "quiz_score_bonus", "attempt", a.id,
                     int(pct * quiz_rate))
        for s in Submission.query.filter_by(user_id=u.id).all():
            _add(u.id, "assignment_submit", "assignment", s.assignment_id,
                 point_value("assignment_submit"))
        for ps in ProjectSubmission.query.filter_by(user_id=u.id).all():
            _add(u.id, "project_submit", "project", ps.project_id,
                 point_value("project_submit"))
            if ps.status == "evaluated" and ps.percent:
                _add(u.id, "project_evaluated", "project_submission", ps.id,
                     int(ps.percent * proj_rate))
        for d in Discussion.query.filter_by(user_id=u.id).all():
            _add(u.id, "discussion_post", "discussion", d.id,
                 point_value("discussion_post"))
        for r in DiscussionReply.query.filter_by(user_id=u.id).all():
            _add(u.id, "discussion_post", "reply", r.id,
                 point_value("discussion_post"))
        for mi in MockInterview.query.filter_by(
                user_id=u.id, status=MockInterview.STATUS_DONE).all():
            _add(u.id, "mock_interview_complete", "interview", mi.id,
                 point_value("mock_interview_complete"))
        # rebuild streak from real activity dates
        dates = sorted(_activity_dates(u.id))
        profile = get_profile(u.id)
        if dates:
            streak, prev = 1, dates[0]
            for d in dates[1:]:
                streak = streak + 1 if d == prev + timedelta(days=1) else 1
                prev = d
            profile.last_active_date = dates[-1]
            profile.current_streak = streak
            profile.longest_streak = max(profile.longest_streak or 0, streak)
        db.session.flush()
        recompute_points_total(u.id)
        if pioneer and not UserBadge.query.filter_by(
                user_id=u.id, badge_id=pioneer.id).first():
            db.session.add(UserBadge(user_id=u.id, badge_id=pioneer.id))
            stats["badges"] += 1
        for b in check_badges(u.id):
            stats["badges"] += 1
        db.session.commit()
    settings.backfill_done = True
    db.session.commit()
    return stats
