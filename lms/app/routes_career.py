"""Phase 7 — Career & Placements routes: resume, portfolio, mock interviews,
readiness score (students); employer portal; placement analytics + employer
approval + readiness weights (admin/manager)."""
import json
from datetime import date, datetime

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from flask_login import current_user

from . import db
from .career import (GUIDANCE_DISCLAIMER, INTERVIEW_QUESTIONS,
                     interview_ask_question, interview_feedback,
                     interview_finalize, readiness_for, resume_for,
                     resume_sections)
from .decorators import manager_or_admin, role_required
from .models import (Certificate, Course, Enrollment, Job, JobApplication,
                     MockInterview, MockInterviewQA, Portfolio, ReadinessWeights,
                     Resume, User, UserBadge, ROLE_EMPLOYER)

career_bp = Blueprint("career", __name__)
student_only = role_required("student")
employer_only = role_required(ROLE_EMPLOYER)


def _employer_jobs():
    return (Job.query.filter_by(employer_id=current_user.id)
            .order_by(Job.created_at.desc()).all())


def _employer_job_or_404(job_id):
    """Employers may only touch their own postings."""
    job = Job.query.get_or_404(job_id)
    if job.employer_id != current_user.id:
        abort(404)
    return job


def _parse_deadline(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _fill_job_from_form(job, form, employer):
    job.title = form.get("title", "").strip()
    job.company = form.get("company", "").strip() or (employer.company or "")
    job.type = form.get("type") if form.get("type") in Job.TYPES else Job.TYPE_JOB
    job.location = form.get("location", "").strip()
    job.remote = bool(form.get("remote"))
    job.description = form.get("description", "").strip()
    job.skills = form.get("skills", "").strip()
    job.deadline = _parse_deadline(form.get("deadline"))
    job.active = bool(form.get("active"))
    job.apply_mode = (form.get("apply_mode")
                      if form.get("apply_mode") in (Job.APPLY_INTERNAL, Job.APPLY_EXTERNAL)
                      else Job.APPLY_INTERNAL)
    job.external_url = form.get("external_url", "").strip()
    return job


# ============================================================ student: hub
@career_bp.route("/career")
@student_only
def hub():
    rd = readiness_for(current_user)
    interviews = (MockInterview.query.filter_by(user_id=current_user.id)
                  .order_by(MockInterview.created_at.desc()).limit(5).all())
    r = resume_for(current_user)
    pf = Portfolio.query.filter_by(user_id=current_user.id).first()
    return render_template("career_hub.html", readiness=rd,
                           interviews=interviews, resume=r, portfolio=pf,
                           disclaimer=GUIDANCE_DISCLAIMER)


# ============================================================ student: resume
@career_bp.route("/career/resume", methods=["GET", "POST"])
@student_only
def resume_builder():
    r = resume_for(current_user)
    if request.method == "POST":
        r.headline = request.form.get("headline", "").strip()[:160]
        r.summary = request.form.get("summary", "").strip()
        r.skills_text = request.form.get("skills_text", "").strip()
        try:
            exp = json.loads(request.form.get("experience_json", "[]") or "[]")
            r.experience_json = json.dumps(exp if isinstance(exp, list) else [])
        except (ValueError, TypeError):
            pass
        try:
            edu = json.loads(request.form.get("education_json", "[]") or "[]")
            r.education_json = json.dumps(edu if isinstance(edu, list) else [])
        except (ValueError, TypeError):
            pass
        try:
            links = json.loads(request.form.get("links_json", "{}") or "{}")
            r.links_json = json.dumps(links if isinstance(links, dict) else {})
        except (ValueError, TypeError):
            pass
        db.session.commit()
        flash("Resume saved.", "success")
        return redirect(url_for("career.resume_builder"))
    sections = resume_sections(current_user)
    return render_template("resume_builder.html", sections=sections,
                           exp_json=r.experience_json, edu_json=r.education_json,
                           links_json=r.links_json)


@career_bp.route("/career/resume/pdf")
@student_only
def resume_pdf():
    from .pdfresume import generate_resume_pdf, resume_path
    sections = resume_sections(current_user)
    out = resume_path(current_user.id, current_app.config["UPLOAD_DIR"])
    generate_resume_pdf(sections, out)
    return send_file(out, as_attachment=True,
                     download_name=f"resume_{current_user.name.replace(' ', '_')}.pdf")


# ============================================================ portfolio
@career_bp.route("/career/portfolio", methods=["GET", "POST"])
@student_only
def portfolio_edit():
    pf = Portfolio.query.filter_by(user_id=current_user.id).first()
    if not pf:
        pf = Portfolio(user_id=current_user.id, code=Portfolio.new_code())
        db.session.add(pf)
        db.session.commit()
    if request.method == "POST":
        pf.headline = request.form.get("headline", "").strip()[:160]
        pf.about = request.form.get("about", "").strip()
        pf.is_public = bool(request.form.get("is_public"))
        pf.show_resume = bool(request.form.get("show_resume"))
        if request.form.get("regen_code"):
            pf.code = Portfolio.new_code()
        db.session.commit()
        flash("Portfolio saved.", "success")
        return redirect(url_for("career.portfolio_edit"))
    sections = resume_sections(current_user)
    public_url = url_for("career.portfolio_public", code=pf.code, _external=True)
    return render_template("portfolio_edit.html", portfolio=pf,
                           sections=sections, public_url=public_url)


@career_bp.route("/portfolio/<code>")
def portfolio_public(code):
    pf = Portfolio.query.filter_by(code=code).first_or_404()
    if not pf.is_public:
        abort(404)
    sections = resume_sections(pf.user)
    # Phase 8: badge showcase on public portfolio
    badges = (UserBadge.query.filter_by(user_id=pf.user_id)
              .order_by(UserBadge.awarded_at.desc()).all())
    return render_template("portfolio_public.html", portfolio=pf,
                           sections=sections, owner=pf.user, badges=badges)


@career_bp.route("/portfolio/<code>/resume.pdf")
def portfolio_resume_pdf(code):
    pf = Portfolio.query.filter_by(code=code).first_or_404()
    if not pf.is_public or not pf.show_resume:
        abort(404)
    from .pdfresume import generate_resume_pdf, resume_path
    sections = resume_sections(pf.user)
    out = resume_path(pf.user_id, current_app.config["UPLOAD_DIR"])
    generate_resume_pdf(sections, out)
    return send_file(out, as_attachment=True,
                     download_name=f"resume_{pf.user.name.replace(' ', '_')}.pdf")


# ============================================================ mock interviews
def _interview_courses():
    return [e.course for e in
            Enrollment.query.filter_by(user_id=current_user.id)
            .filter(Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                                          Enrollment.STATUS_COMPLETED]))
            .order_by(Enrollment.enrolled_at.desc()).all()]


@career_bp.route("/career/interviews", methods=["GET", "POST"])
@student_only
def interviews():
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        target_role = request.form.get("target_role", "").strip()[:160]
        course = db.session.get(Course, course_id) if course_id else None
        if course and course not in _interview_courses():
            flash("You are not enrolled in that course.", "warning")
            return redirect(url_for("career.interviews"))
        if not target_role:
            flash("Please enter a target role.", "warning")
            return redirect(url_for("career.interviews"))
        session = MockInterview(user_id=current_user.id,
                               course_id=course.id if course else None,
                               target_role=target_role,
                               questions_total=INTERVIEW_QUESTIONS)
        db.session.add(session)
        db.session.flush()
        q = interview_ask_question(session)
        db.session.add(MockInterviewQA(session_id=session.id, position=0,
                                       question=q))
        db.session.commit()
        return redirect(url_for("career.interview_session",
                                session_id=session.id))
    sessions = (MockInterview.query.filter_by(user_id=current_user.id)
                .order_by(MockInterview.created_at.desc()).all())
    return render_template("interviews.html", sessions=sessions,
                           courses=_interview_courses())


@career_bp.route("/career/interviews/<int:session_id>")
@student_only
def interview_session(session_id):
    session = MockInterview.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        abort(404)
    pending = next((q for q in session.qas if not (q.answer or "").strip()),
                   None)
    return render_template("interview_session.html", session=session,
                           pending=pending)


@career_bp.route("/career/interviews/<int:session_id>/answer", methods=["POST"])
@student_only
def interview_answer(session_id):
    session = MockInterview.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        abort(404)
    if session.status != MockInterview.STATUS_ACTIVE:
        return jsonify({"error": "completed"}), 400
    data = request.get_json(force=True, silent=True) or {}
    qa = next((q for q in session.qas if not (q.answer or "").strip()), None)
    if not qa:
        return jsonify({"error": "no_pending"}), 400
    qa.answer = (data.get("answer") or "").strip()[:4000]
    score, feedback = interview_feedback(session, qa.question, qa.answer)
    qa.score, qa.feedback = score, feedback
    db.session.commit()
    done = session.answered_count() >= (session.questions_total or INTERVIEW_QUESTIONS)
    next_q = None
    if not done:
        nq = interview_ask_question(session)
        db.session.add(MockInterviewQA(session_id=session.id,
                                       position=len(session.qas),
                                       question=nq))
        db.session.commit()
        next_q = nq
    else:
        interview_finalize(session)
        # Phase 8: mock interview completion points
        from . import gamification as G
        G.award_points(current_user.id, "mock_interview_complete",
                       "interview", session.id)
    return jsonify({"score": score, "feedback": feedback, "done": done,
                    "next_question": next_q,
                    "overall": session.score if done else None})


@career_bp.route("/career/interviews/<int:session_id>/finish", methods=["POST"])
@student_only
def interview_finish(session_id):
    session = MockInterview.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        abort(404)
    if session.status == MockInterview.STATUS_ACTIVE:
        interview_finalize(session)
        # Phase 8: mock interview completion points (idempotent)
        from . import gamification as G
        G.award_points(current_user.id, "mock_interview_complete",
                       "interview", session.id)
        flash("Interview completed — see your feedback below.", "success")
    return redirect(url_for("career.interview_session", session_id=session.id))


# ============================================================ readiness
@career_bp.route("/career/readiness")
@student_only
def readiness():
    rd = readiness_for(current_user)
    return render_template("readiness.html", readiness=rd,
                           disclaimer=GUIDANCE_DISCLAIMER)


# ============================================================ employer signup
@career_bp.route("/employer/signup", methods=["GET", "POST"])
def employer_signup():
    if current_user.is_authenticated:
        return redirect(url_for("career.employer_dashboard")
                        if current_user.role == ROLE_EMPLOYER else "/")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "").strip()
        company = request.form.get("company", "").strip()
        if not name or not email or not company or len(pw) < 6:
            flash("Please fill all fields (password min 6 characters).", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
        else:
            u = User(name=name, email=email, role=ROLE_EMPLOYER,
                     company=company[:160], is_active=False,
                     phone=request.form.get("phone", "").strip()[:20])
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            flash("Application received — our team will review and activate "
                  "your employer account shortly.", "success")
            return redirect(url_for("auth.login"))
    return render_template("employer_signup.html")


# ============================================================ employer portal
@career_bp.route("/employer")
@employer_only
def employer_dashboard():
    jobs = _employer_jobs()
    counts = {}
    for j in jobs:
        counts[j.id] = {
            "total": len(j.applications),
            "placed": sum(1 for a in j.applications
                          if a.status == JobApplication.STATUS_PLACED),
        }
    return render_template("employer_dashboard.html", jobs=jobs, counts=counts)


@career_bp.route("/employer/jobs/new", methods=["GET", "POST"])
@employer_only
def employer_job_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Job title is required.", "danger")
            return redirect(url_for("career.employer_job_new"))
        job = _fill_job_from_form(Job(), request.form, current_user)
        job.employer_id = current_user.id
        job.created_by = current_user.id
        db.session.add(job)
        db.session.commit()
        flash(f"Job '{title}' posted.", "success")
        return redirect(url_for("career.employer_dashboard"))
    return render_template("employer_job_form.html", job=None,
                           job_types=Job.TYPES,
                           default_company=current_user.company or "")


@career_bp.route("/employer/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@employer_only
def employer_job_edit(job_id):
    job = _employer_job_or_404(job_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Job title is required.", "danger")
            return redirect(url_for("career.employer_job_edit", job_id=job.id))
        _fill_job_from_form(job, request.form, current_user)
        db.session.commit()
        flash("Job updated.", "success")
        return redirect(url_for("career.employer_dashboard"))
    return render_template("employer_job_form.html", job=job,
                           job_types=Job.TYPES,
                           default_company=current_user.company or "")


@career_bp.route("/employer/jobs/<int:job_id>/toggle", methods=["POST"])
@employer_only
def employer_job_toggle(job_id):
    job = _employer_job_or_404(job_id)
    job.active = not job.active
    db.session.commit()
    flash(f"Job {'activated' if job.active else 'paused'}.", "info")
    return redirect(url_for("career.employer_dashboard"))


@career_bp.route("/employer/jobs/<int:job_id>/applications", methods=["GET", "POST"])
@employer_only
def employer_applications(job_id):
    job = _employer_job_or_404(job_id)
    if request.method == "POST":
        app_id = request.form.get("application_id", type=int)
        app = JobApplication.query.get_or_404(app_id)
        if app.job_id != job.id:
            abort(404)
        new_status = request.form.get("status", "")
        if new_status in JobApplication.STATUSES:
            app.status = new_status
        app.employer_note = request.form.get("employer_note", "").strip()[:2000]
        db.session.commit()
        flash("Candidate updated.", "success")
        return redirect(url_for("career.employer_applications", job_id=job.id))
    return render_template("employer_applications.html", job=job,
                           statuses=JobApplication.STATUSES)


# ============================================================ admin: employers
@career_bp.route("/admin/employers")
@manager_or_admin
def admin_employers():
    pending = (User.query.filter_by(role=ROLE_EMPLOYER, is_active=False)
               .order_by(User.created_at.desc()).all())
    active = (User.query.filter_by(role=ROLE_EMPLOYER, is_active=True)
              .order_by(User.created_at.desc()).all())
    return render_template("admin_employers.html", pending=pending,
                           active=active)


@career_bp.route("/admin/employers/<int:user_id>/approve", methods=["POST"])
@manager_or_admin
def admin_employer_approve(user_id):
    u = User.query.get_or_404(user_id)
    if u.role != ROLE_EMPLOYER:
        abort(404)
    u.is_active = True
    db.session.commit()
    flash(f"Employer {u.email} approved.", "success")
    return redirect(url_for("career.admin_employers"))


@career_bp.route("/admin/employers/<int:user_id>/reject", methods=["POST"])
@manager_or_admin
def admin_employer_reject(user_id):
    u = User.query.get_or_404(user_id)
    if u.role != ROLE_EMPLOYER:
        abort(404)
    db.session.delete(u)
    db.session.commit()
    flash(f"Employer application {u.email} rejected and removed.", "info")
    return redirect(url_for("career.admin_employers"))


# ============================================================ admin: placement analytics
@career_bp.route("/admin/placement-analytics")
@manager_or_admin
def placement_analytics():
    apps = JobApplication.query.all()
    funnel = {s: 0 for s in JobApplication.STATUSES}
    for a in apps:
        funnel[a.status] = funnel.get(a.status, 0) + 1
    total = len(apps) or 1
    placed = funnel.get(JobApplication.STATUS_PLACED, 0)
    offered = funnel.get(JobApplication.STATUS_OFFERED, 0)
    # course-wise outcomes: enrolled students with a placed application
    course_rows = []
    for c in Course.query.filter_by(is_bonus=False).order_by(Course.title).all():
        enrolled_ids = {e.user_id for e in
                        Enrollment.query.filter_by(course_id=c.id).all()}
        placed_n = sum(1 for a in apps
                       if a.status == JobApplication.STATUS_PLACED
                       and a.user_id in enrolled_ids)
        applied_n = sum(1 for a in apps if a.user_id in enrolled_ids)
        course_rows.append({"course": c.title, "applied": applied_n,
                            "placed": placed_n})
    # employer leaderboard: by placed candidates
    emp_rows = []
    employers = User.query.filter_by(role=ROLE_EMPLOYER, is_active=True).all()
    for emp in employers:
        emp_jobs = Job.query.filter_by(employer_id=emp.id).all()
        emp_apps = [a for j in emp_jobs for a in j.applications]
        emp_rows.append({
            "company": emp.company or emp.name,
            "jobs": len(emp_jobs),
            "applications": len(emp_apps),
            "placed": sum(1 for a in emp_apps
                          if a.status == JobApplication.STATUS_PLACED),
        })
    emp_rows.sort(key=lambda r: r["placed"], reverse=True)
    return render_template(
        "placement_analytics.html",
        funnel=funnel, funnel_labels=list(funnel.keys()),
        funnel_values=list(funnel.values()),
        offer_rate=round(100 * (offered + placed) / total, 1),
        placement_rate=round(100 * placed / total, 1),
        course_rows=course_rows, emp_rows=emp_rows[:10],
        total_apps=len(apps))


# ============================================================ admin: career settings
@career_bp.route("/admin/career-settings", methods=["GET", "POST"])
@manager_or_admin
def career_settings():
    w = ReadinessWeights.get()
    if request.method == "POST":
        for field in ("w_completion", "w_quiz", "w_projects", "w_resume",
                      "w_interviews", "w_certificates"):
            try:
                v = float(request.form.get(field, "0") or 0)
            except (ValueError, TypeError):
                v = 0.0
            setattr(w, field, max(0.0, min(100.0, v)))
        db.session.commit()
        flash("Readiness weights saved (normalized to 100%).", "success")
        return redirect(url_for("career.career_settings"))
    return render_template("career_settings.html", weights=w)
