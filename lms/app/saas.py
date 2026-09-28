"""Phase 12 §21.1/§21.2/§21.7 — multi-tenancy, white-labeling, enterprise tools.

Additive by design: every tenant_id column is nullable and NULL means
"the default Sayyed EdVantage tenant", so all existing rows and queries
behave exactly as before. tenant_scope() is the helper new/tenant-aware
code should use; legacy queries are untouched.
"""
import csv
import io
import re
import secrets

from flask import has_request_context, session
from sqlalchemy import or_

from . import db
from .models import AppSetting, AuditLog, Course, Enrollment, Tenant, TenantSetting, User

DEFAULT_TENANT_SLUG = "sayyed-edvantage"

# Brand defaults — must match the live Sayyed EdVantage look exactly.
DEFAULT_BRAND = {
    "brand_name": "Sayyed EdVantage",
    "tagline": "Empowering Students for Success",
    "primary_color": "",   # empty = theme default gold
    "accent_color": "",    # empty = theme default blue
    "logo_file": "",       # empty = built-in navbar brand
}


# ------------------------------------------------------------ tenancy

def get_default_tenant():
    tenant = Tenant.query.filter_by(slug=DEFAULT_TENANT_SLUG).first()
    return tenant


def get_current_tenant():
    """Request-scoped tenant; always falls back to the default tenant."""
    tenant = None
    if has_request_context():
        tid = session.get("tenant_id")
        if tid:
            tenant = db.session.get(Tenant, tid)
            if tenant and not tenant.active:
                tenant = None
    return tenant or get_default_tenant()


def tenant_scope(model):
    """Filter criterion: rows of the current tenant OR legacy NULL rows."""
    tenant = get_current_tenant()
    if tenant is None or tenant.slug == DEFAULT_TENANT_SLUG:
        # Default tenant owns every legacy NULL row: no filtering needed.
        return True
    return or_(model.tenant_id == tenant.id, model.tenant_id.is_(None))


def ensure_saas_defaults():
    """Seed the default tenant + its (empty = platform-default) settings."""
    try:
        tenant = Tenant.query.filter_by(slug=DEFAULT_TENANT_SLUG).first()
        if not tenant:
            tenant = Tenant(name="Sayyed EdVantage", slug=DEFAULT_TENANT_SLUG,
                            active=True)
            db.session.add(tenant)
            db.session.flush()
        if not TenantSetting.query.filter_by(tenant_id=tenant.id).first():
            db.session.add(TenantSetting(tenant_id=tenant.id))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ------------------------------------------------------------ branding

def get_brand():
    """Branding dict for templates. Empty settings => platform defaults."""
    brand = dict(DEFAULT_BRAND)
    tenant = get_current_tenant()
    if tenant:
        s = TenantSetting.query.filter_by(tenant_id=tenant.id).first()
        if s:
            if s.brand_name:
                brand["brand_name"] = s.brand_name
            if s.tagline:
                brand["tagline"] = s.tagline
            if s.primary_color:
                brand["primary_color"] = s.primary_color
            if s.accent_color:
                brand["accent_color"] = s.accent_color
            if s.logo_file:
                brand["logo_file"] = s.logo_file
    brand["is_custom"] = bool(
        tenant and tenant.slug != DEFAULT_TENANT_SLUG or
        any([brand["brand_name"] != DEFAULT_BRAND["brand_name"],
             brand["tagline"] != DEFAULT_BRAND["tagline"],
             brand["primary_color"], brand["accent_color"],
             brand["logo_file"]]))
    return brand


def is_valid_hex_color(value):
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", (value or "").strip()))


# ------------------------------------------------------------ bulk enroll (§21.7a)

def bulk_enroll_from_csv(file_stream):
    """Parse an uploaded CSV (name,email,course) and enroll.

    Returns (created_users, created_enrollments, errors[]) where errors
    are (row_number, message). Never raises on bad rows.
    """
    text = file_stream.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    created_users = 0
    created_enrollments = 0
    errors = []
    seen_emails = set()
    for n, row in enumerate(reader, start=2):  # 1 = header
        try:
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip().lower()
            course_ref = (row.get("course") or "").strip()
            if not name or not email or "@" not in email:
                errors.append((n, "name/email missing or invalid"))
                continue
            if email in seen_emails:
                errors.append((n, f"duplicate email in file: {email}"))
                continue
            seen_emails.add(email)
            if course_ref.isdigit():
                course = db.session.get(Course, int(course_ref))
            else:
                course = Course.query.filter_by(slug=course_ref).first()
            if not course:
                errors.append((n, f"unknown course: {course_ref}"))
                continue
            user = User.query.filter_by(email=email).first()
            temp_password = None
            if not user:
                temp_password = secrets.token_urlsafe(6)
                user = User(name=name, email=email, role="student")
                user.set_password(temp_password)
                db.session.add(user)
                db.session.flush()
                created_users += 1
            existing = Enrollment.query.filter_by(
                user_id=user.id, course_id=course.id).first()
            if existing:
                errors.append((n, f"already enrolled: {email}"))
                continue
            db.session.add(Enrollment(user_id=user.id, course_id=course.id,
                                      status=Enrollment.STATUS_ACTIVE,
                                      paid=False))
            created_enrollments += 1
            db.session.commit()
        except Exception as exc:  # never let one bad row kill the batch
            db.session.rollback()
            errors.append((n, f"error: {exc}"))
    return created_users, created_enrollments, errors


# ------------------------------------------------------------ audit CSV (§21.7b)

def audit_logs_csv(action="", actor=""):
    """CSV text of the (optionally filtered) audit log."""
    q = AuditLog.query
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if actor:
        q = q.filter(AuditLog.actor_email.ilike(f"%{actor}%"))
    rows = q.order_by(AuditLog.created_at.desc()).limit(2000).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "actor_email", "action",
                "target_type", "target_id", "detail", "ip"])
    for r in rows:
        w.writerow([r.id, r.created_at, r.actor_email, r.action,
                    r.target_type, r.target_id, r.detail, r.ip])
    return buf.getvalue()


# ------------------------------------------------------------ integrations (§21.7c)

OAUTH_KEYS = ("google_client_id", "google_client_secret")


def get_oauth_settings():
    return {k: AppSetting.get(k, "") for k in OAUTH_KEYS}


def save_oauth_settings(client_id, secret):
    for k, v in (("google_client_id", client_id or ""),
                 ("google_client_secret", secret or "")):
        row = db.session.get(AppSetting, k)
        if row:
            row.value = v
        else:
            db.session.add(AppSetting(key=k, value=v))
    db.session.commit()
