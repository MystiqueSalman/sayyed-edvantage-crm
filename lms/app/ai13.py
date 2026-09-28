"""Phase 13 Stream 3 — AI extras (§13.3): faculty content assistant, AI
project evaluator, at-risk flags, student memory profile.

All AI output here is labeled AI-draft and requires human review.
Additive only: no existing route/template/behavior is touched.

Blueprint registration (for the coordinator — do NOT edit __init__.py here):
    from .ai13 import ai13_bp  # noqa: E402  (Phase 13: AI extras)
    app.register_blueprint(ai13_bp)
"""
import json
import os
import re
from datetime import datetime

import requests
from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from . import db
from .decorators import role_required
from .memory13 import get_memory, refresh_memory
from .memory13 import memory_context_text  # re-export for tutor injection
from .models import (Course, Lesson, Module, Project, ProjectSubmission,
                     User)
from .models13_ai import (AiDraft13, AtRiskFlag13, ProjectEvaluation13,
                          Rubric13)

ai13_bp = Blueprint("ai13", __name__)

AI_UNAVAILABLE_MSG = ("AI unavailable — configure the LLM key "
                      "(set OPENAI_API_KEY and enable AI in Admin → AI settings).")

KINDS = ("lesson-outline", "quiz-draft", "assignment-draft")

# The Quiz model has NO draft/inactive flag (verified 2026-09-28): only
# Question.is_active exists. So quiz drafts cannot be auto-imported as
# inactive quizzes — they are offered as copyable text instead.
QUIZ_IMPORT_NOTE = ("The Quiz model has no draft/inactive flag, so this quiz "
                    "draft cannot be auto-imported as an inactive quiz. "
                    "Copy the text below into the question bank manually — "
                    "nothing was published.")


# ---------------------------------------------------------- LLM helper ----
def llm_available():
    """Reuse the platform's existing LLM gate (app.ai_agent.openai_available):
    OPENAI_API_KEY must be set and AISettings.enabled must be on."""
    try:
        from .ai_agent import openai_available
        return openai_available()
    except Exception:
        return False


def ai_generate(system_text, user_text, max_tokens=900, temperature=0.5):
    """Call the configured OpenAI chat model.

    Returns the reply text, or None when the LLM is unavailable
    (no key / disabled / any API error). Never raises.
    """
    try:
        if not llm_available():
            return None
        from .models import AISettings
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            return None
        model = AISettings.get().model or "gpt-4o-mini"
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "system", "content": system_text},
                               {"role": "user", "content": user_text}],
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip() or None
    except Exception:
        return None


# --------------------------------------------------------------- helpers --
def _faculty_courses():
    if current_user.role in ("admin", "manager"):
        return Course.query.order_by(Course.title).all()
    return (Course.query.filter_by(instructor_id=current_user.id)
            .order_by(Course.title).all())


def _course_context(course):
    """Real modules/lessons for grounded prompts (DO NOT GUESS)."""
    lines = []
    mods = (Module.query.filter_by(course_id=course.id)
            .order_by(Module.position, Module.id).all())
    for m in mods[:12]:
        lessons = (Lesson.query.filter_by(module_id=m.id)
                   .order_by(Lesson.position, Lesson.id).all())
        lt = ", ".join(l.title for l in lessons[:10]) or "(no lessons)"
        lines.append(f"- Module: {m.title} | Lessons: {lt}")
    return "\n".join(lines) or "(this course has no modules/lessons yet)"


def _draft_or_403(draft_id):
    d = db.session.get(AiDraft13, draft_id)
    if not d:
        from flask import abort
        abort(404)
    if (current_user.role == "faculty" and d.faculty_id != current_user.id):
        from flask import abort
        abort(403)
    return d


def _eval_query_for_staff():
    q = ProjectEvaluation13.query.join(
        ProjectSubmission,
        ProjectEvaluation13.project_submission_id == ProjectSubmission.id)
    if current_user.role == "faculty":
        course_ids = [c.id for c in _faculty_courses()]
        q = (q.join(Project, ProjectSubmission.project_id == Project.id)
             .filter(Project.course_id.in_(course_ids)))
    return q.order_by(ProjectEvaluation13.evaluated_at.desc())


def _extract_json(text):
    """Pull the first {...} JSON object out of LLM text. None if invalid."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _parse_criteria(raw):
    """Parse 'Name : weight' lines into [{name, weight}]."""
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, weight = line.partition(":")
        name, weight = name.strip(), weight.strip()
        try:
            w = float(weight)
        except ValueError:
            return None
        if name and w > 0:
            out.append({"name": name[:120], "weight": w})
    return out or None


# ------------------------------------------- 1. content assistant ---------
@ai13_bp.route("/faculty/ai-assistant", methods=["GET", "POST"])
@role_required("faculty", "admin", "manager")
def ai_assistant():
    courses = _faculty_courses()
    course_ids = {c.id for c in courses}
    if request.method == "POST":
        kind = request.form.get("kind", "")
        topic = request.form.get("topic", "").strip()[:200]
        try:
            course_id = int(request.form.get("course_id", 0))
        except ValueError:
            course_id = 0
        course = db.session.get(Course, course_id)
        if kind not in KINDS or not topic or not course or course.id not in course_ids:
            flash("Pick a valid course, kind and topic.", "danger")
            return redirect(url_for("ai13.ai_assistant"))
        ctx = _course_context(course)
        system = ("You are a course-content assistant for Sayyed EdVantage, "
                  "an Indian IT training institute. You help faculty draft "
                  "lesson outlines, quiz questions and assignment briefs.\n"
                  "BINDING RULES — DO NOT GUESS:\n"
                  "- Use ONLY the course modules/lessons below as the factual "
                  "syllabus context. Never invent module or lesson names.\n"
                  "- Never mention fees, discounts, batch dates, placements, "
                  "salaries or guarantees.\n"
                  "- Write clear, simple English suitable for Indian students, "
                  "with headings.")
        if kind == "lesson-outline":
            user_text = (f"Course: {course.title}\nActual course structure:\n"
                         f"{ctx}\n\nDraft a detailed lesson outline for the "
                         f"topic: '{topic}'. Structure: objectives, key "
                         f"concepts (referencing the real lessons above), "
                         f"examples, and a short recap.")
        elif kind == "quiz-draft":
            user_text = (f"Course: {course.title}\nActual course structure:\n"
                         f"{ctx}\n\nDraft 8 multiple-choice questions (4 "
                         f"options A–D each, clearly mark the correct answer) "
                         f"on the topic: '{topic}'. Ground every question in "
                         f"the course structure above.")
        else:
            user_text = (f"Course: {course.title}\nActual course structure:\n"
                         f"{ctx}\n\nDraft a hands-on assignment brief for the "
                         f"topic: '{topic}'. Include: objective, step-by-step "
                         f"tasks, deliverables, and evaluation hints.")
        content = ai_generate(system, user_text)
        if content is None:
            flash(AI_UNAVAILABLE_MSG, "warning")
            return redirect(url_for("ai13.ai_assistant"))
        draft = AiDraft13(faculty_id=current_user.id, course_id=course.id,
                          kind=kind, topic=topic, content=content,
                          status="draft")  # ALWAYS draft — never auto-published
        db.session.add(draft)
        db.session.commit()
        flash("AI draft saved — review before use. Nothing was published.",
              "success")
        return redirect(url_for("ai13.draft_detail", draft_id=draft.id))
    if current_user.role in ("admin", "manager"):
        drafts = (AiDraft13.query
                  .order_by(AiDraft13.created_at.desc()).limit(100).all())
    else:
        drafts = (AiDraft13.query
                  .filter_by(faculty_id=current_user.id)
                  .order_by(AiDraft13.created_at.desc()).limit(100).all())
    return render_template("p13_ai_assistant.html", courses=courses,
                           drafts=drafts, kinds=KINDS)


@ai13_bp.route("/faculty/ai-assistant/draft/<int:draft_id>")
@role_required("faculty", "admin", "manager")
def draft_detail(draft_id):
    d = _draft_or_403(draft_id)
    return render_template("p13_draft_detail.html", draft=d,
                           quiz_import_note=QUIZ_IMPORT_NOTE)


@ai13_bp.route("/faculty/ai-assistant/draft/<int:draft_id>/edit",
               methods=["GET", "POST"])
@role_required("faculty", "admin", "manager")
def draft_edit(draft_id):
    d = _draft_or_403(draft_id)
    if request.method == "POST":
        d.topic = request.form.get("topic", "").strip()[:200] or d.topic
        d.content = request.form.get("content", "")[:20000]
        d.status = "draft"  # edits never change the draft-only rule
        db.session.commit()
        flash("Draft updated (still a draft — nothing published).", "success")
        return redirect(url_for("ai13.draft_detail", draft_id=d.id))
    return render_template("p13_draft_edit.html", draft=d)


@ai13_bp.route("/faculty/ai-assistant/draft/<int:draft_id>/delete",
               methods=["POST"])
@role_required("faculty", "admin", "manager")
def draft_delete(draft_id):
    d = _draft_or_403(draft_id)
    db.session.delete(d)
    db.session.commit()
    flash("Draft deleted.", "success")
    return redirect(url_for("ai13.ai_assistant"))


# ------------------------------------------------- 2. AI project evaluator
@ai13_bp.route("/faculty/rubrics", methods=["GET", "POST"])
@role_required("faculty", "admin", "manager")
def rubrics():
    courses = _faculty_courses()
    course_ids = [c.id for c in courses]
    projects = (Project.query.filter(Project.course_id.in_(course_ids))
                .order_by(Project.title).all()) if course_ids else []
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:160]
        criteria = _parse_criteria(request.form.get("criteria", ""))
        try:
            course_id = int(request.form.get("course_id") or 0) or None
        except ValueError:
            course_id = None
        try:
            project_id = int(request.form.get("project_id") or 0) or None
        except ValueError:
            project_id = None
        if not name or not criteria:
            flash("Name and at least one 'Criterion : weight' line are "
                  "required.", "danger")
            return redirect(url_for("ai13.rubrics"))
        if course_id and course_id not in course_ids:
            flash("Invalid course.", "danger")
            return redirect(url_for("ai13.rubrics"))
        rubric = Rubric13(name=name, course_id=course_id, project_id=project_id,
                          criteria=criteria, created_by=current_user.id)
        db.session.add(rubric)
        db.session.commit()
        flash(f"Rubric '{name}' created.", "success")
        return redirect(url_for("ai13.rubrics"))
    q = Rubric13.query
    if current_user.role == "faculty":
        q = q.filter(Rubric13.created_by == current_user.id)
    return render_template("p13_rubrics.html", rubrics=q.order_by(
        Rubric13.created_at.desc()).all(), courses=courses,
        projects=projects)


@ai13_bp.route("/faculty/rubrics/<int:rubric_id>/delete", methods=["POST"])
@role_required("faculty", "admin", "manager")
def rubric_delete(rubric_id):
    r = db.session.get(Rubric13, rubric_id)
    if not r:
        from flask import abort
        abort(404)
    if (current_user.role == "faculty" and r.created_by != current_user.id):
        from flask import abort
        abort(403)
    db.session.delete(r)
    db.session.commit()
    flash("Rubric deleted.", "success")
    return redirect(url_for("ai13.rubrics"))


@ai13_bp.route("/faculty/evaluate/<int:sub_id>/ai", methods=["GET", "POST"])
@role_required("faculty", "admin", "manager")
def ai_evaluate(sub_id):
    sub = db.session.get(ProjectSubmission, sub_id)
    if not sub:
        from flask import abort
        abort(404)
    course = sub.project.course
    if current_user.role == "faculty" and course.instructor_id != current_user.id:
        from flask import abort
        abort(403)
    rubrics = (Rubric13.query
               .filter((Rubric13.project_id == sub.project_id) |
                       (Rubric13.course_id == course.id))
               .order_by(Rubric13.project_id.desc().nullslast(),
                         Rubric13.created_at.desc()).all())
    if request.method == "POST":
        try:
            rubric_id = int(request.form.get("rubric_id", 0))
        except ValueError:
            rubric_id = 0
        rubric = db.session.get(Rubric13, rubric_id)
        if not rubric or rubric not in rubrics:
            flash("Pick a valid rubric.", "danger")
            return redirect(url_for("ai13.ai_evaluate", sub_id=sub.id))
        crit_lines = "\n".join(
            f"- {c['name']} (weight {c['weight']})"
            for c in rubric.criteria)
        system = ("You are an expert evaluator for IT training projects. "
                  "Score ONLY what the submission shows — never invent "
                  "achievements, and never mention fees, placements or "
                  "guarantees.\n"
                  "Return ONLY a JSON object, no other text:\n"
                  '{"scores": {"<criterion name>": <0-10 number>}, '
                  '"feedback": "<2-4 sentences of constructive feedback>"}')
        user_text = (f"Project: {sub.project.title}\n"
                     f"Brief: {(sub.project.description or '')[:1200]}\n"
                     f"Max marks: {sub.project.max_marks}\n"
                     f"Student notes: {(sub.notes or '')[:1500]}\n"
                     f"Project URL: {sub.project_url or '(none)'}\n\n"
                     f"Rubric criteria (score each 0-10):\n{crit_lines}")
        raw = ai_generate(system, user_text, max_tokens=600, temperature=0.3)
        if raw is None:
            flash(AI_UNAVAILABLE_MSG, "warning")
            return redirect(url_for("ai13.ai_evaluate", sub_id=sub.id))
        parsed = _extract_json(raw) or {}
        scores_in = parsed.get("scores") if isinstance(parsed, dict) else None
        feedback = (parsed.get("feedback") if isinstance(parsed, dict)
                    else "") or ""
        scores = {}
        for c in rubric.criteria:
            name = c["name"]
            try:
                v = float((scores_in or {}).get(name, 0))
            except (TypeError, ValueError):
                v = 0.0
            scores[name] = round(max(0.0, min(10.0, v)), 1)
        ev = ProjectEvaluation13(
            project_submission_id=sub.id, rubric_id=rubric.id,
            scores=scores, feedback_text=str(feedback)[:4000],
            status="pending_review", evaluated_at=datetime.utcnow())
        sub.status = "under_review"  # existing Phase 6 status value
        db.session.add(ev)
        db.session.commit()
        flash("AI evaluation saved as PENDING REVIEW — a faculty member must "
              "approve it before the student sees anything.", "success")
        return redirect(url_for("ai13.evaluations"))
    default_rubric = next(
        (r for r in rubrics if r.project_id == sub.project_id), None)
    return render_template("p13_evaluate.html", sub=sub, rubrics=rubrics,
                           default_rubric=default_rubric)


@ai13_bp.route("/faculty/evaluations")
@role_required("faculty", "admin", "manager")
def evaluations():
    pending = _eval_query_for_staff().filter(
        ProjectEvaluation13.status == "pending_review").all()
    decided = _eval_query_for_staff().filter(
        ProjectEvaluation13.status != "pending_review").limit(50).all()
    return render_template("p13_evaluations.html", pending=pending,
                           decided=decided)


@ai13_bp.route("/faculty/evaluations/<int:eval_id>/review", methods=["POST"])
@role_required("faculty", "admin", "manager")
def evaluation_review(eval_id):
    ev = db.session.get(ProjectEvaluation13, eval_id)
    if not ev:
        from flask import abort
        abort(404)
    sub = ev.submission
    course = sub.project.course
    if current_user.role == "faculty" and course.instructor_id != current_user.id:
        from flask import abort
        abort(403)
    action = request.form.get("action", "")
    # allow the reviewer to correct the AI's scores/feedback first
    scores = {}
    for c in (ev.rubric.criteria if ev.rubric else []):
        name = c["name"]
        try:
            v = float(request.form.get(f"score_{name}", "") or
                      (ev.scores or {}).get(name, 0))
        except (TypeError, ValueError):
            v = 0.0
        scores[name] = round(max(0.0, min(10.0, v)), 1)
    feedback = request.form.get("feedback", "").strip()[:4000] or ev.feedback_text
    if action == "approve":
        ev.scores = scores
        ev.feedback_text = feedback
        ev.status = "approved"
        ev.reviewed_by = current_user.id
        ev.reviewed_at = datetime.utcnow()
        marks = ev.marks_for(sub.project.max_marks)
        sub.marks = marks
        sub.feedback = feedback
        sub.status = "evaluated"  # existing Phase 6 value — now visible
        sub.evaluated_at = datetime.utcnow()
        sub.evaluated_by = current_user.id
        db.session.commit()
        flash(f"Evaluation approved — student sees {marks}/"
              f"{sub.project.max_marks}.", "success")
    elif action == "reject":
        ev.status = "rejected"
        ev.reviewed_by = current_user.id
        ev.reviewed_at = datetime.utcnow()
        sub.status = "submitted"  # back in the manual grading queue
        db.session.commit()
        flash("AI evaluation rejected — submission returned to the manual "
              "grading queue.", "warning")
    else:
        flash("Unknown action.", "danger")
    return redirect(url_for("ai13.evaluations"))


@ai13_bp.route("/student/evaluations")
@role_required("student")
def student_evaluations():
    """Students see ONLY approved AI evaluations — never pending/rejected."""
    evals = (ProjectEvaluation13.query
             .join(ProjectSubmission,
                   ProjectEvaluation13.project_submission_id
                   == ProjectSubmission.id)
             .filter(ProjectSubmission.user_id == current_user.id,
                     ProjectEvaluation13.status == "approved")
             .order_by(ProjectEvaluation13.reviewed_at.desc()).all())
    return render_template("p13_student_evaluations.html", evals=evals)


# ------------------------------------------------- 3. at-risk flags --------
ATRISK_GUARANTEE = ("At-risk flags are visible to staff only. Students are "
                    "NEVER notified automatically — any outreach is a manual, "
                    "human decision by a counsellor.")


@ai13_bp.route("/counsellor/at-risk")
@role_required("counsellor", "admin", "manager")
def at_risk():
    show = request.args.get("show", "open")
    q = (AtRiskFlag13.query
         .order_by(AtRiskFlag13.created_at.desc()))
    if show == "resolved":
        q = q.filter_by(resolved=True)
    else:
        q = q.filter_by(resolved=False)
        show = "open"
    flags = q.limit(200).all()
    return render_template("p13_atrisk.html", flags=flags, show=show,
                           guarantee=ATRISK_GUARANTEE)


@ai13_bp.route("/counsellor/at-risk/recompute", methods=["POST"])
@role_required("counsellor", "admin", "manager")
def at_risk_recompute():
    from . import atrisk13
    new_flags, total_open = atrisk13.recompute_all()
    if new_flags:
        # Staff-only notification — students are never messaged.
        try:
            from . import hardening as H
            staff = (User.query
                     .filter(User.role.in_(["admin", "manager", "counsellor"]),
                             User.is_active.is_(True)).all())
            for s in staff:
                H.notify(s.id, "at_risk",
                         f"⚠️ {new_flags} new at-risk student(s)",
                         f"{total_open} student(s) currently flagged. "
                         f"Review them on the at-risk page. Students are not "
                         f"notified automatically.",
                         link="/counsellor/at-risk", _commit=True)
        except Exception:
            pass
    flash(f"Recomputed. {new_flags} new flag(s), {total_open} currently open. "
          f"Students were not notified.", "success")
    return redirect(url_for("ai13.at_risk"))


@ai13_bp.route("/counsellor/at-risk/<int:flag_id>/resolve", methods=["POST"])
@role_required("counsellor", "admin", "manager")
def at_risk_resolve(flag_id):
    from . import atrisk13
    if atrisk13.resolve_flag(flag_id):
        flash("Flag marked resolved.", "success")
    else:
        flash("Flag not found.", "danger")
    return redirect(url_for("ai13.at_risk"))


# ------------------------------------------- 4. student memory profile ----
@ai13_bp.route("/student/memory")
@role_required("student")
def student_memory():
    mem = get_memory(current_user.id)
    return render_template("p13_memory.html", mem=mem)


@ai13_bp.route("/student/memory/refresh", methods=["POST"])
@role_required("student")
def student_memory_refresh():
    refresh_memory(current_user.id)
    flash("Memory profile refreshed from your learning activity.", "success")
    return redirect(url_for("ai13.student_memory"))
