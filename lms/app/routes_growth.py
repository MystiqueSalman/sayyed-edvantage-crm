"""Phase 3 routes: referrals, job board, WhatsApp settings.

Public: /r/<code> (referral landing), /jobs, /jobs/<id>.
Student: /referrals (Refer & Earn dashboard), /applications, job apply.
Admin: job CRUD, application pipeline, referral program admin.
Manager: job CRUD + application pipeline (no referral/whatsapp settings).
"""
from datetime import date

from flask import (Blueprint, flash, make_response, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from . import db
from .decorators import admin_required, manager_or_admin, role_required
from .growth import (REF_COOKIE, attribute_signup, get_or_create_referral_code,
                     maybe_reward_referral, record_click, referrer_stats)
from .models import (Coupon, Job, JobApplication, Referral, ReferralSettings,
                     User, WhatsAppSettings)

growth_bp = Blueprint("growth", __name__)
student_only = role_required("student")


# ---------------------------------------------------------------- referral landing (public)
@growth_bp.route("/r/<code>")
def referral_redirect(code):
    record_click(code)
    resp = make_response(redirect(url_for("auth.register")))
    resp.set_cookie(REF_COOKIE, code.upper(), max_age=30 * 24 * 3600,
                    httponly=True, samesite="Lax")
    return resp


# ---------------------------------------------------------------- student: Refer & Earn dashboard
@growth_bp.route("/referrals")
@student_only
def my_referrals():
    code = get_or_create_referral_code(current_user)
    link = url_for("growth.referral_redirect", code=code, _external=True)
    stats = referrer_stats(current_user.id)
    settings = ReferralSettings.get()
    return render_template("student_refer.html", code=code, link=link,
                           stats=stats, settings=settings)


# ---------------------------------------------------------------- job board (public listing + detail)
@growth_bp.route("/jobs")
def jobs():
    today = date.today()
    items = (Job.query.filter(Job.active.is_(True))
             .filter((Job.deadline.is_(None)) | (Job.deadline >= today))
             .order_by(Job.created_at.desc()).all())
    applied_ids = set()
    if current_user.is_authenticated and current_user.role == "student":
        applied_ids = {a.job_id for a in JobApplication.query.filter_by(
            user_id=current_user.id).all()}
    return render_template("jobs.html", jobs=items, applied_ids=applied_ids)


@growth_bp.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    if not job.active and not (current_user.is_authenticated and
                               current_user.role in ("admin", "manager")):
        return render_template("404.html"), 404
    existing = None
    if current_user.is_authenticated and current_user.role == "student":
        existing = JobApplication.query.filter_by(
            job_id=job.id, user_id=current_user.id).first()
    return render_template("job_detail.html", job=job, existing=existing)


@growth_bp.route("/jobs/<int:job_id>/apply", methods=["POST"])
@student_only
def job_apply(job_id):
    job = Job.query.get_or_404(job_id)
    if not job.is_open() or job.apply_mode != Job.APPLY_INTERNAL:
        flash("Applications are closed for this posting.", "warning")
        return redirect(url_for("growth.job_detail", job_id=job.id))
    if JobApplication.query.filter_by(job_id=job.id,
                                      user_id=current_user.id).first():
        flash("You've already applied for this job.", "info")
        return redirect(url_for("growth.job_detail", job_id=job.id))
    note = request.form.get("cover_note", "").strip()
    # keep the student's phone fresh for WhatsApp/pipeline contact
    phone = request.form.get("phone", "").strip()
    if phone and phone != (current_user.phone or ""):
        current_user.phone = phone
    db.session.add(JobApplication(job_id=job.id, user_id=current_user.id,
                                  cover_note=note))
    db.session.commit()
    flash(f"Application sent for {job.title} at {job.company}. Good luck! 🍀",
          "success")
    return redirect(url_for("growth.my_applications"))


@growth_bp.route("/applications")
@student_only
def my_applications():
    apps = (JobApplication.query.filter_by(user_id=current_user.id)
            .order_by(JobApplication.applied_at.desc()).all())
    return render_template("my_applications.html", apps=apps)


# ---------------------------------------------------------------- admin: jobs (manager allowed)
@growth_bp.route("/admin/jobs", methods=["GET", "POST"])
@manager_or_admin
def admin_jobs():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Job title is required.", "danger")
            return redirect(url_for("growth.admin_jobs"))
        deadline_raw = request.form.get("deadline", "").strip()
        deadline = None
        if deadline_raw:
            try:
                deadline = date.fromisoformat(deadline_raw)
            except ValueError:
                deadline = None
        db.session.add(Job(
            title=title,
            company=request.form.get("company", "").strip(),
            type=request.form.get("type", Job.TYPE_JOB)
            if request.form.get("type") in Job.TYPES else Job.TYPE_JOB,
            location=request.form.get("location", "").strip(),
            remote=bool(request.form.get("remote")),
            description=request.form.get("description", "").strip(),
            skills=request.form.get("skills", "").strip(),
            deadline=deadline,
            active=bool(request.form.get("active")),
            apply_mode=(request.form.get("apply_mode")
                        if request.form.get("apply_mode") in
                        (Job.APPLY_INTERNAL, Job.APPLY_EXTERNAL)
                        else Job.APPLY_INTERNAL),
            external_url=request.form.get("external_url", "").strip(),
            created_by=current_user.id))
        db.session.commit()
        flash(f"Job '{title}' posted.", "success")
        return redirect(url_for("growth.admin_jobs"))
    items = Job.query.order_by(Job.created_at.desc()).all()
    return render_template("admin_jobs.html", jobs=items, job_types=Job.TYPES)


@growth_bp.route("/admin/jobs/<int:job_id>/toggle", methods=["POST"])
@manager_or_admin
def admin_job_toggle(job_id):
    job = Job.query.get_or_404(job_id)
    job.active = not job.active
    db.session.commit()
    return redirect(url_for("growth.admin_jobs"))


@growth_bp.route("/admin/jobs/<int:job_id>/delete", methods=["POST"])
@admin_required
def admin_job_delete(job_id):
    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash("Job posting deleted.", "info")
    return redirect(url_for("growth.admin_jobs"))


@growth_bp.route("/admin/jobs/<int:job_id>/applications", methods=["GET", "POST"])
@manager_or_admin
def admin_job_applications(job_id):
    job = Job.query.get_or_404(job_id)
    if request.method == "POST":
        app_id = int(request.form.get("app_id") or 0)
        status = request.form.get("status", "")
        appn = JobApplication.query.filter_by(id=app_id, job_id=job.id).first()
        if appn and status in JobApplication.STATUSES:
            appn.status = status
            db.session.commit()
            flash(f"Application #{appn.id} → {status}.", "success")
        return redirect(url_for("growth.admin_job_applications", job_id=job.id))
    apps = (JobApplication.query.filter_by(job_id=job.id)
            .order_by(JobApplication.applied_at.desc()).all())
    return render_template("admin_job_applications.html", job=job, apps=apps,
                           statuses=JobApplication.STATUSES)


# ---------------------------------------------------------------- admin: referrals (admin only)
@growth_bp.route("/admin/referrals", methods=["GET", "POST"])
@admin_required
def admin_referrals():
    settings = ReferralSettings.get()
    if request.method == "POST":
        try:
            pct = int(request.form.get("reward_percent", 10) or 10)
        except ValueError:
            pct = 10
        settings.reward_percent = max(1, min(100, pct))
        settings.enabled = bool(request.form.get("enabled"))
        db.session.commit()
        flash("Referral program settings saved.", "success")
        return redirect(url_for("growth.admin_referrals"))
    refs = Referral.query.order_by(Referral.created_at.desc()).limit(200).all()
    return render_template("admin_referrals.html", settings=settings, refs=refs)


@growth_bp.route("/admin/referrals/<int:ref_id>/invalidate", methods=["POST"])
@admin_required
def admin_referral_invalidate(ref_id):
    ref = Referral.query.get_or_404(ref_id)
    ref.status = Referral.STATUS_INVALID
    db.session.commit()
    flash("Referral marked invalid — no reward will be issued.", "warning")
    return redirect(url_for("growth.admin_referrals"))


@growth_bp.route("/admin/referrals/<int:ref_id>/validate", methods=["POST"])
@admin_required
def admin_referral_validate(ref_id):
    ref = Referral.query.get_or_404(ref_id)
    if ref.status == Referral.STATUS_INVALID:
        from .growth import _has_paid_enrollment
        ref.status = (Referral.STATUS_ENROLLED
                      if _has_paid_enrollment(ref.referred_id)
                      else Referral.STATUS_SIGNED_UP)
        db.session.commit()
        # a re-validated referral may now qualify for its reward
        maybe_reward_referral(ref.referred)
        flash("Referral re-validated.", "success")
    return redirect(url_for("growth.admin_referrals"))


# ---------------------------------------------------------------- admin: WhatsApp settings (admin only)
@growth_bp.route("/admin/whatsapp-settings", methods=["GET", "POST"])
@admin_required
def whatsapp_settings():
    settings = WhatsAppSettings.get()
    if request.method == "POST":
        if "send_test" in request.form:
            from .whatsapp import send_whatsapp_sync
            to = request.form.get("test_phone", "").strip()
            ok, msg = send_whatsapp_sync(
                to, "✅ *Sayyed EdVantage LMS*\nWhatsApp notifications are "
                    "working. Students will get enrollment, payment, class "
                    "reminder and grading alerts here.")
            flash(msg, "success" if ok else "danger")
        else:
            settings.phone_number_id = request.form.get(
                "phone_number_id", "").strip()
            if request.form.get("access_token"):  # never prefill / overwrite blank
                settings.access_token = request.form.get("access_token").strip()
            settings.enabled = bool(request.form.get("enabled"))
            db.session.commit()
            flash("WhatsApp settings saved.", "success")
        return redirect(url_for("growth.whatsapp_settings"))
    # The access token is NEVER passed back to the template.
    return render_template("admin_whatsapp.html", settings=settings,
                           token_set=bool(settings.access_token))
