"""Phase 12 §21 — SaaS/enterprise routes: tenancy, branding, i18n switch,
bulk enrollment, audit export, OAuth stub settings, adaptive views."""
import os

from flask import (Blueprint, Response, current_app, flash, redirect,
                   render_template, request, send_from_directory, session, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import db
from . import adaptive as ADAPT
from . import operations as OPS
from . import saas as SAAS
from .decorators import admin_required, manager_or_admin, role_required
from .i18n import LANGUAGES, set_lang
from .models import Course, Tenant, TenantSetting, User

saas_bp = Blueprint("saas", __name__)
student_only = role_required("student")

ALLOWED_LOGOS = {"png", "jpg", "jpeg", "webp", "svg"}


# ------------------------------------------------------------ i18n switch

@saas_bp.route("/lang/<code>")
def switch_lang(code):
    set_lang(code)
    nxt = request.referrer or url_for("main.index")
    # keep the redirect on-site
    if not nxt.startswith("/"):
        nxt = url_for("main.index")
    return redirect(nxt)


# ------------------------------------------------------------ public brand logo

@saas_bp.route("/brand/<path:filename>")
def brand_file(filename):
    """Serve tenant branding logos (public — shown in the navbar)."""
    directory = os.path.join(current_app.config["UPLOAD_DIR"], "branding")
    return send_from_directory(directory, filename)


# ------------------------------------------------------------ tenants (admin)

@saas_bp.route("/admin/tenants")
@manager_or_admin
def tenant_list():
    tenants = Tenant.query.order_by(Tenant.id).all()
    counts = {}
    for t in tenants:
        counts[t.id] = {
            "users": User.query.filter_by(tenant_id=t.id).count(),
        }
    return render_template("admin_tenants.html", tenants=tenants, counts=counts)


@saas_bp.route("/admin/tenants/new", methods=["GET", "POST"])
@manager_or_admin
def tenant_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower().replace(" ", "-")
        if not name or not slug:
            flash("Name and slug are required.", "error")
        elif Tenant.query.filter_by(slug=slug).first():
            flash("That slug is already taken.", "error")
        else:
            tenant = Tenant(name=name, slug=slug, active=False)
            db.session.add(tenant)
            db.session.flush()
            db.session.add(TenantSetting(tenant_id=tenant.id))
            db.session.commit()
            OPS.audit(current_user, "tenant.create", "tenant", tenant.id, name,
                      request.remote_addr or "")
            flash(f"Tenant “{name}” created.", "ok")
            return redirect(url_for("saas.tenant_list"))
    return render_template("admin_tenant_form.html")


@saas_bp.route("/admin/tenants/<int:tenant_id>/toggle", methods=["POST"])
@manager_or_admin
def tenant_toggle(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        return redirect(url_for("saas.tenant_list"))
    if tenant.slug == SAAS.DEFAULT_TENANT_SLUG:
        flash("The default tenant cannot be deactivated.", "error")
        return redirect(url_for("saas.tenant_list"))
    tenant.active = not tenant.active
    db.session.commit()
    OPS.audit(current_user, "tenant.toggle", "tenant", tenant.id,
              f"active={tenant.active}", request.remote_addr or "")
    flash(f"Tenant “{tenant.name}” {'activated' if tenant.active else 'deactivated'}.",
          "ok")
    return redirect(url_for("saas.tenant_list"))


# ------------------------------------------------------------ branding (admin)

@saas_bp.route("/admin/branding", methods=["GET", "POST"])
@manager_or_admin
def branding():
    tenant = SAAS.get_default_tenant()
    settings = (TenantSetting.query.filter_by(tenant_id=tenant.id).first()
                if tenant else None)
    if request.method == "POST" and tenant:
        if not settings:
            settings = TenantSetting(tenant_id=tenant.id)
            db.session.add(settings)
        settings.brand_name = request.form.get("brand_name", "").strip()[:160]
        settings.tagline = request.form.get("tagline", "").strip()[:300]
        primary = request.form.get("primary_color", "").strip()
        accent = request.form.get("accent_color", "").strip()
        settings.primary_color = primary if SAAS.is_valid_hex_color(primary) else ""
        settings.accent_color = accent if SAAS.is_valid_hex_color(accent) else ""
        logo = request.files.get("logo")
        if logo and logo.filename:
            ext = logo.filename.rsplit(".", 1)[-1].lower()
            if ext in ALLOWED_LOGOS:
                directory = os.path.join(current_app.config["UPLOAD_DIR"],
                                         "branding")
                os.makedirs(directory, exist_ok=True)
                fname = secure_filename(f"tenant-{tenant.id}-logo.{ext}")
                logo.save(os.path.join(directory, fname))
                settings.logo_file = fname
            else:
                flash("Logo must be png/jpg/webp/svg.", "error")
        if request.form.get("clear_logo"):
            settings.logo_file = ""
        db.session.commit()
        OPS.audit(current_user, "branding.update", "tenant", tenant.id, "",
                  request.remote_addr or "")
        flash("Branding saved.", "ok")
        return redirect(url_for("saas.branding"))
    return render_template("admin_branding.html", settings=settings,
                           brand=SAAS.get_brand())


# ------------------------------------------------------------ bulk enroll (§21.7a)

@saas_bp.route("/admin/bulk-enroll", methods=["GET", "POST"])
@manager_or_admin
def bulk_enroll():
    result = None
    if request.method == "POST":
        file = request.files.get("csv")
        if not file or not file.filename:
            flash("Choose a CSV file first.", "error")
        else:
            created_users, created_enrollments, errors = \
                SAAS.bulk_enroll_from_csv(file.stream)
            OPS.audit(current_user, "bulk_enroll", "enrollment", None,
                      f"users={created_users} enrollments={created_enrollments} "
                      f"errors={len(errors)}", request.remote_addr or "")
            result = {"users": created_users,
                      "enrollments": created_enrollments, "errors": errors}
    courses = Course.query.order_by(Course.title).all()
    return render_template("admin_bulk_enroll.html", courses=courses,
                           result=result)


# ------------------------------------------------------------ audit export (§21.7b)

@saas_bp.route("/admin/audit-logs/export.csv")
@manager_or_admin
def audit_export():
    csv_text = SAAS.audit_logs_csv(
        action=request.args.get("action", "").strip(),
        actor=request.args.get("actor", "").strip())
    OPS.audit(current_user, "audit.export", "audit_log", None, "",
              request.remote_addr or "")
    return Response(csv_text, mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=audit-logs.csv"})


# ------------------------------------------------------------ integrations (§21.7c)

@saas_bp.route("/admin/integrations", methods=["GET", "POST"])
@admin_required
def integrations():
    if request.method == "POST":
        existing = SAAS.get_oauth_settings()
        secret = request.form.get("google_client_secret", "").strip()
        SAAS.save_oauth_settings(
            request.form.get("google_client_id", "").strip(),
            secret or existing["google_client_secret"])  # blank = keep old
        OPS.audit(current_user, "oauth.settings", "integration", None, "",
                  request.remote_addr or "")
        flash("Google OAuth settings saved. (Login button stays "
              "“coming soon” until a full OAuth flow is implemented.)", "ok")
        return redirect(url_for("saas.integrations"))
    oauth = dict(SAAS.get_oauth_settings())
    oauth["google_client_secret"] = ""  # never echo the secret back
    return render_template("admin_integrations.html", oauth=oauth)


# ------------------------------------------------------------ adaptive views (§21.5)

@saas_bp.route("/learn/recommended")
@login_required
def recommended():
    recs = ADAPT.recommendations_for_student(current_user.id)
    return render_template("recommended.html", recs=recs)


@saas_bp.route("/admin/adaptive")
@manager_or_admin
def adaptive_admin():
    course_id = request.args.get("course_id", type=int)
    courses = Course.query.order_by(Course.title).all()
    aggregates = ADAPT.class_weak_topics(course_id) if course_id else []
    course = db.session.get(Course, course_id) if course_id else None
    return render_template("admin_adaptive.html", courses=courses,
                           aggregates=aggregates, course=course)
