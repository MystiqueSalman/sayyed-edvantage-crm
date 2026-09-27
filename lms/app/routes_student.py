"""Student routes: dashboard, learning, quizzes, assignments, certificates."""
import os
import uuid
from datetime import datetime, timedelta

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user
from werkzeug.utils import secure_filename

from . import db
from .decorators import role_required
from .models import (Announcement, Assignment, Certificate, Course, Enrollment, Lesson,
                     LessonProgress, LiveSession, Module, Quiz, QuizAttempt, Review,
                     Submission, Wishlist)
from .pdfcert import certificate_path, generate_certificate_pdf
from .routes_crm import _onboarding_for  # Phase 4: onboarding checklist

student_bp = Blueprint("student", __name__)
student_only = role_required("student")

ALLOWED_SUBMIT_EXTS = {"pdf", "doc", "docx", "zip", "txt", "png", "jpg", "jpeg", "py", "ipynb"}


def _active_enrollment_or_403(course_id):
    enr = Enrollment.query.filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course_id,
        Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                               Enrollment.STATUS_COMPLETED])).first()
    if not enr and current_user.role != "student":
        return None
    return enr


def check_and_issue_certificate(user_id, course_id):
    """Issue a certificate when all lessons are done and every module quiz is passed."""
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
        best = (QuizAttempt.query.filter_by(quiz_id=quiz.id, user_id=user_id)
                .order_by(QuizAttempt.score.desc()).first())
        if not best or best.percent < quiz.pass_percent:
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
    return render_template("dashboard.html", enrollments=enrollments,
                           pending=pending, certs=certs, live_sessions=live_sessions,
                           now=now, onboarding=_onboarding_for(current_user))


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
    module_quiz = lesson.module.quizzes[0] if lesson.module.quizzes else None
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


@student_bp.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
@student_only
def quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    course = quiz.module.course
    if not _active_enrollment_or_403(course.id):
        abort(403)
    if request.method == "POST":
        score, total = 0, len(quiz.questions)
        for q in quiz.questions:
            if request.form.get(f"q{q.id}", "").upper() == q.correct:
                score += 1
        attempt = QuizAttempt(quiz_id=quiz.id, user_id=current_user.id,
                              score=score, total=total)
        db.session.add(attempt)
        db.session.commit()
        cert = check_and_issue_certificate(current_user.id, course.id)
        if cert:
            flash("Course completed! Your certificate is ready.", "success")
            return redirect(url_for("student.certificates"))
        return redirect(url_for("student.quiz_result", attempt_id=attempt.id))
    attempts = (QuizAttempt.query.filter_by(quiz_id=quiz.id, user_id=current_user.id)
                .order_by(QuizAttempt.taken_at.desc()).all())
    return render_template("quiz.html", quiz=quiz, course=course, attempts=attempts)


@student_bp.route("/quiz/result/<int:attempt_id>")
@student_only
def quiz_result(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    if attempt.user_id != current_user.id:
        abort(403)
    return render_template("quiz_result.html", attempt=attempt,
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
        flash("Assignment submitted.", "success")
        return redirect(url_for("student.assignment_detail", assignment_id=assignment.id))
    return render_template("assignment_detail.html", assignment=assignment, sub=sub)


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
