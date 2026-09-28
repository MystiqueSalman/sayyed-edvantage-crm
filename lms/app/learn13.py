"""Phase 13 Stream 2 (Learning extras) — one Blueprint: learn13_bp.

Contents:
  * Private lesson notes      /notes, /notes/lesson/<id>
  * SQL lab                   /labs/sql...
  * Data-Science notebook lab /labs/datascience...
  * Course versioning         /manage/courses/<id>/versions...
  * Signed video URLs         /v/<token>, /v/<token>/stream
  * Per-lesson video policy editor (faculty/admin)

All paths are explicit on the blueprint (no url_prefix). Everything here
is additive: no existing route, model, or template behaviour is changed.
"""
import os
import re
import sqlite3
import time
from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from . import db
from .decorators import role_required
from .labs import run_python_code
from .models import (AppSetting, Course, Enrollment, Lesson, Module, User)
from .models13_learning import (CourseVersion13, DsExercise13, DsProgress13,
                                EnrollmentVersion13, LessonNote13,
                                SqlAttempt13, SqlExercise13, VideoPolicy13,
                                version_for_enrollment)
from .video13 import (default_expiry_hours, download_allowed,
                      expiry_hours_for_lesson, mint_video_token,
                      signed_video_url, verify_video_token)

learn13_bp = Blueprint("learn13", __name__)
student_only = role_required("student")

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "static", "datasets")


# ---------------------------------------------------------------------------
# helpers


def _enrolled_or_403(course_id):
    """Student-side access check (mirrors student._active_enrollment_or_403)."""
    enr = (Enrollment.query
           .filter(Enrollment.user_id == current_user.id,
                   Enrollment.course_id == course_id,
                   Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                                         Enrollment.STATUS_COMPLETED]))
           .first())
    if not enr:
        abort(403)
    return enr


def _manage_course_or_403(course_id):
    course = Course.query.get_or_404(course_id)
    if not current_user.can_manage_course(course):
        abort(403)
    return course


# ---------------------------------------------------------------------------
# 1. Private lesson notes


@learn13_bp.route("/notes")
@student_only
def notes_list():
    """All of the student's notes, grouped by course."""
    notes = (LessonNote13.query
             .filter_by(user_id=current_user.id)
             .order_by(LessonNote13.updated_at.desc()).all())
    lesson_ids = [n.lesson_id for n in notes]
    lessons = {l.id: l for l in
               Lesson.query.filter(Lesson.id.in_(lesson_ids)).all()} if lesson_ids else {}
    grouped = []  # [(course, [(note, lesson), ...])]
    by_course = {}
    for n in notes:
        lesson = lessons.get(n.lesson_id)
        if not lesson:
            continue
        course = lesson.module.course
        by_course.setdefault(course.id, (course, []))[1].append((n, lesson))
    grouped = sorted(by_course.values(), key=lambda g: g[0].title)
    return render_template("p13_notes_list.html", grouped=grouped)


@learn13_bp.route("/notes/lesson/<int:lesson_id>", methods=["GET", "POST"])
@student_only
def lesson_note(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    _enrolled_or_403(lesson.module.course_id)
    note = (LessonNote13.query
            .filter_by(user_id=current_user.id, lesson_id=lesson.id).first())
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()[:160]
        body = (request.form.get("body") or "")
        if note:
            note.title = title
            note.body = body
        else:
            note = LessonNote13(user_id=current_user.id, lesson_id=lesson.id,
                                title=title, body=body)
            db.session.add(note)
        db.session.commit()
        flash("📝 Note saved.", "success")
        return redirect(url_for("learn13.notes_list"))
    course = lesson.module.course
    return render_template("p13_note_form.html", lesson=lesson, course=course,
                           note=note)


@learn13_bp.route("/notes/lesson/<int:lesson_id>/delete", methods=["POST"])
@student_only
def lesson_note_delete(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    _enrolled_or_403(lesson.module.course_id)
    note = (LessonNote13.query
            .filter_by(user_id=current_user.id, lesson_id=lesson.id).first())
    if note:
        db.session.delete(note)
        db.session.commit()
        flash("Note deleted.", "info")
    return redirect(url_for("learn13.notes_list"))


# ---------------------------------------------------------------------------
# 2. SQL lab — in-browser SQLite practice (read-only)


_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|REPLACE|ATTACH|DETACH|"
    r"VACUUM|PRAGMA|REINDEX|LOAD_EXTENSION|SAVEPOINT|TRANSACTION)\b",
    re.IGNORECASE)
_SQL_TIMEOUT_S = 5
_MAX_ROWS = 1000


def strip_sql_comments(sql):
    """Remove /* */ and -- comments, respecting quoted strings."""
    out, i, n = [], 0, len(sql)
    quote = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                # '' inside a '...' string is an escaped quote
                if i + 1 < n and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 1
                else:
                    quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
        elif ch == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def validate_readonly_query(sql):
    """Return (ok, error). Only SELECT/WITH reads; no ATTACH/LOAD etc."""
    cleaned = strip_sql_comments(sql or "").strip().rstrip(";").strip()
    if not cleaned:
        return False, "Query is empty."
    if not re.match(r"(?i)^(SELECT|WITH)\b", cleaned):
        return False, "Only read-only SELECT (or WITH … SELECT) queries are allowed."
    if _WRITE_WORDS.search(cleaned):
        return False, "Write/DDL statements are not allowed in the SQL lab."
    return True, ""


def _canon_value(v):
    if isinstance(v, float):
        return round(v, 6)
    return v


def _fetch_all(conn, sql, timeout_s=_SQL_TIMEOUT_S):
    """Run one SELECT with a hard time budget. Returns (cols, rows)."""
    deadline = time.time() + timeout_s

    def _progress():
        return 1 if time.time() > deadline else 0

    conn.set_progress_handler(_progress, 1000)
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in (cur.description or [])]
        rows = cur.fetchmany(_MAX_ROWS + 1)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise TimeoutError(
                f"Query exceeded the {_SQL_TIMEOUT_S}s time limit.")
        raise
    finally:
        conn.set_progress_handler(None, 0)
    truncated = len(rows) > _MAX_ROWS
    return cols, rows[:_MAX_ROWS], truncated


def _result_signature(cols, rows):
    """Order-insensitive signature: sorted col names + multiset of rows."""
    col_key = tuple(sorted(c.lower() for c in cols))
    row_key = []
    for row in rows:
        pairs = sorted(((c.lower(), _canon_value(v))
                        for c, v in zip(cols, row)),
                       key=lambda p: p[0])
        row_key.append(tuple(pairs))
    from collections import Counter
    return col_key, Counter(row_key)


def run_sql_attempt(exercise, user_sql):
    """Execute a student query against a fresh in-memory DB.

    Returns dict(passed=..., columns=..., rows=..., error=...).
    """
    ok, err = validate_readonly_query(user_sql)
    if not ok:
        return {"passed": False, "columns": [], "rows": [],
                "error": err}
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(exercise.setup_sql or "")
        exp_cols, exp_rows, _ = _fetch_all(conn, exercise.expected_sql)
        try:
            act_cols, act_rows, truncated = _fetch_all(conn, user_sql)
        except TimeoutError as exc:
            return {"passed": False, "columns": [], "rows": [],
                    "error": str(exc)}
        except Exception as exc:
            return {"passed": False, "columns": [], "rows": [],
                    "error": f"Query failed: {exc}"}
        passed = _result_signature(exp_cols, exp_rows) == \
            _result_signature(act_cols, act_rows)
        error = ""
        if not passed:
            error = ("Result does not match the expected answer yet — "
                     "check the rows and column names.")
            if truncated:
                error += " (showing first 1000 rows)"
        return {"passed": passed,
                "columns": act_cols,
                "rows": [[_canon_value(v) for v in r] for r in act_rows],
                "error": error}
    finally:
        conn.close()


@learn13_bp.route("/labs/sql")
@student_only
def sql_list():
    exercises = (SqlExercise13.query.filter_by(active=True)
                 .order_by(SqlExercise13.id).all())
    return render_template("p13_sql_list.html", exercises=exercises)


@learn13_bp.route("/labs/sql/<int:exercise_id>")
@student_only
def sql_detail(exercise_id):
    ex = SqlExercise13.query.get_or_404(exercise_id)
    if not ex.active:
        abort(404)
    attempts = (SqlAttempt13.query
                .filter_by(user_id=current_user.id, exercise_id=ex.id)
                .order_by(SqlAttempt13.id.desc()).limit(10).all())
    return render_template("p13_sql_detail.html", ex=ex, attempts=attempts)


@learn13_bp.route("/labs/sql/<int:exercise_id>/run", methods=["POST"])
@student_only
def sql_run(exercise_id):
    ex = SqlExercise13.query.get_or_404(exercise_id)
    if not ex.active:
        abort(404)
    query = request.form.get("query") or (request.get_json(silent=True) or {}).get("query", "")
    result = run_sql_attempt(ex, query)
    db.session.add(SqlAttempt13(user_id=current_user.id, exercise_id=ex.id,
                                sql_query=(query or "")[:4000],
                                passed=result["passed"]))
    db.session.commit()
    return jsonify({"ok": True, **result})


# ---------------------------------------------------------------------------
# 3. Data-Science notebook lab (guided, step-based; stdlib-only sandbox)


_DATASET_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.csv$")


def _dataset_text(name):
    """Read a bundled CSV. Names are strictly validated (no path escape)."""
    if not _DATASET_NAME_RE.match(name or ""):
        raise ValueError(f"Unknown dataset: {name!r}")
    path = os.path.join(DATASET_DIR, name)
    if not os.path.isfile(path):
        raise ValueError(f"Unknown dataset: {name!r}")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def run_ds_step(exercise, step_idx, student_code):
    """Run one DS step: student code, then authored validation_code.

    Both run through the Phase 12 sandbox (run_python_code). The dataset
    (if any) is injected as DATASET_CSV text — students parse it with
    ``csv.reader(DATASET_CSV.splitlines())`` since the sandbox has no
    file access. Returns dict(passed=..., output=..., error=...).
    """
    steps = exercise.steps or []
    if not (0 <= step_idx < len(steps)):
        return {"passed": False, "output": "", "error": "Unknown step."}
    step = steps[step_idx]
    prelude = "import csv\nimport statistics\n"
    dataset = step.get("dataset")
    if dataset:
        try:
            csv_text = _dataset_text(dataset)
        except ValueError as exc:
            return {"passed": False, "output": "", "error": str(exc)}
        prelude += (f"DATASET_CSV = {csv_text!r}\n"
                    f"DATASET_NAME = {dataset!r}\n")
    student_code = student_code or ""
    validation = step.get("validation_code") or ""
    harness = (prelude + student_code +
               "\n# ---- step validation (authored) ----\n" + validation + "\n")
    ok, out, err = run_python_code(harness)
    if ok:
        return {"passed": True, "output": out, "error": ""}
    # Distinguish "student code crashed" from "validation failed".
    ok2, out2, err2 = run_python_code(prelude + student_code)
    if not ok2:
        return {"passed": False, "output": out2,
                "error": f"Your code raised an error: {err2}"}
    return {"passed": False, "output": out,
            "error": f"Not quite — the step check failed: {err}"}


@learn13_bp.route("/labs/datascience")
@student_only
def ds_list():
    exercises = (DsExercise13.query.filter_by(active=True)
                 .order_by(DsExercise13.sort_order, DsExercise13.id).all())
    return render_template("p13_ds_list.html", exercises=exercises)


@learn13_bp.route("/labs/datascience/<int:exercise_id>")
@student_only
def ds_detail(exercise_id):
    ex = DsExercise13.query.get_or_404(exercise_id)
    if not ex.active:
        abort(404)
    progress = {(p.step_idx): p for p in
                DsProgress13.query.filter_by(
                    user_id=current_user.id, exercise_id=ex.id).all()}
    steps = ex.steps or []
    return render_template("p13_ds_detail.html", ex=ex, steps=steps,
                           progress=progress)


@learn13_bp.route("/labs/datascience/<int:exercise_id>/step/<int:step_idx>/run",
                  methods=["POST"])
@student_only
def ds_step_run(exercise_id, step_idx):
    ex = DsExercise13.query.get_or_404(exercise_id)
    if not ex.active:
        abort(404)
    payload = request.get_json(silent=True) or {}
    code = request.form.get("code") or payload.get("code", "")
    result = run_ds_step(ex, step_idx, code)
    prog = (DsProgress13.query
            .filter_by(user_id=current_user.id, exercise_id=ex.id,
                       step_idx=step_idx).first())
    if prog:
        prog.passed = result["passed"]
        prog.output = (result["output"] or "")[:2000]
    else:
        db.session.add(DsProgress13(
            user_id=current_user.id, exercise_id=ex.id, step_idx=step_idx,
            passed=result["passed"], output=(result["output"] or "")[:2000]))
    db.session.commit()
    return jsonify({"ok": True, **result})


# ---------------------------------------------------------------------------
# 4. Course versioning


def build_course_snapshot(course):
    return {"modules": [
        {"title": m.title,
         "lessons": [{"title": l.title, "kind": l.kind} for l in m.lessons]}
        for m in course.modules]}


def diff_snapshots(old, new):
    """Summarise structural changes between two snapshots."""
    old = old or {"modules": []}
    new = new or {"modules": []}
    old_mods = {m.get("title"): m for m in old.get("modules", [])}
    new_mods = {m.get("title"): m for m in new.get("modules", [])}
    added_modules = [t for t in new_mods if t not in old_mods]
    removed_modules = [t for t in old_mods if t not in new_mods]
    added_lessons, removed_lessons, changed_lessons = [], [], []
    for title in old_mods:
        if title not in new_mods:
            continue
        old_ls = {l.get("title"): l for l in old_mods[title].get("lessons", [])}
        new_ls = {l.get("title"): l for l in new_mods[title].get("lessons", [])}
        for lt in new_ls:
            if lt not in old_ls:
                added_lessons.append(f"{title} / {lt}")
            elif old_ls[lt].get("kind") != new_ls[lt].get("kind"):
                changed_lessons.append(
                    f"{title} / {lt} "
                    f"({old_ls[lt].get('kind')} → {new_ls[lt].get('kind')})")
        for lt in old_ls:
            if lt not in new_ls:
                removed_lessons.append(f"{title} / {lt}")
    return {"added_modules": added_modules,
            "removed_modules": removed_modules,
            "added_lessons": added_lessons,
            "removed_lessons": removed_lessons,
            "changed_lessons": changed_lessons}


@learn13_bp.route("/manage/courses/<int:course_id>/versions/publish",
                  methods=["POST"])
@login_required
def course_version_publish(course_id):
    course = _manage_course_or_403(course_id)
    last_no = (db.session.query(db.func.max(CourseVersion13.version_no))
               .filter_by(course_id=course.id).scalar() or 0)
    version = CourseVersion13(
        course_id=course.id,
        version_no=last_no + 1,
        snapshot=build_course_snapshot(course),
        note=(request.form.get("note") or "").strip()[:300],
        created_by=current_user.id,
    )
    db.session.add(version)
    db.session.commit()
    flash(f"📌 Version {version.version_no} published.", "success")
    return redirect(url_for("learn13.course_versions", course_id=course.id))


@learn13_bp.route("/manage/courses/<int:course_id>/versions")
@login_required
def course_versions(course_id):
    course = _manage_course_or_403(course_id)
    versions = (CourseVersion13.query.filter_by(course_id=course.id)
                .order_by(CourseVersion13.version_no.desc()).all())
    view_id = request.args.get("view", type=int)
    view_version, diff = None, None
    if view_id:
        view_version = CourseVersion13.query.filter_by(
            id=view_id, course_id=course.id).first_or_404()
        prev = (CourseVersion13.query
                .filter(CourseVersion13.course_id == course.id,
                        CourseVersion13.version_no < view_version.version_no)
                .order_by(CourseVersion13.version_no.desc()).first())
        diff = diff_snapshots(prev.snapshot if prev else None,
                              view_version.snapshot)
    return render_template("p13_versions.html", course=course,
                           versions=versions, view_version=view_version,
                           diff=diff)


# ---------------------------------------------------------------------------
# 5. Video security: signed URLs + per-lesson policy


def _lesson_for_token(token):
    """Validate token, load lesson, return (lesson, user_id, error)."""
    coords, err = verify_video_token(token)
    if err:
        return None, None, err
    lesson_id, user_id, _exp = coords
    lesson = Lesson.query.get(lesson_id)
    if not lesson or lesson.kind != Lesson.KIND_VIDEO or not lesson.video_url:
        return None, None, "video not found"
    return lesson, user_id, None


def _may_watch_video(lesson, token_user_id):
    """Logged-in user must own the token and may access the lesson."""
    if not current_user.is_authenticated:
        return False
    if current_user.id != token_user_id:
        return False
    course = lesson.module.course
    if current_user.can_manage_content():
        return True
    enr = (Enrollment.query
           .filter(Enrollment.user_id == current_user.id,
                   Enrollment.course_id == course.id,
                   Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                                         Enrollment.STATUS_COMPLETED]))
           .first())
    return enr is not None


@learn13_bp.route("/v/<token>")
@login_required
def video_watch(token):
    lesson, token_user_id, err = _lesson_for_token(token)
    if err or not _may_watch_video(lesson, token_user_id):
        abort(403)
    stream_url = url_for("learn13.video_stream", token=token)
    return render_template("p13_video_watch.html", lesson=lesson,
                           course=lesson.module.course,
                           stream_url=stream_url,
                           allow_download=download_allowed(lesson.id),
                           token=token)


@learn13_bp.route("/v/<token>/stream")
@login_required
def video_stream(token):
    lesson, token_user_id, err = _lesson_for_token(token)
    if err or not _may_watch_video(lesson, token_user_id):
        abort(403)
    # 302 to the stored URL — the raw URL never appears in page source.
    return redirect(lesson.video_url)


@learn13_bp.route("/manage/lessons/<int:lesson_id>/video-policy",
                  methods=["GET", "POST"])
@login_required
def video_policy_edit(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    _manage_course_or_403(lesson.module.course_id)
    policy = VideoPolicy13.query.filter_by(lesson_id=lesson.id).first()
    if request.method == "POST":
        allow_download = request.form.get("allow_download") == "on"
        try:
            expiry = max(1, min(72, int(request.form.get(
                "token_expiry_hours") or 2)))
        except ValueError:
            expiry = 2
        if policy:
            policy.allow_download = allow_download
            policy.token_expiry_hours = expiry
        else:
            db.session.add(VideoPolicy13(
                lesson_id=lesson.id, allow_download=allow_download,
                token_expiry_hours=expiry))
        db.session.commit()
        flash("🎬 Video policy saved.", "success")
        return redirect(url_for("manage.lesson_edit", lesson_id=lesson.id))
    return render_template("p13_video_policy.html", lesson=lesson,
                           course=lesson.module.course, policy=policy,
                           default_expiry=default_expiry_hours())


# ---------------------------------------------------------------------------
# template helpers (app-wide): signed video URL for the lesson page


def _p13_signed_url(lesson):
    """Signed watch URL for a video lesson, or '' (falls back to raw URL)."""
    try:
        if not current_user.is_authenticated:
            return ""
        if (not lesson or getattr(lesson, "kind", "") != "video"
                or not getattr(lesson, "video_url", "")):
            return ""
        return signed_video_url(lesson.id, current_user.id)
    except Exception:
        return ""


@learn13_bp.app_context_processor
def _p13_template_helpers():
    return {"p13_signed_url": _p13_signed_url,
            "p13_video_download_allowed": download_allowed,
            "p13_enabled": True}


# ---------------------------------------------------------------------------
# idempotent seed (called by the coordinator from create_app, next to the
# Phase 12 ensure_lab_examples hook)


def _sql_seed_exercises():
    return [
        {
            "title": "High scorers",
            "description": ("<p>Find every student who scored <b>85 or more</b>. "
                            "Return the <span class='code-pill'>name</span> and "
                            "<span class='code-pill'>score</span> columns.</p>"),
            "setup_sql": (
                "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, score INTEGER);\n"
                "INSERT INTO students (name, score) VALUES\n"
                "('Aarav', 92), ('Diya', 88), ('Arjun', 76),\n"
                "('Ananya', 95), ('Vikram', 81), ('Rohan', 72);"),
            "expected_sql": "SELECT name, score FROM students WHERE score >= 85;",
            "hint": "Use WHERE to filter rows: WHERE score >= 85.",
        },
        {
            "title": "Average score by subject",
            "description": ("<p>Compute the average score for each subject. "
                            "Name the average column "
                            "<span class='code-pill'>avg_score</span>.</p>"),
            "setup_sql": (
                "CREATE TABLE results (student TEXT, subject TEXT, score INTEGER);\n"
                "INSERT INTO results VALUES\n"
                "('Aarav','Maths',92),('Diya','Science',88),('Arjun','Maths',76),\n"
                "('Ananya','English',95),('Vikram','Science',81),('Sneha','Maths',89);"),
            "expected_sql": "SELECT subject, AVG(score) AS avg_score FROM results GROUP BY subject;",
            "hint": "GROUP BY subject and aggregate with AVG(score) AS avg_score.",
        },
        {
            "title": "Above-average students",
            "description": ("<p>List the <span class='code-pill'>name</span> of every "
                            "student whose score is above the overall average. "
                            "Use a subquery to compute the average.</p>"),
            "setup_sql": (
                "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, score INTEGER);\n"
                "INSERT INTO students (name, score) VALUES\n"
                "('Aarav', 92), ('Diya', 88), ('Arjun', 76),\n"
                "('Ananya', 95), ('Vikram', 81), ('Rohan', 72);"),
            "expected_sql": "SELECT name FROM students WHERE score > (SELECT AVG(score) FROM students);",
            "hint": "Compare score against a scalar subquery: (SELECT AVG(score) FROM students).",
        },
        {
            "title": "Enrollments with course names",
            "description": ("<p>Show each student's <span class='code-pill'>name</span> "
                            "alongside the <span class='code-pill'>title</span> of the "
                            "course they enrolled in. Join all three tables.</p>"),
            "setup_sql": (
                "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT);\n"
                "CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT);\n"
                "CREATE TABLE enrollments (student_id INTEGER, course_id INTEGER);\n"
                "INSERT INTO students VALUES (1,'Aarav'),(2,'Diya'),(3,'Arjun');\n"
                "INSERT INTO courses VALUES (10,'Data Science'),(20,'Python Programming');\n"
                "INSERT INTO enrollments VALUES (1,10),(2,20),(3,10);"),
            "expected_sql": ("SELECT s.name, c.title FROM students s "
                             "JOIN enrollments e ON e.student_id = s.id "
                             "JOIN courses c ON c.id = e.course_id;"),
            "hint": "JOIN the three tables through the enrollments bridge table.",
        },
        {
            "title": "Big sales months",
            "description": ("<p>Find the <span class='code-pill'>month</span> values whose "
                            "total sales exceed 100000. Aggregate first, then filter "
                            "the groups.</p>"),
            "setup_sql": (
                "CREATE TABLE sales (month TEXT, amount INTEGER);\n"
                "INSERT INTO sales VALUES ('Jan',45000),('Jan',60000),\n"
                "('Feb',30000),('Feb',40000),('Mar',80000),('Mar',90000);"),
            "expected_sql": "SELECT month FROM sales GROUP BY month HAVING SUM(amount) > 100000;",
            "hint": "Filter groups with HAVING, not WHERE.",
        },
    ]


def _ds_seed_exercise():
    return {
        "title": "CSV data analysis with Python's csv module",
        "description": ("<p>A guided mini-project: load two real CSV datasets and "
                        "answer questions with the standard library "
                        "<span class='code-pill'>csv</span> and "
                        "<span class='code-pill'>statistics</span> modules.</p>"
                        "<p>The dataset text is injected as "
                        "<span class='code-pill'>DATASET_CSV</span> — parse it with "
                        "<span class='code-pill'>csv.reader(DATASET_CSV.splitlines())</span>.</p>"),
        "sort_order": 0,
        "steps": [
            {
                "instruction": ("<p><b>Step 1 — average score.</b> "
                                "<span class='code-pill'>DATASET_CSV</span> holds "
                                "<b>student_scores.csv</b> (columns: name, subject, score). "
                                "Compute the mean of the <i>score</i> column as a float "
                                "and store it in a variable named "
                                "<span class='code-pill'>mean_score</span>.</p>"),
                "starter_code": ("rows = list(csv.reader(DATASET_CSV.splitlines()))\n"
                                 "header = rows[0]\n"
                                 "data = rows[1:]\n"
                                 "# TODO: compute the mean of column index 2 -> mean_score\n"
                                 "mean_score = 0.0\n"
                                 "print(mean_score)\n"),
                "validation_code": "assert abs(mean_score - 84.1) < 0.01, f\"mean_score should be ~84.1, got {mean_score}\"\n",
                "dataset": "student_scores.csv",
            },
            {
                "instruction": ("<p><b>Step 2 — class topper.</b> Using the same "
                                "dataset, find the <i>name</i> of the student with the "
                                "highest score and store it in "
                                "<span class='code-pill'>topper</span>.</p>"),
                "starter_code": ("rows = list(csv.reader(DATASET_CSV.splitlines()))\n"
                                 "data = rows[1:]\n"
                                 "# TODO: find the name with the max score -> topper\n"
                                 "topper = \"\"\n"
                                 "print(topper)\n"),
                "validation_code": "assert topper == \"Ananya Iyer\", f\"topper should be 'Ananya Iyer', got {topper!r}\"\n",
                "dataset": "student_scores.csv",
            },
            {
                "instruction": ("<p><b>Step 3 — total revenue.</b> "
                                "<span class='code-pill'>DATASET_CSV</span> now holds "
                                "<b>monthly_sales.csv</b> (columns: month, revenue). "
                                "Compute the total revenue as an int in "
                                "<span class='code-pill'>total_revenue</span>.</p>"),
                "starter_code": ("rows = list(csv.reader(DATASET_CSV.splitlines()))\n"
                                 "data = rows[1:]\n"
                                 "# TODO: sum the revenue column -> total_revenue\n"
                                 "total_revenue = 0\n"
                                 "print(total_revenue)\n"),
                "validation_code": "assert total_revenue == 776000, f\"total_revenue should be 776000, got {total_revenue}\"\n",
                "dataset": "monthly_sales.csv",
            },
            {
                "instruction": ("<p><b>Step 4 — above-average months.</b> Build a list "
                                "named <span class='code-pill'>above_avg_months</span> "
                                "with the month strings whose revenue is strictly "
                                "greater than the average revenue.</p>"),
                "starter_code": ("rows = list(csv.reader(DATASET_CSV.splitlines()))\n"
                                 "data = rows[1:]\n"
                                 "revenues = [int(r[1]) for r in data]\n"
                                 "avg = sum(revenues) / len(revenues)\n"
                                 "# TODO: months with revenue > avg -> above_avg_months\n"
                                 "above_avg_months = []\n"
                                 "print(above_avg_months)\n"),
                "validation_code": ("assert sorted(above_avg_months) == "
                                    "[\"2026-06\", \"2026-07\", \"2026-10\", \"2026-11\", \"2026-12\"], "
                                    "\"unexpected months: \" + str(above_avg_months)\n"),
                "dataset": "monthly_sales.csv",
            },
        ],
    }


def ensure_learning13_defaults():
    """Idempotent seed: SQL exercises, DS exercise, video setting key."""
    try:
        for spec in _sql_seed_exercises():
            if not SqlExercise13.query.filter_by(title=spec["title"]).first():
                db.session.add(SqlExercise13(
                    title=spec["title"], description=spec["description"],
                    setup_sql=spec["setup_sql"],
                    expected_sql=spec["expected_sql"], hint=spec["hint"],
                    active=True))
        ds = _ds_seed_exercise()
        if not DsExercise13.query.filter_by(title=ds["title"]).first():
            db.session.add(DsExercise13(
                title=ds["title"], description=ds["description"],
                steps=ds["steps"], active=True,
                sort_order=ds["sort_order"]))
        if not AppSetting.query.get("p13_video_default_expiry_hours"):
            db.session.add(AppSetting(key="p13_video_default_expiry_hours",
                                      value="2"))
        db.session.commit()
    except Exception:
        db.session.rollback()
