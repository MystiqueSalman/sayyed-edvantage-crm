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
from .models import (Assignment, Course, Lesson, LiveSession, Module, Project,
                     ProjectSubmission, Question, Quiz, QuizAnswer, QuizAttempt,
                     Recording, Submission, User)

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
def _exam_settings_from_form(form, quiz=None):
    """Parse Phase 6 exam settings from a form (create or edit)."""
    quiz = quiz or Quiz()
    quiz.title = form.get("title", "").strip() or quiz.title or "Untitled quiz"
    quiz.pass_percent = max(1, min(100, int(form.get("pass_percent", 60) or 60)))
    quiz.time_limit_min = max(0, int(form.get("time_limit_min", 0) or 0))
    quiz.shuffle_questions = bool(form.get("shuffle_questions"))
    quiz.shuffle_options = bool(form.get("shuffle_options"))
    quiz.negative_marking = max(0.0, min(2.0, float(form.get("negative_marking", 0) or 0)))
    quiz.max_attempts = max(0, int(form.get("max_attempts", 0) or 0))
    if form.get("score_policy") in ("best", "latest"):
        quiz.score_policy = form.get("score_policy")
    return quiz


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
            quiz = _exam_settings_from_form(request.form, Quiz(module_id=module.id))
            db.session.add(quiz)
            db.session.commit()
            return redirect(url_for("manage.quiz_questions", quiz_id=quiz.id))
    return render_template("manage_quiz_form.html", course=course, module=module,
                           quiz=None)


@manage_bp.route("/quiz/<int:quiz_id>/edit", methods=["GET", "POST"])
@content_manager_required
def quiz_edit(quiz_id):
    """Edit quiz title + Phase 6 exam settings (§5.3)."""
    quiz = Quiz.query.get_or_404(quiz_id)
    course = _course_or_403(quiz.module.course_id)
    if request.method == "POST":
        _exam_settings_from_form(request.form, quiz)
        db.session.commit()
        flash("Quiz settings saved.", "success")
        return redirect(url_for("manage.quiz_questions", quiz_id=quiz.id))
    return render_template("manage_quiz_form.html", course=course,
                           module=quiz.module, quiz=quiz)


def _parse_question_form(form, course):
    """Parse a type-aware question form. Returns (kwargs, error)."""
    import json as _json
    text = form.get("text", "").strip()
    qtype = form.get("qtype", "mcq_single")
    if qtype not in ("mcq_single", "mcq_multiple", "true_false", "fill_blank",
                     "matching", "descriptive"):
        qtype = "mcq_single"
    if not text:
        return None, "Question text is required."
    try:
        marks = max(0.5, float(form.get("marks", 1) or 1))
    except ValueError:
        marks = 1.0
    difficulty = form.get("difficulty", "medium")
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    lesson_id = form.get("lesson_id", type=int) or None
    if lesson_id and lesson_id not in {l.id for l in course.lessons}:
        lesson_id = None
    kw = dict(text=text, qtype=qtype, difficulty=difficulty,
              topic=form.get("topic", "").strip()[:120],
              skills=form.get("skills", "").strip()[:200],
              marks=marks, lesson_id=lesson_id)
    answer_data = {}
    if qtype == "mcq_single":
        for opt in "abcd":
            kw[f"option_{opt}"] = form.get(f"option_{opt}", "").strip()[:300]
        correct = form.get("correct", "A").upper()
        if correct not in "ABCD" or not kw[f"option_{correct.lower()}"]:
            return None, "Pick a valid correct option with text."
        kw["correct"] = correct
    elif qtype == "mcq_multiple":
        for opt in "abcd":
            kw[f"option_{opt}"] = form.get(f"option_{opt}", "").strip()[:300]
        correct = [c for c in form.getlist("correct_multi") if c in "ABCD"]
        correct = [c for c in correct if kw[f"option_{c.lower()}"]]
        if len(correct) < 2:
            return None, "Select at least 2 correct options with text."
        answer_data["correct"] = correct
        kw["correct"] = correct[0]
    elif qtype == "true_false":
        kw["option_a"], kw["option_b"] = "True", "False"
        kw["option_c"], kw["option_d"] = "", ""
        correct = form.get("correct_tf", "true").lower()
        if correct not in ("true", "false"):
            return None, "Choose True or False."
        answer_data["correct"] = correct
        kw["correct"] = "T" if correct == "true" else "F"
    elif qtype == "fill_blank":
        accepted = [a.strip() for a in form.get("accepted", "").splitlines()
                    if a.strip()]
        if not accepted:
            return None, "Enter at least one accepted answer (one per line)."
        answer_data["accepted"] = accepted[:10]
    elif qtype == "matching":
        lefts = [l.strip() for l in form.get("match_left", "").splitlines()
                 if l.strip()]
        rights = [r.strip() for r in form.get("match_right", "").splitlines()
                  if r.strip()]
        if len(lefts) < 2 or len(lefts) != len(rights):
            return None, ("Enter matching pairs: same number of left and "
                          "right items (one per line, min 2 pairs).")
        answer_data["pairs"] = [[l, r] for l, r in zip(lefts[:8], rights[:8])]
    elif qtype == "descriptive":
        answer_data["model_answer"] = form.get("model_answer", "").strip()[:2000]
    kw["answer_data"] = _json.dumps(answer_data)
    return kw, ""


@manage_bp.route("/quiz/<int:quiz_id>/questions", methods=["GET", "POST"])
@content_manager_required
def quiz_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    course = _course_or_403(quiz.module.course_id)
    if request.method == "POST":
        kw, err = _parse_question_form(request.form, course)
        if err:
            flash(err, "danger")
        else:
            pos = (db.session.query(db.func.max(Question.position))
                   .filter_by(quiz_id=quiz.id).scalar() or 0) + 1
            db.session.add(Question(quiz_id=quiz.id, position=pos, **kw))
            db.session.commit()
            flash("Question added.", "success")
    return render_template("manage_quiz_questions.html", course=course, quiz=quiz,
                           lessons=course.lessons)


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


# ------------------------------------------------- Phase 6: question bank
@manage_bp.route("/question-bank")
@content_manager_required
def question_bank():
    """Faculty question bank (§5.2): filter/search across managed courses."""
    course_id = request.args.get("course_id", "")
    qtype = request.args.get("qtype", "")
    difficulty = request.args.get("difficulty", "")
    topic = request.args.get("topic", "").strip()
    active = request.args.get("active", "1")
    q = Question.query.join(Quiz, Question.quiz_id == Quiz.id).join(
        Module, Quiz.module_id == Module.id)
    courses = [c for c in Course.query.order_by(Course.title).all()
               if current_user.can_manage_course(c)]
    if not courses:
        abort(403)
    q = q.filter(Module.course_id.in_([c.id for c in courses]))
    if course_id.isdigit():
        q = q.filter(Module.course_id == int(course_id))
    if qtype:
        q = q.filter(Question.qtype == qtype)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    if topic:
        like = f"%{topic}%"
        q = q.filter(Question.topic.ilike(like) | Question.skills.ilike(like)
                    | Question.text.ilike(like))
    if active == "1":
        q = q.filter(Question.is_active.is_(True))
    elif active == "0":
        q = q.filter(Question.is_active.is_(False))
    items = q.order_by(Question.id.desc()).limit(300).all()
    return render_template("question_bank.html", questions=items, courses=courses,
                           f=request.args,
                           qtypes=["mcq_single", "mcq_multiple", "true_false",
                                   "fill_blank", "matching", "descriptive"])


@manage_bp.route("/question-bank/new", methods=["GET", "POST"])
@content_manager_required
def bank_question_new():
    """Create a bank question, optionally attaching it straight to a quiz."""
    courses = [c for c in Course.query.order_by(Course.title).all()
               if current_user.can_manage_course(c)]
    if not courses:
        abort(403)
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        course = next((c for c in courses if c.id == course_id), None)
        if not course:
            flash("Choose a course you manage.", "danger")
            return redirect(url_for("manage.bank_question_new"))
        kw, err = _parse_question_form(request.form, course)
        if err:
            flash(err, "danger")
        else:
            quiz_id = request.form.get("quiz_id", type=int)
            quiz = None
            if quiz_id:
                quiz = Quiz.query.get(quiz_id)
                if not quiz or quiz.module.course_id != course.id:
                    quiz, quiz_id = None, None
            if quiz is None:
                if not course.modules:
                    flash("This course has no modules yet.", "danger")
                    return redirect(url_for("manage.bank_question_new"))
                # bank-only placeholder quiz keeps bank questions queryable
                # through the normal quiz relationship (hidden from students)
                quiz = Quiz(module_id=course.modules[0].id,
                            title="__question_bank__")
                db.session.add(quiz)
                db.session.flush()
            pos = (db.session.query(db.func.max(Question.position))
                   .filter_by(quiz_id=quiz.id).scalar() or 0) + 1
            db.session.add(Question(quiz_id=quiz.id, position=pos, **kw))
            db.session.commit()
            flash("Question saved to the bank.", "success")
            return redirect(url_for("manage.question_bank"))
    quizzes = []
    for c in courses:
        for m in c.modules:
            quizzes.extend(m.quizzes)
    return render_template("bank_question_form.html", courses=courses,
                           quizzes=[qz for qz in quizzes
                                    if qz.title != "__question_bank__"])


@manage_bp.route("/question/<int:question_id>/toggle", methods=["POST"])
@content_manager_required
def bank_question_toggle(question_id):
    q = Question.query.get_or_404(question_id)
    _course_or_403(q.quiz.module.course_id)
    q.is_active = not q.is_active
    db.session.commit()
    flash(f"Question {'activated' if q.is_active else 'deactivated'}.", "info")
    return redirect(request.referrer or url_for("manage.question_bank"))


@manage_bp.route("/quiz/<int:quiz_id>/from-bank", methods=["GET", "POST"])
@content_manager_required
def quiz_from_bank(quiz_id):
    """Build a quiz from the bank: manual pick or auto-generate (§5.2)."""
    import random as _random
    quiz = Quiz.query.get_or_404(quiz_id)
    course = _course_or_403(quiz.module.course_id)
    bank_q = (Question.query.join(Quiz, Question.quiz_id == Quiz.id)
              .join(Module, Quiz.module_id == Module.id)
              .filter(Module.course_id == course.id,
                      Question.is_active.is_(True))
              .order_by(Question.id.desc()).limit(500).all())
    # hide questions already on this quiz
    on_quiz = {q.id for q in quiz.questions}
    bank_q = [q for q in bank_q if q.id not in on_quiz]
    if request.method == "POST":
        mode = request.form.get("mode", "manual")
        picked = []
        if mode == "auto":
            n = max(1, min(50, int(request.form.get("count", 10) or 10)))
            diff = request.form.get("difficulty", "")
            topic = request.form.get("topic", "").strip()
            pool = bank_q
            if diff:
                pool = [q for q in pool if q.difficulty == diff]
            if topic:
                like = topic.lower()
                pool = [q for q in pool
                        if like in (q.topic or "").lower()
                        or like in (q.skills or "").lower()]
            picked = _random.sample(pool, min(n, len(pool)))
            if not picked:
                flash("No bank questions match those filters.", "warning")
                return redirect(url_for("manage.quiz_from_bank", quiz_id=quiz.id))
        else:
            ids = {int(i) for i in request.form.getlist("qid") if i.isdigit()}
            picked = [q for q in bank_q if q.id in ids]
        pos = (db.session.query(db.func.max(Question.position))
               .filter_by(quiz_id=quiz.id).scalar() or 0)
        for src in picked:
            pos += 1
            db.session.add(Question(
                quiz_id=quiz.id, position=pos, text=src.text,
                option_a=src.option_a, option_b=src.option_b,
                option_c=src.option_c, option_d=src.option_d,
                correct=src.correct, lesson_id=src.lesson_id,
                qtype=src.qtype, difficulty=src.difficulty, topic=src.topic,
                skills=src.skills, marks=src.marks, is_active=True,
                answer_data=src.answer_data))
        db.session.commit()
        flash(f"Added {len(picked)} question(s) to '{quiz.title}'.", "success")
        return redirect(url_for("manage.quiz_questions", quiz_id=quiz.id))
    return render_template("quiz_from_bank.html", course=course, quiz=quiz,
                           bank=bank_q)


# --------------------------------------- Phase 6: exam analytics (§5.4)
@manage_bp.route("/quiz/<int:quiz_id>/analytics")
@content_manager_required
def quiz_analytics(quiz_id):
    """Faculty analytics: attempts, avg/best/latest, pass rate, per-question."""
    quiz = Quiz.query.get_or_404(quiz_id)
    _course_or_403(quiz.module.course_id)
    attempts = [a for a in quiz.attempts if a.is_submitted]
    scores = [(a.percent or 0.0) for a in attempts]
    passed = sum(1 for a in attempts
                 if (a.percent or 0.0) >= quiz.pass_percent)
    # per-question performance: avg fraction of marks
    qstats = []
    for q in quiz.questions:
        answers = QuizAnswer.query.filter_by(question_id=q.id).all()
        graded = [a for a in answers if not a.needs_review]
        fracs = [(a.marks_awarded or 0.0) / (q.marks or 1.0) for a in graded]
        qstats.append({
            "q": q, "n": len(graded),
            "avg": round(sum(fracs) / len(fracs) * 100, 1) if fracs else None})
    return render_template("manage_quiz_analytics.html", quiz=quiz,
                           attempts=attempts,
                           n=len(attempts),
                           avg=round(sum(scores) / len(scores), 1) if scores else None,
                           best=max(scores) if scores else None,
                           latest=(attempts[-1].percent if attempts else None),
                           pass_rate=(round(passed / len(attempts) * 100, 1)
                                      if attempts else None),
                           pending=QuizAnswer.query.join(
                               QuizAttempt, QuizAnswer.attempt_id == QuizAttempt.id)
                               .filter(QuizAttempt.quiz_id == quiz.id,
                                       QuizAnswer.needs_review.is_(True)).count(),
                           expired=sum(1 for a in attempts if a.time_expired),
                           qstats=qstats)
@manage_bp.route("/grading")
@content_manager_required
def grading_queue():
    """Faculty queue: attempts with descriptive answers awaiting review."""
    courses = [c for c in Course.query.all() if current_user.can_manage_course(c)]
    course_ids = [c.id for c in courses]
    pending = (QuizAnswer.query.join(QuizAttempt,
                                    QuizAnswer.attempt_id == QuizAttempt.id)
               .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
               .join(Module, Quiz.module_id == Module.id)
               .filter(Module.course_id.in_(course_ids),
                       QuizAnswer.needs_review.is_(True))
               .order_by(QuizAnswer.id.asc()).all()) if course_ids else []
    return render_template("manage_grading.html", pending=pending)


@manage_bp.route("/grading/<int:answer_id>", methods=["POST"])
@content_manager_required
def grade_answer(answer_id):
    """Faculty grades one descriptive answer: marks + feedback."""
    from .routes_student import check_and_issue_certificate
    ans = QuizAnswer.query.get_or_404(answer_id)
    _course_or_403(ans.question.quiz.module.course_id)
    try:
        marks = float(request.form.get("marks", 0) or 0)
    except ValueError:
        flash("Marks must be a number.", "danger")
        return redirect(url_for("manage.grading_queue"))
    marks = max(0.0, min(ans.question.marks or 0.0, marks))
    ans.marks_awarded = round(marks, 2)
    ans.is_correct = marks >= (ans.question.marks or 0.0)
    ans.feedback = request.form.get("feedback", "").strip()[:2000]
    ans.needs_review = False
    ans.reviewed_by = current_user.id
    ans.reviewed_at = datetime.utcnow()
    attempt = ans.attempt
    # recompute attempt score from all answers
    attempt.score = round(max(0.0, sum(
        (a.marks_awarded or 0.0) for a in attempt.answers)), 2)
    if not any(a.needs_review for a in attempt.answers):
        attempt.pending_review = False
        cert = check_and_issue_certificate(attempt.user_id,
                                           attempt.quiz.module.course_id)
        if cert:
            flash("All answers graded — certificate issued.", "success")
    db.session.commit()
    flash("Answer graded.", "success")
    return redirect(url_for("manage.grading_queue"))


# ------------------------------------------------- Phase 6: projects (§5.5)
@manage_bp.route("/projects")
@content_manager_required
def manage_projects():
    courses = [c for c in Course.query.order_by(Course.title).all()
               if current_user.can_manage_course(c)]
    course_id = request.args.get("course_id", "")
    q = Project.query
    if course_id.isdigit():
        q = q.filter_by(course_id=int(course_id))
    elif courses:
        q = q.filter(Project.course_id.in_([c.id for c in courses]))
    items = q.order_by(Project.created_at.desc()).all()
    return render_template("manage_projects.html", projects=items,
                           courses=courses, f=request.args)


@manage_bp.route("/projects/new", methods=["GET", "POST"])
@content_manager_required
def project_new():
    courses = [c for c in Course.query.order_by(Course.title).all()
               if current_user.can_manage_course(c)]
    if not courses:
        abort(403)
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        title = request.form.get("title", "").strip()
        if not course_id or not title:
            flash("Course and title are required.", "danger")
        else:
            _course_or_403(course_id)
            deadline = None
            if request.form.get("deadline"):
                try:
                    deadline = datetime.strptime(
                        request.form.get("deadline"), "%Y-%m-%d").date()
                except ValueError:
                    pass
            db.session.add(Project(
                course_id=course_id, title=title,
                description=request.form.get("description", "").strip(),
                skills=request.form.get("skills", "").strip()[:200],
                deadline=deadline,
                max_marks=max(1, int(request.form.get("max_marks", 100) or 100)),
                created_by=current_user.id))
            db.session.commit()
            flash("Project brief published.", "success")
            return redirect(url_for("manage.manage_projects"))
    return render_template("manage_project_form.html", courses=courses,
                           project=None)


@manage_bp.route("/projects/<int:project_id>/submissions")
@content_manager_required
def project_submissions(project_id):
    project = Project.query.get_or_404(project_id)
    _course_or_403(project.course_id)
    subs = (ProjectSubmission.query.filter_by(project_id=project.id)
            .order_by(ProjectSubmission.submitted_at.desc()).all())
    return render_template("manage_project_submissions.html", project=project,
                           subs=subs)


@manage_bp.route("/projects/submission/<int:sub_id>/evaluate", methods=["POST"])
@content_manager_required
def project_evaluate(sub_id):
    sub = ProjectSubmission.query.get_or_404(sub_id)
    _course_or_403(sub.project.course_id)
    try:
        marks = float(request.form.get("marks", 0) or 0)
    except ValueError:
        flash("Marks must be a number.", "danger")
        return redirect(url_for("manage.project_submissions",
                                project_id=sub.project_id))
    marks = max(0.0, min(sub.project.max_marks, marks))
    sub.marks = round(marks, 2)
    sub.feedback = request.form.get("feedback", "").strip()[:2000]
    sub.status = "evaluated"
    sub.evaluated_at = datetime.utcnow()
    sub.evaluated_by = current_user.id
    db.session.commit()
    flash("Project evaluated.", "success")
    return redirect(url_for("manage.project_submissions",
                            project_id=sub.project_id))


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
        try:
            from .whatsapp import send_graded_whatsapp
            send_graded_whatsapp(sub)
        except Exception:
            pass  # WhatsApp must never break grading
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
