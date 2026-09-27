"""Phase 5 — AI Tutor, study planner and revision routes (students)."""
import json
from datetime import date, datetime

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from . import db
from .ai_tutor import (ask_tutor, clear_memory, daily_limit,
                       generate_study_plan, get_memory, memory_snapshot,
                       questions_used_today, todays_plan_items,
                       tutor_course_enabled, tutor_globally_enabled,
                       weak_topics_for_student)
from .decorators import role_required
from .models import (AITutorExchange, Course, Enrollment, Lesson, StudyPlan,
                     StudyPlanItem)
from .routes_student import _active_enrollment_or_403

tutor_bp = Blueprint("tutor", __name__)
student_only = role_required("student")


def _enrolled_courses():
    enrollments = (Enrollment.query.filter_by(user_id=current_user.id)
                   .filter(Enrollment.status.in_(
                       [Enrollment.STATUS_ACTIVE,
                        Enrollment.STATUS_COMPLETED]))
                   .order_by(Enrollment.enrolled_at.desc()).all())
    return [e.course for e in enrollments]


def _pick_course(course_id):
    """Return (course, enrolled_courses).

    If course_id is given but the student isn't enrolled in it, returns
    (None, courses) so the caller can redirect with a friendly message —
    the student never sees content for a course they aren't enrolled in.
    """
    courses = _enrolled_courses()
    if not courses:
        return None, []
    if course_id:
        course = next((c for c in courses if c.id == course_id), None)
        return course, courses
    return courses[0], courses


def _resolve_course_or_redirect(course_id, endpoint):
    """Shared guard for tutor/planner/revise pages.

    Returns (course, courses, response): if response is not None, the
    caller must return it (redirect with an explanatory flash).
    """
    if not tutor_globally_enabled():
        flash("The AI Tutor is currently disabled by the admin.", "warning")
        return None, None, redirect(url_for("student.dashboard"))
    course, courses = _pick_course(course_id)
    if not courses:
        flash("Enroll in a course to use this feature.", "warning")
        return None, None, redirect(url_for("main.catalog"))
    if not course:
        flash("You are not enrolled in that course.", "warning")
        return None, None, redirect(url_for(endpoint))
    if not tutor_course_enabled(course):
        flash(f"AI Tutor is disabled for {course.title}.", "warning")
        return None, None, redirect(url_for("student.dashboard"))
    return course, courses, None


@tutor_bp.route("/tutor")
@student_only
def tutor_home():
    course_id = request.args.get("course_id", type=int)
    prefill = request.args.get("q", "")
    lesson_id = request.args.get("lesson_id", type=int)
    course, courses, redir = _resolve_course_or_redirect(
        course_id, "tutor.tutor_home")
    if redir:
        return redir
    # refresh weak topics from latest quiz answers (feeds memory + revise card)
    weak = weak_topics_for_student(current_user.id, course.id)
    mem = memory_snapshot(current_user.id, course.id)
    history = (AITutorExchange.query
               .filter_by(user_id=current_user.id, course_id=course.id)
               .order_by(AITutorExchange.created_at.desc())
               .limit(20).all())
    history = list(reversed(history))
    lesson = db.session.get(Lesson, lesson_id) if lesson_id else None
    if lesson and lesson.module.course_id != course.id:
        lesson = None
    return render_template("tutor.html", course=course, courses=courses,
                           weak=weak, mem=mem, history=history,
                           prefill=prefill, focus_lesson=lesson,
                           used_today=questions_used_today(current_user.id),
                           daily_limit=daily_limit())


@tutor_bp.route("/tutor/ask", methods=["POST"])
@student_only
def tutor_ask():
    data = request.get_json(force=True, silent=True) or {}
    course = db.session.get(Course, data.get("course_id") or 0)
    if not course or not _active_enrollment_or_403(course.id):
        return jsonify({"error": "not_enrolled"}), 403
    answer, cited, err = ask_tutor(current_user, course,
                                   data.get("question", ""))
    if err:
        return jsonify({"error": err,
                        "limit": daily_limit(),
                        "used": questions_used_today(current_user.id)}), 200
    lesson_titles = {}
    if cited:
        for l in Lesson.query.filter(Lesson.id.in_(cited)).all():
            lesson_titles[l.id] = l.title
    return jsonify({"answer": answer, "cited": cited,
                    "cited_titles": lesson_titles,
                    "used": questions_used_today(current_user.id),
                    "limit": daily_limit()})


@tutor_bp.route("/tutor/memory/clear", methods=["POST"])
@student_only
def tutor_memory_clear():
    course_id = request.form.get("course_id", type=int)
    course, _ = _pick_course(course_id)
    if not course or not _active_enrollment_or_403(course.id):
        abort(403)
    clear_memory(current_user.id, course.id)
    flash("Your AI tutor memory for this course has been cleared.", "info")
    return redirect(url_for("tutor.tutor_home", course_id=course.id))


# ------------------------------------------------------------ study planner

@tutor_bp.route("/planner")
@student_only
def planner():
    course_id = request.args.get("course_id", type=int)
    course, courses, redir = _resolve_course_or_redirect(
        course_id, "tutor.planner")
    if redir:
        return redir
    plan = StudyPlan.query.filter_by(user_id=current_user.id,
                                     course_id=course.id).first()
    items_by_date = {}
    if plan:
        for it in plan.items:
            items_by_date.setdefault(it.planned_date, []).append(it)
    return render_template("planner.html", course=course, courses=courses,
                           plan=plan, items_by_date=items_by_date,
                           today=date.today())


@tutor_bp.route("/planner/generate", methods=["POST"])
@student_only
def planner_generate():
    course = db.session.get(Course, request.form.get("course_id", type=int) or 0)
    if not course or not _active_enrollment_or_403(course.id):
        abort(403)
    try:
        target = datetime.strptime(
            request.form.get("target_date", ""), "%Y-%m-%d").date()
    except ValueError:
        flash("Please pick a valid target date.", "danger")
        return redirect(url_for("tutor.planner", course_id=course.id))
    hours = request.form.get("hours_per_day", "1")
    try:
        plan, warning = generate_study_plan(current_user, course, target,
                                            float(hours))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("tutor.planner", course_id=course.id))
    if warning:
        flash(warning, "warning")
    else:
        flash(f"Study plan ready — {len(plan.items)} lessons scheduled "
              f"until {plan.target_date.strftime('%d %b %Y')}.", "success")
    return redirect(url_for("tutor.planner", course_id=course.id))


@tutor_bp.route("/planner/item/<int:item_id>/toggle", methods=["POST"])
@student_only
def planner_item_toggle(item_id):
    item = StudyPlanItem.query.get_or_404(item_id)
    if item.plan.user_id != current_user.id:
        abort(403)
    item.done = not item.done
    db.session.commit()
    wants_json = (request.is_json or "application/json" in
                  request.headers.get("Accept", ""))
    if wants_json:
        return jsonify({"done": item.done})
    return redirect(url_for("tutor.planner", course_id=item.plan.course_id))


# ------------------------------------------------------------ revise

@tutor_bp.route("/revise")
@student_only
def revise():
    course_id = request.args.get("course_id", type=int)
    course, courses, redir = _resolve_course_or_redirect(
        course_id, "tutor.revise")
    if redir:
        return redir
    weak = weak_topics_for_student(current_user.id, course.id)
    return render_template("revise.html", course=course, courses=courses,
                           weak=weak)
