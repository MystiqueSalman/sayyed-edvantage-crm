"""Student routes: dashboard, learning, quizzes, assignments, certificates."""
import os
import uuid
from datetime import datetime, timedelta

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy import func

from . import db
from .decorators import role_required
from .models import (Announcement, Assignment, Certificate, Challenge,
                     ChallengeEnrollment, Course, Enrollment, Lesson,
                     LessonProgress, LiveSession, Module, Project, ProjectSubmission,
                     Quiz, QuizAnswer, QuizAttempt, Review, Submission, User,
                     UserBadge, Wishlist)
from .pdfcert import certificate_path, generate_certificate_pdf
from .routes_crm import _onboarding_for  # Phase 4: onboarding checklist
from . import gamification as G  # Phase 8: points/badges/streaks/challenges

student_bp = Blueprint("student", __name__)
student_only = role_required("student")

ALLOWED_SUBMIT_EXTS = {"pdf", "doc", "docx", "zip", "txt", "png", "jpg", "jpeg", "py", "ipynb"}


def _flash_new_badges(badges):
    """Phase 8: celebrate newly earned badges."""
    for b in badges or []:
        flash(f"🏅 Badge earned: {b.icon} {b.name} — {b.description}",
              "success")


def _active_enrollment_or_403(course_id):
    enr = Enrollment.query.filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course_id,
        Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                               Enrollment.STATUS_COMPLETED])).first()
    if not enr and current_user.role != "student":
        return None
    return enr


def _policy_attempt(quiz, user_id):
    """Phase 6: the attempt that counts under the quiz's score policy.
    Only submitted, fully-graded attempts count (no pending review)."""
    attempts = (QuizAttempt.query
                .filter(QuizAttempt.quiz_id == quiz.id,
                        QuizAttempt.user_id == user_id,
                        QuizAttempt.submitted_at.isnot(None),
                        QuizAttempt.pending_review.is_(False))
                .order_by(QuizAttempt.id).all())
    if not attempts:
        return None
    if quiz.score_policy == "latest":
        return attempts[-1]
    return max(attempts, key=lambda a: (a.percent or 0.0, a.id))


def check_and_issue_certificate(user_id, course_id):
    """Issue a certificate when all lessons are done and every module quiz is
    passed per that quiz's score policy (§5.6)."""
    course = db.session.get(Course, course_id)
    lessons = course.lessons
    if not lessons:
        return None
    done = LessonProgress.query.filter(
        LessonProgress.user_id == user_id,
        LessonProgress.lesson_id.in_([l.id for l in lessons])).count()
    if done < len(lessons):
        return None
    for quiz in course.quizzes:
        if quiz.title == "__question_bank__":
            continue
        counting = _policy_attempt(quiz, user_id)
        if not counting or counting.percent < quiz.pass_percent:
            return None
    existing = Certificate.query.filter_by(user_id=user_id, course_id=course_id).first()
    if existing:
        return existing
    cert = Certificate(user_id=user_id, course_id=course_id,
                       code="SE-" + uuid.uuid4().hex[:10].upper())
    db.session.add(cert)
    enr = Enrollment.query.filter_by(user_id=user_id, course_id=course_id).first()
    if enr:
        enr.status = Enrollment.STATUS_COMPLETED
    db.session.commit()
    # Phase 10: real events — certificate issued + course completed (§25.2, §12.4)
    try:
        from . import hardening as _H
        user = db.session.get(User, user_id)
        ctx = {"user_name": user.name if user else "",
               "course_title": course.title, "code": cert.code}
        _H.notify(user_id, "certificate.issued",
                  f"Certificate ready for {course.title} 🏅",
                  f"Congratulations! Your certificate ({cert.code}) is ready.",
                  link="/certificates", context=ctx)
        _H.dispatch_webhook("certificate.issued", {
            "certificate_code": cert.code, "user_id": user_id,
            "user_name": user.name if user else "",
            "course_id": course_id, "course_title": course.title})
        _H.dispatch_webhook("course.completed", {
            "user_id": user_id,
            "user_name": user.name if user else "",
            "course_id": course_id, "course_title": course.title,
            "enrollment_id": enr.id if enr else None})
    except Exception:
        pass
    return cert


@student_bp.route("/dashboard")
@student_only
def dashboard():
    enrollments = (Enrollment.query.filter_by(user_id=current_user.id)
                   .filter(Enrollment.status.in_(["active", "completed"]))
                   .order_by(Enrollment.enrolled_at.desc()).all())
    # pending assignments across enrolled courses
    course_ids = [e.course_id for e in enrollments]
    pending = []
    if course_ids:
        submitted_ids = {s.assignment_id for s in Submission.query.filter_by(
            user_id=current_user.id).all()}
        pending = (Assignment.query.filter(Assignment.course_id.in_(course_ids))
                   .filter(~Assignment.id.in_(submitted_ids) if submitted_ids else True)
                   .order_by(Assignment.due_date).limit(10).all())
    certs = Certificate.query.filter_by(user_id=current_user.id).all()
    # live class widget: upcoming sessions across enrolled courses
    now = datetime.utcnow()
    live_sessions = []
    if course_ids:
        live_sessions = (LiveSession.query
                         .filter(LiveSession.course_id.in_(course_ids),
                                 LiveSession.starts_at >= now - timedelta(hours=3))
                         .order_by(LiveSession.starts_at).limit(6).all())
    # Phase 5: weak topics + today's study plan (AI learning layer)
    from .ai_tutor import todays_plan_items, weak_topics_for_student
    weak_topics = []
    for e in enrollments[:4]:
        for t in weak_topics_for_student(current_user.id, e.course_id)[:3]:
            t["course"] = e.course
            weak_topics.append(t)
        if len(weak_topics) >= 6:
            break
    plan_items = todays_plan_items(current_user.id)
    # Phase 8: gamification widgets
    game_profile = G.get_profile(current_user.id)
    recent_badges = (UserBadge.query.filter_by(user_id=current_user.id)
                     .order_by(UserBadge.awarded_at.desc()).limit(4).all())
    my_challenges = (ChallengeEnrollment.query
                     .filter_by(user_id=current_user.id, completed=False)
                     .join(Challenge).filter(Challenge.is_active.is_(True))
                     .all())
    my_challenges = [e for e in my_challenges if e.challenge.is_live][:3]
    # Phase 12: rules-based adaptive "recommended next" (§21.5)
    p12_recs = []
    try:
        from .adaptive import recommendations_for_student as _p12recs
        for e in enrollments[:2]:
            p12_recs.extend(_p12recs(current_user.id, e.course_id)[:2])
        p12_recs = p12_recs[:3]
    except Exception:
        p12_recs = []
    # UI14: redesigned dashboard cards + stats --------------------------------
    course_cards = []
    total_done = 0
    total_time_sec = 0
    for e in enrollments:
        lessons = e.course.lessons
        lesson_ids = [l.id for l in lessons]
        done_ids = set()
        spent = 0
        if lesson_ids:
            rows = LessonProgress.query.filter(
                LessonProgress.user_id == current_user.id,
                LessonProgress.lesson_id.in_(lesson_ids)).all()
            done_ids = {r.lesson_id for r in rows}
            spent = (db.session.query(func.coalesce(
                        func.sum(LessonProgress.time_spent_sec), 0))
                     .filter(LessonProgress.user_id == current_user.id,
                             LessonProgress.lesson_id.in_(lesson_ids))
                     .scalar() or 0)
        done = len(done_ids)
        total_done += done
        total_time_sec += spent
        total = len(lesson_ids)
        continue_lesson_id = next((l.id for l in lessons if l.id not in done_ids),
                                  lessons[0].id if lessons else None)
        course_cards.append({
            "e": e,
            "total": total,
            "done": done,
            "pct": round(100 * done / total) if total else 0,
            "continue_lesson_id": continue_lesson_id,
        })
    overall_pct = (int(sum(c["pct"] for c in course_cards) / len(course_cards))
                   if course_cards else 0)
    dash = {
        "enrolled": len(enrollments),
        "lessons_done": total_done,
        "hours": total_time_sec // 3600,
        "certificates": len(certs),
        "points": (game_profile.points_total or 0) if game_profile else 0,
        "streak": (game_profile.current_streak or 0) if game_profile else 0,
    }
    # UI14: upcoming assignment cards (max 4, ordered by due date)
    assignment_cards = []
    today = datetime.utcnow().date()
    if course_ids:
        my_submitted = {s.assignment_id for s in
                        Submission.query.filter_by(user_id=current_user.id).all()}
        for a in (Assignment.query.filter(Assignment.course_id.in_(course_ids))
                  .order_by(Assignment.due_date.asc().nullslast(),
                            Assignment.created_at.desc())
                  .limit(4).all()):
            if a.id in my_submitted:
                status = "Submitted"
            elif a.due_date and a.due_date < today:
                status = "Overdue"
            else:
                status = "Pending"
            assignment_cards.append({"a": a, "status": status})
    announcements = (Announcement.query.filter_by(active=True)
                     .order_by(Announcement.created_at.desc()).limit(4).all())
    return render_template("dashboard.html", enrollments=enrollments,
                           pending=pending, certs=certs, live_sessions=live_sessions,
                           now=now, onboarding=_onboarding_for(current_user),
                           weak_topics=weak_topics, plan_items=plan_items,
                           game_profile=game_profile,
                           recent_badges=recent_badges,
                           my_challenges=my_challenges,
                           p12_recs=p12_recs,
                           course_cards=course_cards, dash=dash,
                           assignment_cards=assignment_cards,
                           announcements=announcements,
                           overall_pct=overall_pct)


@student_bp.route("/lesson/<int:lesson_id>")
@student_only
def lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.module.course
    enr = _active_enrollment_or_403(course.id)
    if not enr:
        flash("Enroll in this course to access lessons.", "warning")
        return redirect(url_for("main.course_detail", slug=course.slug))
    # drip scheduling: locked until enrolled_at + available_after_days
    unlock_at = lesson.unlock_date(enr.enrolled_at)
    locked_days = (unlock_at.date() - datetime.utcnow().date()).days
    if locked_days > 0:
        return render_template("lesson.html", lesson=lesson, course=course,
                               done=False, prev_lesson=None, next_lesson=None,
                               module_quiz=None, locked=True,
                               locked_days=locked_days, unlock_at=unlock_at)
    done = LessonProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson.id).first() is not None
    # prev / next navigation
    lessons = course.lessons
    idx = [l.id for l in lessons].index(lesson.id)
    prev_lesson = lessons[idx - 1] if idx > 0 else None
    next_lesson = lessons[idx + 1] if idx < len(lessons) - 1 else None
    visible_quizzes = [q for q in lesson.module.quizzes
                       if q.title != "__question_bank__"]
    module_quiz = visible_quizzes[0] if visible_quizzes else None
    return render_template("lesson.html", lesson=lesson, course=course, done=done,
                           prev_lesson=prev_lesson, next_lesson=next_lesson,
                           module_quiz=module_quiz, locked=False)


@student_bp.route("/lesson/<int:lesson_id>/complete", methods=["POST"])
@student_only
def lesson_complete(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.module.course
    enr = _active_enrollment_or_403(course.id)
    if not enr:
        abort(403)
    if lesson.unlock_date(enr.enrolled_at).date() > datetime.utcnow().date():
        abort(403)  # drip-locked lessons can't be completed early
    if not LessonProgress.query.filter_by(
            user_id=current_user.id, lesson_id=lesson.id).first():
        db.session.add(LessonProgress(user_id=current_user.id, lesson_id=lesson.id))
        db.session.commit()
        # Phase 8: points + streak + badges + challenges
        _pts, new_badges = G.award_points(
            current_user.id, "lesson_complete", "lesson", lesson.id)
        _flash_new_badges(new_badges)
    cert = check_and_issue_certificate(current_user.id, course.id)
    if cert:
        flash("Course completed! Your certificate is ready.", "success")
        return redirect(url_for("student.certificates"))
    # next lesson or back to course
    lessons = course.lessons
    idx = [l.id for l in lessons].index(lesson.id)
    if idx < len(lessons) - 1:
        return redirect(url_for("student.lesson", lesson_id=lessons[idx + 1].id))
    flash("Lesson marked complete.", "success")
    return redirect(url_for("main.course_detail", slug=course.slug))


@student_bp.route("/lesson/<int:lesson_id>/heartbeat", methods=["POST"])
@student_only
def lesson_heartbeat(lesson_id):
    """UI14: real learning-time tracking.

    The lesson page pings this every 60s with {"seconds": <n>}; the seconds
    accumulate on the student's LessonProgress row.
    """
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return jsonify({"ok": False, "error": "Lesson not found."}), 404
    course = lesson.module.course
    if not _active_enrollment_or_403(course.id):
        return jsonify({"ok": False, "error": "Forbidden."}), 403
    data = request.get_json(silent=True) or {}
    try:
        seconds = int(data.get("seconds", 0))
    except (TypeError, ValueError):
        seconds = 0
    if not 0 < seconds <= 300:
        return jsonify({"ok": False, "error": "seconds must be 1-300."}), 400
    row = LessonProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson.id).first()
    if not row:
        row = LessonProgress(user_id=current_user.id, lesson_id=lesson.id,
                             time_spent_sec=0)
        db.session.add(row)
    row.time_spent_sec = (row.time_spent_sec or 0) + seconds
    db.session.commit()
    return jsonify({"ok": True, "total": row.time_spent_sec})


@student_bp.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
@student_only
def quiz(quiz_id):
    """Phase 6 — exam mode (§5.3): attempt limits, timed exams with live
    countdown + auto-submit, per-attempt question/option randomization, and
    the multi-type grading engine (app/assessment.py)."""
    from .assessment import (attempts_used, best_score, can_attempt,
                             grade_attempt, option_order_for_question,
                             order_questions_for_attempt)
    import json as _json
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.title == "__question_bank__":
        abort(404)
    course = quiz.module.course
    if not _active_enrollment_or_403(course.id):
        abort(403)
    questions = [q for q in quiz.questions if q.is_active]

    def submitted_count():
        return QuizAttempt.query.filter_by(
            quiz_id=quiz.id, user_id=current_user.id).filter(
            QuizAttempt.submitted_at.isnot(None)).count()

    def current_attempt():
        return (QuizAttempt.query.filter_by(quiz_id=quiz.id,
                                            user_id=current_user.id,
                                            submitted_at=None)
                .order_by(QuizAttempt.started_at.desc()).first())

    def time_left_seconds(attempt):
        if not quiz.time_limit_min or not attempt or not attempt.started_at:
            return None
        elapsed = (datetime.utcnow() - attempt.started_at).total_seconds()
        return max(0, int(quiz.time_limit_min * 60 - elapsed))

    def collect_answers(form):
        """Raw answers per question from the submitted form."""
        raw = {}
        for q in questions:
            key = f"q{q.id}"
            if q.qtype == "mcq_multiple":
                vals = form.getlist(key)
                raw[q.id] = ",".join(v.strip().upper() for v in vals if v.strip())
            elif q.qtype == "matching":
                pairs = q.answer.get("pairs", [])
                mapping = {}
                for i, (left, _right) in enumerate(pairs):
                    mapping[left] = form.get(f"{key}_m{i}", "")
                raw[q.id] = _json.dumps(mapping)
            else:
                raw[q.id] = form.get(key, "")
        return raw

    def finalize(attempt, raw_answers, expired=False):
        ordered = order_questions_for_attempt(
            quiz, questions, seed=attempt.id or 0)
        # keep only questions still on the quiz, in the stored order
        by_id = {q.id: q for q in questions}
        stored = attempt.question_ids_in_order
        ordered = [by_id[i] for i in stored if i in by_id] or ordered
        per_q, score, total, pending = grade_attempt(quiz, ordered, raw_answers)
        attempt.score = score
        attempt.total = total
        attempt.submitted_at = datetime.utcnow()
        attempt.time_expired = expired
        attempt.pending_review = pending
        for q, raw, g in per_q:
            db.session.add(QuizAnswer(
                attempt_id=attempt.id, question_id=q.id,
                chosen=raw if isinstance(raw, str) else _json.dumps(raw),
                is_correct=g.is_correct, marks_awarded=g.marks_awarded,
                needs_review=g.needs_review))
        db.session.commit()
        # Phase 10: real event — quiz submitted (§25.2)
        try:
            from . import hardening as _H
            _H.dispatch_webhook("quiz.submitted", {
                "attempt_id": attempt.id, "quiz_id": quiz.id,
                "quiz_title": quiz.title,
                "course_id": course.id, "course_title": course.title,
                "user_id": current_user.id, "user_name": current_user.name,
                "score": attempt.score, "total": attempt.total,
                "percent": attempt.percent,
                "pending_review": bool(pending)})
        except Exception:
            pass
        # Phase 8: quiz points (base + score-scaled bonus) + streak/badges
        _pts, new_badges = G.award_points(
            current_user.id, "quiz_attempt", "attempt", attempt.id)
        bonus = int(attempt.percent * G.bonus_rate(
            G.QUIZ_BONUS_RATE_SETTING, 0.2))
        if bonus > 0:
            _b2, more = G.award_points(
                current_user.id, "quiz_score_bonus", "attempt", attempt.id,
                points=bonus)
            new_badges = (new_badges or []) + (more or [])
        _flash_new_badges(new_badges)
        if not pending:
            cert = check_and_issue_certificate(current_user.id, course.id)
            if cert:
                flash("Course completed! Your certificate is ready.", "success")
                return redirect(url_for("student.certificates"))
        else:
            flash("Submitted! Descriptive answers are pending faculty review.",
                  "info")
        return redirect(url_for("student.quiz_result", attempt_id=attempt.id))

    if request.method == "POST":
        attempt = current_attempt()
        if attempt is None:
            # Direct POST (no GET first): start and submit immediately.
            allowed, reason = can_attempt(quiz, current_user.id)
            if not allowed:
                flash(reason, "warning")
                return redirect(url_for("student.quiz", quiz_id=quiz.id))
            attempt = QuizAttempt(quiz_id=quiz.id, user_id=current_user.id,
                                  started_at=datetime.utcnow(),
                                  submitted_at=None,
                                  question_order=_json.dumps([q.id for q in questions]))
            db.session.add(attempt)
            db.session.flush()
        expired = time_left_seconds(attempt) == 0
        return finalize(attempt, collect_answers(request.form), expired=expired)

    # GET — start or resume
    allowed, reason = can_attempt(quiz, current_user.id)
    if not allowed:
        flash(reason, "warning")
        attempts = (QuizAttempt.query.filter_by(quiz_id=quiz.id,
                                                user_id=current_user.id)
                    .filter(QuizAttempt.submitted_at.isnot(None))
                    .order_by(QuizAttempt.submitted_at.desc()).all())
        return render_template("quiz.html", quiz=quiz, course=course,
                               attempts=attempts, blocked=True,
                               best=best_score(quiz, current_user.id))
    attempt = current_attempt()
    if attempt is None:
        # random seed per fresh attempt so two attempts differ
        import random as _random
        seed = _random.randrange(1, 10 ** 9)
        ordered_ids = [q.id for q in order_questions_for_attempt(
            quiz, questions, seed=seed)]
        attempt = QuizAttempt(
            quiz_id=quiz.id, user_id=current_user.id,
            started_at=datetime.utcnow(), submitted_at=None,
            question_order=_json.dumps(ordered_ids))
        db.session.add(attempt)
        db.session.commit()
    remaining = time_left_seconds(attempt)
    if remaining == 0:
        # time ran out before they even loaded the page
        return finalize(attempt, {}, expired=True)
    by_id = {q.id: q for q in questions}
    ordered = [by_id[i] for i in attempt.question_ids_in_order if i in by_id]
    if not ordered:
        ordered = list(questions)
    opt_orders = {q.id: option_order_for_question(
        quiz, q, seed=(attempt.id or 0) * 100003 + q.id) for q in ordered}
    attempts = (QuizAttempt.query.filter_by(quiz_id=quiz.id,
                                            user_id=current_user.id)
                .filter(QuizAttempt.submitted_at.isnot(None))
                .order_by(QuizAttempt.submitted_at.desc()).all())
    match_rights = {}
    for q in ordered:
        if q.qtype == "matching":
            rights = [r for _, r in q.answer.get("pairs", [])]
            import random as _random
            _random.Random((attempt.id or 0) * 7919 + q.id).shuffle(rights)
            match_rights[q.id] = rights
    return render_template(
        "quiz.html", quiz=quiz, course=course, attempts=attempts,
        attempt=attempt, questions_ordered=ordered, opt_orders=opt_orders,
        match_rights=match_rights, remaining=remaining,
        used=submitted_count(), best=best_score(quiz, current_user.id))


@student_bp.route("/quiz/result/<int:attempt_id>")
@student_only
def quiz_result(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    if attempt.user_id != current_user.id:
        abort(403)
    ordered_answers = sorted(attempt.answers,
                             key=lambda a: (a.question.position or 0, a.id))
    return render_template("quiz_result.html", attempt=attempt,
                           answers=ordered_answers,
                           course=attempt.quiz.module.course)


@student_bp.route("/assignments")
@student_only
def assignments():
    enrollments = Enrollment.query.filter_by(
        user_id=current_user.id, status=Enrollment.STATUS_ACTIVE).all()
    course_ids = [e.course_id for e in enrollments]
    items = []
    if course_ids:
        items = (Assignment.query.filter(Assignment.course_id.in_(course_ids))
                 .order_by(Assignment.due_date).all())
    subs = {s.assignment_id: s for s in Submission.query.filter_by(
        user_id=current_user.id).all()}
    return render_template("assignments.html", assignments=items, subs=subs)


@student_bp.route("/assignment/<int:assignment_id>", methods=["GET", "POST"])
@student_only
def assignment_detail(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    if not _active_enrollment_or_403(assignment.course_id):
        abort(403)
    sub = Submission.query.filter_by(
        assignment_id=assignment.id, user_id=current_user.id).first()
    if request.method == "POST":
        note = request.form.get("note", "").strip()
        file = request.files.get("file")
        filename = ""
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_SUBMIT_EXTS:
                flash("File type not allowed.", "danger")
                return redirect(url_for("student.assignment_detail",
                                        assignment_id=assignment.id))
            filename = f"sub_{assignment.id}_{current_user.id}_{uuid.uuid4().hex[:8]}." \
                       f"{secure_filename(file.filename).rsplit('.', 1)[-1].lower()}"
            file.save(os.path.join(current_app.config["UPLOAD_DIR"], filename))
        if not filename and not note:
            flash("Attach a file or write a note.", "warning")
            return redirect(url_for("student.assignment_detail",
                                    assignment_id=assignment.id))
        if sub:
            if sub.file_path:  # replace old file
                old = os.path.join(current_app.config["UPLOAD_DIR"], sub.file_path)
                if os.path.exists(old):
                    os.remove(old)
            sub.file_path, sub.note = filename, note
            sub.submitted_at = datetime.utcnow()
            sub.grade, sub.feedback, sub.graded_at = None, "", None
        else:
            sub = Submission(assignment_id=assignment.id, user_id=current_user.id,
                             file_path=filename, note=note)
            db.session.add(sub)
        db.session.commit()
        # Phase 8: assignment points (idempotent per assignment)
        _pts, new_badges = G.award_points(
            current_user.id, "assignment_submit", "assignment",
            assignment.id)
        _flash_new_badges(new_badges)
        flash("Assignment submitted.", "success")
        return redirect(url_for("student.assignment_detail", assignment_id=assignment.id))
    return render_template("assignment_detail.html", assignment=assignment, sub=sub)


# ------------------------------------------------------- Phase 6: projects
@student_bp.route("/project/submission/<int:sub_id>/file")
@login_required
def project_file(sub_id):
    """Download a project submission file (own, or faculty/admin)."""
    sub = ProjectSubmission.query.get_or_404(sub_id)
    if not (sub.user_id == current_user.id or current_user.role in
            ("admin", "manager") or (
                current_user.role == "faculty"
                and sub.project.course.instructor_id == current_user.id)):
        abort(403)
    path = os.path.join(current_app.config["UPLOAD_DIR"], sub.file_path)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True)


@student_bp.route("/projects")
@student_only
def projects():
    """Student: project briefs for enrolled courses + my submissions."""
    course_ids = [e.course_id for e in Enrollment.query.filter_by(
        user_id=current_user.id).filter(
        Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                               Enrollment.STATUS_COMPLETED])).all()]
    items = (Project.query.filter(Project.course_id.in_(course_ids),
                                 Project.is_active.is_(True))
             .order_by(Project.deadline.asc()).all()) if course_ids else []
    subs = {s.project_id: s for s in ProjectSubmission.query.filter_by(
        user_id=current_user.id).all()}
    return render_template("projects.html", projects=items, subs=subs)


@student_bp.route("/project/<int:project_id>", methods=["GET", "POST"])
@student_only
def project_detail(project_id):
    """Student: view brief + submit (URL + file + notes). Resubmit allowed
    before the deadline; re-evaluation resets on resubmit."""
    project = Project.query.get_or_404(project_id)
    if not _active_enrollment_or_403(project.course_id):
        abort(403)
    sub = ProjectSubmission.query.filter_by(
        project_id=project.id, user_id=current_user.id).first()
    if request.method == "POST":
        if project.is_overdue:
            flash("The deadline has passed — submissions are closed.", "danger")
            return redirect(url_for("student.project_detail",
                                    project_id=project.id))
        url = request.form.get("project_url", "").strip()[:300]
        notes = request.form.get("notes", "").strip()
        file = request.files.get("file")
        filename = sub.file_path if sub else ""
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_SUBMIT_EXTS:
                flash("File type not allowed.", "danger")
                return redirect(url_for("student.project_detail",
                                        project_id=project.id))
            if filename:
                old = os.path.join(current_app.config["UPLOAD_DIR"], filename)
                if os.path.exists(old):
                    os.remove(old)
            filename = (f"proj_{project.id}_{current_user.id}_"
                        f"{uuid.uuid4().hex[:8]}."
                        f"{secure_filename(file.filename).rsplit('.', 1)[-1].lower()}")
            file.save(os.path.join(current_app.config["UPLOAD_DIR"], filename))
        if not filename and not url and not notes:
            flash("Add a project URL, attach a file, or write notes.", "warning")
            return redirect(url_for("student.project_detail",
                                    project_id=project.id))
        if sub:
            sub.project_url, sub.file_path, sub.notes = url, filename, notes
            sub.status = "submitted"  # back into the evaluation queue
            sub.marks, sub.feedback = None, ""
            sub.submitted_at = datetime.utcnow()
            sub.evaluated_at, sub.evaluated_by = None, None
        else:
            sub = ProjectSubmission(project_id=project.id,
                                    user_id=current_user.id,
                                    project_url=url, file_path=filename,
                                    notes=notes, status="submitted")
            db.session.add(sub)
        db.session.commit()
        # Phase 8: project submission points (idempotent per project)
        _pts, new_badges = G.award_points(
            current_user.id, "project_submit", "project", project.id)
        _flash_new_badges(new_badges)
        flash("Project submitted for evaluation.", "success")
        return redirect(url_for("student.project_detail", project_id=project.id))
    return render_template("project_detail.html", project=project, sub=sub,
                           can_resubmit=not project.is_overdue)


@student_bp.route("/certificates")
@student_only
def certificates():
    certs = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template("certificates.html", certs=certs)


@student_bp.route("/certificate/<code>/download")
@student_only
def certificate_download(code):
    cert = Certificate.query.filter_by(code=code, user_id=current_user.id).first_or_404()
    path = certificate_path(cert, current_app.config["UPLOAD_DIR"])
    if not os.path.exists(path):
        generate_certificate_pdf(cert, path)
    return send_file(path, as_attachment=True,
                     download_name=f"SayyedEdVantage-{cert.code}.pdf")


# ---------------------------------------------------------------- reviews
@student_bp.route("/course/<slug>/review", methods=["POST"])
@student_only
def review_add(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    enr = Enrollment.query.filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course.id,
        Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                               Enrollment.STATUS_COMPLETED])).first()
    if not enr:
        flash("Enroll in this course to leave a review.", "warning")
        return redirect(url_for("main.course_detail", slug=slug))
    if Review.query.filter_by(user_id=current_user.id,
                              course_id=course.id).first():
        flash("You've already reviewed this course.", "info")
        return redirect(url_for("main.course_detail", slug=slug))
    try:
        rating = int(request.form.get("rating", 0) or 0)
    except ValueError:
        rating = 0
    text = request.form.get("text", "").strip()
    if rating < 1 or rating > 5:
        flash("Please pick a rating from 1 to 5 stars.", "danger")
    else:
        db.session.add(Review(course_id=course.id, user_id=current_user.id,
                              rating=rating, text=text))
        db.session.commit()
        flash("Thanks for your review! ⭐", "success")
    return redirect(url_for("main.course_detail", slug=slug))


# ---------------------------------------------------------------- wishlist
@student_bp.route("/wishlist")
@student_only
def wishlist():
    items = (Wishlist.query.filter_by(user_id=current_user.id)
             .order_by(Wishlist.created_at.desc()).all())
    return render_template("wishlist.html", items=items)


@student_bp.route("/course/<slug>/wishlist", methods=["POST"])
@student_only
def wishlist_toggle(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    existing = Wishlist.query.filter_by(user_id=current_user.id,
                                        course_id=course.id).first()
    if existing:
        db.session.delete(existing)
        flash(f"Removed {course.title} from your wishlist.", "info")
    else:
        db.session.add(Wishlist(user_id=current_user.id, course_id=course.id))
        flash(f"Saved {course.title} to your wishlist. ❤", "success")
    db.session.commit()
    nxt = request.form.get("next") or url_for("main.course_detail", slug=slug)
    return redirect(nxt)


# ---------------------------------------------------------------- UI14: student utility pages
def _my_enrolled_course_ids():
    return [e.course_id for e in
            Enrollment.query.filter_by(user_id=current_user.id)
            .filter(Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                                           Enrollment.STATUS_COMPLETED])).all()]


@student_bp.route("/announcements")
@student_only
def announcements():
    """UI14: student's announcement inbox."""
    items = (Announcement.query.filter_by(active=True)
             .order_by(Announcement.created_at.desc()).all())
    return render_template("student_announcements.html", announcements=items)


@student_bp.route("/downloads")
@student_only
def downloads():
    """UI14: certificate downloads + PDF lesson materials from enrolled courses."""
    certs = (Certificate.query.filter_by(user_id=current_user.id)
             .order_by(Certificate.issued_at.desc()).all())
    materials = []
    for cid in _my_enrolled_course_ids():
        course = db.session.get(Course, cid)
        if not course:
            continue
        for lesson in course.lessons:
            if lesson.kind == Lesson.KIND_PDF and lesson.pdf_file:
                materials.append({
                    "title": course.title + " — " + lesson.title,
                    "url": url_for("main.uploaded_file",
                                   filename=lesson.pdf_file),
                })
    return render_template("student_downloads.html", certs=certs,
                           materials=materials)


@student_bp.route("/quizzes")
@student_only
def quizzes():
    """UI14: all quizzes across enrolled courses, with attempt stats."""
    items = []
    for cid in _my_enrolled_course_ids():
        course = db.session.get(Course, cid)
        if not course:
            continue
        for q in course.quizzes:
            if q.title == "__question_bank__":
                continue
            attempts = (QuizAttempt.query.filter_by(
                            quiz_id=q.id, user_id=current_user.id)
                        .filter(QuizAttempt.submitted_at.isnot(None)).count())
            best = _policy_attempt(q, current_user.id)
            items.append({"quiz": q, "course": course,
                          "attempts": attempts,
                          "best": best.percent if best else None})
    return render_template("student_quizzes.html", quizzes=items)


@student_bp.route("/profile", methods=["GET", "POST"])
@student_only
def profile():
    """Student profile: name/phone, avatar photo upload, password change."""
    user = db.session.get(User, current_user.id)
    if request.method == "POST":
        action = request.form.get("action", "profile")
        if action == "photo":
            _profile_photo_upload(user)
        elif action == "password":
            _profile_password_change(user)
        else:
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            if not name:
                flash("Name can't be empty.", "danger")
            else:
                user.name = name
                user.phone = phone
                db.session.commit()
                flash("Profile updated.", "success")
        return redirect(url_for("student.profile"))
    return render_template("student_profile.html", user=user)


ALLOWED_AVATAR_EXTS = {"png", "jpg", "jpeg", "webp"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _avatar_dir():
    d = os.path.join(current_app.config["UPLOAD_DIR"], "avatars")
    os.makedirs(d, exist_ok=True)
    return d


def _profile_photo_upload(user):
    """Handle the avatar upload from the profile page."""
    file = request.files.get("photo")
    if not file or not file.filename:
        flash("Choose a photo to upload.", "warning")
        return
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_AVATAR_EXTS:
        flash("Photo must be PNG, JPG, JPEG or WebP.", "danger")
        return
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > AVATAR_MAX_BYTES:
        flash("Photo must be under 2 MB.", "danger")
        return
    avatar_dir = _avatar_dir()
    filename = f"user_{user.id}.{ext}"
    for old_ext in ALLOWED_AVATAR_EXTS:  # drop previous avatar if ext changed
        old = os.path.join(avatar_dir, f"user_{user.id}.{old_ext}")
        if old_ext != ext and os.path.exists(old):
            os.remove(old)
    file.save(os.path.join(avatar_dir, filename))
    user.photo = f"avatars/{filename}"
    db.session.commit()
    flash("Profile photo updated.", "success")


def _profile_password_change(user):
    """Change password after verifying the current one."""
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if not user.check_password(current):
        flash("Current password is incorrect.", "danger")
        return
    if len(new) < 8:
        flash("New password must be at least 8 characters.", "danger")
        return
    if new != confirm:
        flash("New passwords don't match.", "danger")
        return
    user.set_password(new)
    db.session.commit()
    flash("Password changed successfully.", "success")
