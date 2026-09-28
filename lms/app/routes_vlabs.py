"""Phase 12 §21.6 — virtual labs routes (simulated terminal, no real infra)."""
import json

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for, flash)
from flask_login import current_user, login_required

from . import db
from . import operations as OPS
from . import vlabs as VLAB
from .decorators import content_manager_required, role_required
from .models import Course, VLabProgress, VLabScenario

vlabs_bp = Blueprint("vlabs", __name__)
student_only = role_required("student")


# ------------------------------------------------------------ student UI


def ensure_vlab_examples():
    """Idempotent seed: one published Linux basics scenario."""
    try:
        from .models import Course, VLabScenario
        from .vlabs import example_json
        if VLabScenario.query.filter_by(
                title="Linux Basics — Files & Folders").first():
            return
        course = Course.query.filter_by(slug="linux-administration").first()
        db.session.add(VLabScenario(
            title="Linux Basics — Files & Folders",
            description=("Practice pwd, ls, cd, mkdir and cat in a simulated "
                         "Linux terminal. No real server is touched."),
            course_id=course.id if course else None,
            scenario_json=example_json(),
            is_published=True,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

@vlabs_bp.route("/vlabs")
@login_required
def vlab_list():
    scenarios = (VLabScenario.query.filter_by(is_published=True)
                 .order_by(VLabScenario.created_at.desc()).all())
    done_ids = {p.scenario_id for p in VLabProgress.query
                .filter_by(user_id=current_user.id, completed=True).all()}
    return render_template("vlabs_list.html", scenarios=scenarios,
                           done_ids=done_ids)


@vlabs_bp.route("/vlabs/<int:scenario_id>")
@login_required
def vlab_terminal(scenario_id):
    scenario = VLabScenario.query.filter_by(
        id=scenario_id, is_published=True).first_or_404()
    progress = VLabProgress.query.filter_by(
        scenario_id=scenario.id, user_id=current_user.id).first()
    return render_template("vlab_terminal.html", scenario=scenario,
                           scenario_json=json.dumps(scenario.scenario),
                           progress=progress)


@vlabs_bp.route("/vlabs/<int:scenario_id>/complete", methods=["POST"])
@login_required
def vlab_complete(scenario_id):
    scenario = VLabScenario.query.filter_by(
        id=scenario_id, is_published=True).first_or_404()
    data = request.get_json(silent=True) or {}
    prog = VLAB.mark_complete(scenario.id, current_user.id,
                              data.get("log", ""))
    OPS.audit(current_user, "vlab.complete", "vlab_scenario", scenario.id,
              scenario.title, request.remote_addr or "")
    return jsonify({"ok": True, "completed_at": str(prog.completed_at)})


# ------------------------------------------------------------ faculty authoring

@vlabs_bp.route("/manage/vlabs")
@content_manager_required
def manage_list():
    scenarios = (VLabScenario.query
                 .order_by(VLabScenario.created_at.desc()).all())
    return render_template("vlab_manage_list.html", scenarios=scenarios)


@vlabs_bp.route("/manage/vlabs/new", methods=["GET", "POST"])
@content_manager_required
def manage_new():
    courses = Course.query.order_by(Course.title).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        raw = request.form.get("scenario_json", "")
        ok, data_or_err = VLAB.validate_scenario_json(raw)
        if not title:
            flash("Title is required.", "error")
        elif not ok:
            flash(data_or_err, "error")
        else:
            sc = VLabScenario(
                title=title,
                course_id=request.form.get("course_id", type=int) or None,
                description=request.form.get("description", ""),
                scenario_json=raw,
                is_published=bool(request.form.get("is_published")),
                created_by=current_user.id)
            db.session.add(sc)
            db.session.commit()
            OPS.audit(current_user, "vlab.create", "vlab_scenario", sc.id,
                      title, request.remote_addr or "")
            flash("Virtual lab scenario created.", "ok")
            return redirect(url_for("vlabs.manage_list"))
    return render_template("vlab_form.html", courses=courses, scenario=None,
                           example=VLAB.example_json())


@vlabs_bp.route("/manage/vlabs/<int:scenario_id>/edit", methods=["GET", "POST"])
@content_manager_required
def manage_edit(scenario_id):
    scenario = VLabScenario.query.get_or_404(scenario_id)
    courses = Course.query.order_by(Course.title).all()
    if request.method == "POST":
        raw = request.form.get("scenario_json", "")
        ok, data_or_err = VLAB.validate_scenario_json(raw)
        if not ok:
            flash(data_or_err, "error")
        else:
            scenario.title = request.form.get("title", "").strip() or scenario.title
            scenario.course_id = request.form.get("course_id", type=int) or None
            scenario.description = request.form.get("description", "")
            scenario.scenario_json = raw
            scenario.is_published = bool(request.form.get("is_published"))
            db.session.commit()
            OPS.audit(current_user, "vlab.update", "vlab_scenario",
                      scenario.id, scenario.title, request.remote_addr or "")
            flash("Scenario updated.", "ok")
            return redirect(url_for("vlabs.manage_list"))
    return render_template("vlab_form.html", courses=courses,
                           scenario=scenario, example=VLAB.example_json())


@vlabs_bp.route("/manage/vlabs/<int:scenario_id>/delete", methods=["POST"])
@content_manager_required
def manage_delete(scenario_id):
    scenario = VLabScenario.query.get_or_404(scenario_id)
    db.session.delete(scenario)
    db.session.commit()
    OPS.audit(current_user, "vlab.delete", "vlab_scenario", scenario_id, "",
              request.remote_addr or "")
    flash("Scenario deleted.", "ok")
    return redirect(url_for("vlabs.manage_list"))
