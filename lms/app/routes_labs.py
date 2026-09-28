"""Phase 12 §21.4 — coding labs routes (sandboxed Python in the browser)."""
from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for, flash)
from flask_login import current_user, login_required

from . import db
from . import labs as LAB
from . import operations as OPS
from .decorators import content_manager_required, role_required
from .models import LabAttempt, LabExercise, Lesson

labs_bp = Blueprint("labs", __name__)
student_only = role_required("student")


def _exercise_or_404(exercise_id, published_only=True):
    q = LabExercise.query.filter_by(id=exercise_id)
    if published_only:
        q = q.filter_by(is_published=True)
    return q.first_or_404()


# ------------------------------------------------------------ student UI


def ensure_lab_examples():
    """Idempotent seed: one published example coding lab attached to the
    first lesson of the Python Programming course (if seeded)."""
    try:
        from .models import Course, LabExercise
        if LabExercise.query.filter_by(
                title="Hello, Python! Your first program").first():
            return
        course = Course.query.filter_by(slug="python-programming").first()
        if not course:
            return
        lesson = None
        for m in course.modules:
            if m.lessons:
                lesson = m.lessons[0]
                break
        if not lesson:
            return
        db.session.add(LabExercise(
            lesson_id=lesson.id,
            title="Hello, Python! Your first program",
            instructions=("<p>Write a Python program that prints exactly:</p>"
                          "<pre>Hello, Sayyed EdVantage!</pre>"
                          "<p>Press <b>Run</b> to test, then <b>Check answer</b>.</p>"),
            starter_code='print("Hello, Sayyed EdVantage!")\n',
            expected_output="Hello, Sayyed EdVantage!",
            is_published=True,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

@labs_bp.route("/labs")
@login_required
def lab_list():
    exercises = (LabExercise.query.filter_by(is_published=True)
                 .order_by(LabExercise.created_at.desc()).all())
    return render_template("labs_list.html", exercises=exercises)


@labs_bp.route("/labs/<int:exercise_id>")
@login_required
def lab_detail(exercise_id):
    exercise = _exercise_or_404(exercise_id)
    attempts = (LabAttempt.query
                .filter_by(exercise_id=exercise.id, user_id=current_user.id)
                .order_by(LabAttempt.created_at.desc()).limit(10).all())
    return render_template("lab_detail.html", exercise=exercise,
                           attempts=attempts)


@labs_bp.route("/labs/<int:exercise_id>/run", methods=["POST"])
@login_required
def lab_run(exercise_id):
    _exercise_or_404(exercise_id)
    code = request.form.get("code", "") or (request.get_json(silent=True) or {}).get("code", "")
    ok, output, error = LAB.run_python_code(code)
    return jsonify({"ok": ok, "output": output, "error": error})


@labs_bp.route("/labs/<int:exercise_id>/check", methods=["POST"])
@login_required
def lab_check(exercise_id):
    exercise = _exercise_or_404(exercise_id)
    code = request.form.get("code", "") or (request.get_json(silent=True) or {}).get("code", "")
    ok, output, error = LAB.run_python_code(code)
    passed = ok and LAB.check_output(output, exercise.expected_output)
    db.session.add(LabAttempt(exercise_id=exercise.id, user_id=current_user.id,
                              code=code[:50_000], output=output[:20_000],
                              passed=passed))
    db.session.commit()
    return jsonify({"ok": ok, "output": output, "error": error,
                    "passed": passed})


# ------------------------------------------------------------ faculty authoring

@labs_bp.route("/manage/labs")
@content_manager_required
def manage_list():
    exercises = (LabExercise.query
                 .order_by(LabExercise.created_at.desc()).all())
    return render_template("lab_manage_list.html", exercises=exercises)


@labs_bp.route("/manage/labs/new", methods=["GET", "POST"])
@content_manager_required
def manage_new():
    lessons = Lesson.query.order_by(Lesson.id).all()
    if request.method == "POST":
        lesson_id = request.form.get("lesson_id", type=int)
        title = request.form.get("title", "").strip()
        if not lesson_id or not title:
            flash("Lesson and title are required.", "error")
        else:
            ex = LabExercise(
                lesson_id=lesson_id, title=title,
                instructions=request.form.get("instructions", ""),
                starter_code=request.form.get("starter_code", ""),
                expected_output=request.form.get("expected_output", ""),
                is_published=bool(request.form.get("is_published")),
                created_by=current_user.id)
            db.session.add(ex)
            db.session.commit()
            OPS.audit(current_user, "lab.create", "lab_exercise", ex.id,
                      title, request.remote_addr or "")
            flash("Lab exercise created.", "ok")
            return redirect(url_for("labs.manage_list"))
    return render_template("lab_form.html", lessons=lessons, exercise=None)


@labs_bp.route("/manage/labs/<int:exercise_id>/edit", methods=["GET", "POST"])
@content_manager_required
def manage_edit(exercise_id):
    exercise = LabExercise.query.get_or_404(exercise_id)
    lessons = Lesson.query.order_by(Lesson.id).all()
    if request.method == "POST":
        exercise.lesson_id = request.form.get("lesson_id", type=int) or exercise.lesson_id
        exercise.title = request.form.get("title", "").strip() or exercise.title
        exercise.instructions = request.form.get("instructions", "")
        exercise.starter_code = request.form.get("starter_code", "")
        exercise.expected_output = request.form.get("expected_output", "")
        exercise.is_published = bool(request.form.get("is_published"))
        db.session.commit()
        OPS.audit(current_user, "lab.update", "lab_exercise", exercise.id,
                  exercise.title, request.remote_addr or "")
        flash("Lab exercise updated.", "ok")
        return redirect(url_for("labs.manage_list"))
    return render_template("lab_form.html", lessons=lessons, exercise=exercise)


@labs_bp.route("/manage/labs/<int:exercise_id>/delete", methods=["POST"])
@content_manager_required
def manage_delete(exercise_id):
    exercise = LabExercise.query.get_or_404(exercise_id)
    db.session.delete(exercise)
    db.session.commit()
    OPS.audit(current_user, "lab.delete", "lab_exercise", exercise_id, "",
              request.remote_addr or "")
    flash("Lab exercise deleted.", "ok")
    return redirect(url_for("labs.manage_list"))
