"""Shared content management (courses, modules, lessons, quizzes, assignments,
recordings, submissions). Allowed for admin, manager, and faculty — faculty only
for courses they instruct. Registered as manage_bp."""
import os
import uuid
from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user
from werkzeug.utils import secure_filename

from . import db
from .decorators import content_manager_required
from .models import (Assignment, Course, Lesson, LiveSession, Module, Question, Quiz,
                     Recording, Submission)

manage_bp = Blueprint("manage", __name__, url_prefix="/manage")

ALLOWED_PDF_EXTS = {"pdf"}


def _course_or_403(course_id):
    course = Course.query.get_or_404(course_id)
    if not current_user.can_manage_course(course):
        abort(403)
    return course


def _save_pdf_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_PDF_EXTS:
        return None
    name = f"lesson_{uuid.uuid4().hex[:12]}.{ext}"
    file_storage.save(os.path.join(current_app.config["UPLOAD_DIR"], name))
    return name


# ---------------------------------------------------------------- course home
@manage_bp.route("/course/<int:course_id>")
@content_manager_required
def course_home(course_id):
    course = _course_or_403(course_id)
    return render_template("manage_course.html", course=course)


# ---------------------------------------------------------------- modules
@manage_bp.route("/course/<int:course_id>/module/new", methods=["GET", "POST"])
@content_manager_required
def module_new(course_id):
    course = _course_or_403(course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
        else:
            pos = (db.session.query(db.func.max(Module.position))
                   .filter_by(course_id=course.id).scalar() or 0) + 1
            db.session.add(Module(course_id=course.id, title=title, position=pos))
            db.session.commit()
            flash("Module added.", "success")
            return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_module_form.html", course=course, module=None)


@manage_bp.route("/module/<int:module_id>/edit", methods=["GET", "POST"])
@content_manager_required
def module_edit(module_id):
    module = Module.query.get_or_404(module_id)
    course = _course_or_403(module.course_id)
    if request.method == "POST":
        module.title = request.form.get("title", "").strip() or module.title
        db.session.commit()
        flash("Module updated.", "success")
        return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_module_form.html", course=course, module=module)


@manage_bp.route("/module/<int:module_id>/delete", methods=["POST"])
@content_manager_required
def module_delete(module_id):
    module = Module.query.get_or_404(module_id)
    course = _course_or_403(module.course_id)
    db.session.delete(module)
    db.session.commit()
    flash("Module deleted.", "info")
    return redirect(url_for("manage.course_home", course_id=course.id))


# ---------------------------------------------------------------- lessons
@manage_bp.route("/module/<int:module_id>/lesson/new", methods=["GET", "POST"])
@content_manager_required
def lesson_new(module_id):
    module = Module.query.get_or_404(module_id)
    course = _course_or_403(module.course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        kind = request.form.get("kind", "text")
        if not title or kind not in ("text", "video", "pdf"):
            flash("Title and valid lesson type are required.", "danger")
        else:
            pdf_file = ""
            if kind == "pdf":
                pdf_file = _save_pdf_upload(request.files.get("pdf_file"))
                if pdf_file is None:
                    flash("Only PDF files are allowed.", "danger")
                    return render_template("manage_lesson_form.html", course=course,
                                           module=module, lesson=None)
            pos = (db.session.query(db.func.max(Lesson.position))
                   .filter_by(module_id=module.id).scalar() or 0) + 1
            try:
                drip = max(0, int(request.form.get("available_after_days", 0) or 0))
            except ValueError:
                drip = 0
            db.session.add(Lesson(
                module_id=module.id, title=title, position=pos, kind=kind,
                body=request.form.get("body", ""),
                video_url=request.form.get("video_url", "").strip(),
                pdf_file=pdf_file or "",
                available_after_days=drip))
            db.session.commit()
            flash("Lesson added.", "success")
            return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_lesson_form.html", course=course, module=module,
                           lesson=None)


@manage_bp.route("/lesson/<int:lesson_id>/edit", methods=["GET", "POST"])
@content_manager_required
def lesson_edit(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = _course_or_403(lesson.module.course_id)
    if request.method == "POST":
        lesson.title = request.form.get("title", "").strip() or lesson.title
        kind = request.form.get("kind", lesson.kind)
        if kind in ("text", "video", "pdf"):
            lesson.kind = kind
        lesson.body = request.form.get("body", "")
        lesson.video_url = request.form.get("video_url", "").strip()
        try:
            lesson.available_after_days = max(
                0, int(request.form.get("available_after_days",
                                        lesson.available_after_days or 0) or 0))
        except ValueError:
            pass
        if lesson.kind == "pdf":
            pdf_file = _save_pdf_upload(request.files.get("pdf_file"))
            if pdf_file is None:
                flash("Only PDF files are allowed.", "danger")
                return render_template("manage_lesson_form.html", course=course,
                                       module=lesson.module, lesson=lesson)
            if pdf_file:
                if lesson.pdf_file:
                    old = os.path.join(current_app.config["UPLOAD_DIR"], lesson.pdf_file)
                    if os.path.exists(old):
                        os.remove(old)
                lesson.pdf_file = pdf_file
        db.session.commit()
        flash("Lesson updated.", "success")
        return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_lesson_form.html", course=course,
                           module=lesson.module, lesson=lesson)


@manage_bp.route("/lesson/<int:lesson_id>/delete", methods=["POST"])
@content_manager_required
def lesson_delete(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = _course_or_403(lesson.module.course_id)
    db.session.delete(lesson)
    db.session.commit()
    flash("Lesson deleted.", "info")
    return redirect(url_for("manage.course_home", course_id=course.id))


# ---------------------------------------------------------------- quizzes
@manage_bp.route("/module/<int:module_id>/quiz/new", methods=["GET", "POST"])
@content_manager_required
def quiz_new(module_id):
    module = Module.query.get_or_404(module_id)
    course = _course_or_403(module.course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
        else:
            quiz = Quiz(module_id=module.id, title=title,
                        pass_percent=int(request.form.get("pass_percent", 60) or 60))
            db.session.add(quiz)
            db.session.commit()
            return redirect(url_for("manage.quiz_questions", quiz_id=quiz.id))
    return render_template("manage_quiz_form.html", course=course, module=module,
                           quiz=None)


@manage_bp.route("/quiz/<int:quiz_id>/questions", methods=["GET", "POST"])
@content_manager_required
def quiz_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    course = _course_or_403(quiz.module.course_id)
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        correct = request.form.get("correct", "A").upper()
        if not text or correct not in "ABCD":
            flash("Question text and a valid correct option are required.", "danger")
        else:
            pos = (db.session.query(db.func.max(Question.position))
                   .filter_by(quiz_id=quiz.id).scalar() or 0) + 1
            db.session.add(Question(
                quiz_id=quiz.id, text=text,
                option_a=request.form.get("option_a", ""),
                option_b=request.form.get("option_b", ""),
                option_c=request.form.get("option_c", ""),
                option_d=request.form.get("option_d", ""),
                correct=correct, position=pos))
            db.session.commit()
            flash("Question added.", "success")
    return render_template("manage_quiz_questions.html", course=course, quiz=quiz)


@manage_bp.route("/question/<int:question_id>/delete", methods=["POST"])
@content_manager_required
def question_delete(question_id):
    q = Question.query.get_or_404(question_id)
    course = _course_or_403(q.quiz.module.course_id)
    quiz_id = q.quiz_id
    db.session.delete(q)
    db.session.commit()
    flash("Question deleted.", "info")
    return redirect(url_for("manage.quiz_questions", quiz_id=quiz_id))


@manage_bp.route("/quiz/<int:quiz_id>/delete", methods=["POST"])
@content_manager_required
def quiz_delete(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    course = _course_or_403(quiz.module.course_id)
    db.session.delete(quiz)
    db.session.commit()
    flash("Quiz deleted.", "info")
    return redirect(url_for("manage.course_home", course_id=course.id))


# ---------------------------------------------------------------- assignments
@manage_bp.route("/course/<int:course_id>/assignment/new", methods=["GET", "POST"])
@content_manager_required
def assignment_new(course_id):
    course = _course_or_403(course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
        else:
            due = request.form.get("due_date", "").strip()
            db.session.add(Assignment(
                course_id=course.id, title=title,
                description=request.form.get("description", ""),
                due_date=datetime.strptime(due, "%Y-%m-%d").date() if due else None,
                max_marks=int(request.form.get("max_marks", 100) or 100),
                created_by=current_user.id))
            db.session.commit()
            flash("Assignment created.", "success")
            return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_assignment_form.html", course=course, assignment=None)


@manage_bp.route("/assignment/<int:assignment_id>/edit", methods=["GET", "POST"])
@content_manager_required
def assignment_edit(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    course = _course_or_403(assignment.course_id)
    if request.method == "POST":
        assignment.title = request.form.get("title", "").strip() or assignment.title
        assignment.description = request.form.get("description", "")
        due = request.form.get("due_date", "").strip()
        assignment.due_date = datetime.strptime(due, "%Y-%m-%d").date() if due else None
        assignment.max_marks = int(request.form.get("max_marks", 100) or 100)
        db.session.commit()
        flash("Assignment updated.", "success")
        return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_assignment_form.html", course=course,
                           assignment=assignment)


@manage_bp.route("/assignment/<int:assignment_id>/delete", methods=["POST"])
@content_manager_required
def assignment_delete(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    course = _course_or_403(assignment.course_id)
    db.session.delete(assignment)
    db.session.commit()
    flash("Assignment deleted.", "info")
    return redirect(url_for("manage.course_home", course_id=course.id))


@manage_bp.route("/assignment/<int:assignment_id>/submissions")
@content_manager_required
def assignment_submissions(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    _course_or_403(assignment.course_id)
    subs = Submission.query.filter_by(assignment_id=assignment.id).all()
    return render_template("manage_submissions.html", assignment=assignment, subs=subs)


@manage_bp.route("/submission/<int:submission_id>/grade", methods=["GET", "POST"])
@content_manager_required
def submission_grade(submission_id):
    sub = Submission.query.get_or_404(submission_id)
    _course_or_403(sub.assignment.course_id)
    if request.method == "POST":
        try:
            grade = float(request.form.get("grade", ""))
        except ValueError:
            flash("Enter a numeric grade.", "danger")
            return render_template("manage_grade.html", sub=sub)
        sub.grade = grade
        sub.feedback = request.form.get("feedback", "")
        sub.graded_at = datetime.utcnow()
        db.session.commit()
        try:
            from .emailer import send_graded_email
            send_graded_email(sub)
        except Exception:
            pass  # email must never break grading
        flash("Submission graded.", "success")
        return redirect(url_for("manage.assignment_submissions",
                                assignment_id=sub.assignment_id))
    return render_template("manage_grade.html", sub=sub)


@manage_bp.route("/submission/<int:submission_id>/file")
@content_manager_required
def submission_file(submission_id):
    sub = Submission.query.get_or_404(submission_id)
    _course_or_403(sub.assignment.course_id)
    if not sub.file_path:
        abort(404)
    return send_file(os.path.join(current_app.config["UPLOAD_DIR"], sub.file_path),
                     as_attachment=True)


# ---------------------------------------------------------------- live sessions (Jitsi)
def _parse_starts_at(value):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@manage_bp.route("/course/<int:course_id>/live/new", methods=["GET", "POST"])
@content_manager_required
def live_new(course_id):
    course = _course_or_403(course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        starts_at = _parse_starts_at(request.form.get("starts_at"))
        try:
            duration = int(request.form.get("duration_min", 60) or 60)
        except ValueError:
            duration = 60
        if not title or not starts_at:
            flash("Title and start date/time are required.", "danger")
        else:
            room = f"se-{course.slug}-{uuid.uuid4().hex[:8]}"
            db.session.add(LiveSession(
                course_id=course.id, title=title, starts_at=starts_at,
                duration_min=max(15, min(480, duration)), room_name=room,
                created_by=current_user.id,
                recording_url=request.form.get("recording_url", "").strip()))
            db.session.commit()
            flash("Live class scheduled.", "success")
            return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_live_form.html", course=course, session=None)


@manage_bp.route("/live/<int:session_id>/edit", methods=["GET", "POST"])
@content_manager_required
def live_edit(session_id):
    sess = LiveSession.query.get_or_404(session_id)
    course = _course_or_403(sess.course_id)
    if request.method == "POST":
        sess.title = request.form.get("title", "").strip() or sess.title
        starts_at = _parse_starts_at(request.form.get("starts_at"))
        if starts_at:
            sess.starts_at = starts_at
            sess.sent_reminder = False  # re-arm reminder on reschedule
        try:
            sess.duration_min = max(15, min(480,
                int(request.form.get("duration_min", sess.duration_min) or 60)))
        except ValueError:
            pass
        sess.recording_url = request.form.get("recording_url", "").strip()
        db.session.commit()
        flash("Live class updated.", "success")
        return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_live_form.html", course=course, session=sess)


@manage_bp.route("/live/<int:session_id>/delete", methods=["POST"])
@content_manager_required
def live_delete(session_id):
    sess = LiveSession.query.get_or_404(session_id)
    course = _course_or_403(sess.course_id)
    db.session.delete(sess)
    db.session.commit()
    flash("Live class deleted.", "info")
    return redirect(url_for("manage.course_home", course_id=course.id))


# ---------------------------------------------------------------- recordings
@manage_bp.route("/course/<int:course_id>/recording/new", methods=["GET", "POST"])
@content_manager_required
def recording_new(course_id):
    course = _course_or_403(course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
        else:
            rec_on = request.form.get("recorded_on", "").strip()
            db.session.add(Recording(
                course_id=course.id, title=title,
                video_url=request.form.get("video_url", "").strip(),
                duration_min=int(request.form.get("duration_min", 0) or 0),
                recorded_on=datetime.strptime(rec_on, "%Y-%m-%d").date() if rec_on else None))
            db.session.commit()
            flash("Recording added.", "success")
            return redirect(url_for("manage.course_home", course_id=course.id))
    return render_template("manage_recording_form.html", course=course)


@manage_bp.route("/recording/<int:recording_id>/delete", methods=["POST"])
@content_manager_required
def recording_delete(recording_id):
    rec = Recording.query.get_or_404(recording_id)
    course = _course_or_403(rec.course_id)
    db.session.delete(rec)
    db.session.commit()
    flash("Recording deleted.", "info")
    return redirect(url_for("manage.course_home", course_id=course.id))
