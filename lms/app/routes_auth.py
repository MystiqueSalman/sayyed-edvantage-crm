"""Auth: login / logout / student self-registration."""
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import login_user, logout_user, current_user

from . import db
from .models import User, ROLE_STUDENT, ROLES

auth_bp = Blueprint("auth", __name__)


def _landing_for(user):
    if user.role == "admin":
        return url_for("admin.dashboard")
    if user.role == "manager":
        return url_for("admin.dashboard")
    if user.role == "counsellor":  # Phase 4: counsellors land on the CRM
        return url_for("crm.leads")
    if user.role == "employer":  # Phase 7: employers land on their portal
        return url_for("career.employer_dashboard")
    if user.role == "faculty":
        return url_for("faculty.dashboard")
    # Phase 13: extended roles get a safe, always-200 landing.
    if user.role == "super_admin":
        return url_for("admin.dashboard")
    if user.role == "finance_officer":
        return url_for("ops.finance")
    if user.role == "placement_officer":
        return url_for("growth.jobs")
    if user.role == "content_manager":
        return url_for("main.catalog")
    # parent: no dedicated UI yet (parent-progress UI is a follow-up);
    # student dashboard is the safe default.
    return url_for("student.dashboard")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_landing_for(current_user))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            # Phase 13: MFA gate — after the password verifies, users with
            # TOTP enabled are held at /auth/mfa-verify instead of logging
            # in. Safe no-op when the MFA tables don't exist yet.
            try:
                from . import auth13 as _A13  # noqa: E402
                _mfa_redirect = _A13.mfa_gate(user)
            except Exception:
                _mfa_redirect = None
            if _mfa_redirect is not None:
                return _mfa_redirect
            login_user(user)
            # Phase 8: daily login points (once per Asia/Kolkata day)
            from . import gamification as G
            G.award_points(user.id, "daily_login", "day",
                           G.kolkata_today().isoformat())
            flash(f"Welcome back, {user.name}!", "success")
            nxt = request.args.get("next")
            return redirect(nxt or _landing_for(user))
        flash("Invalid email or password.", "danger")
    # Phase 13: the login template shows a Google button (enabled) or a
    # disabled "coming soon" note based on this flag.
    try:
        from . import auth13 as _A13  # noqa: E402
        _google_oauth_configured = _A13.google_oauth_configured()
    except Exception:
        _google_oauth_configured = False
    return render_template("login.html",
                           google_oauth_configured=_google_oauth_configured)


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(_landing_for(current_user))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Please fill all fields (password min 6 characters).", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
        else:
            user = User(name=name, email=email, role=ROLE_STUDENT,
                        phone=request.form.get("phone", "").strip()[:20])
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            try:
                from .growth import (REF_COOKIE, attribute_signup,
                                     get_or_create_referral_code)
                get_or_create_referral_code(user)  # every user gets a code
                ref_code = request.cookies.get(REF_COOKIE, "")
                ref = attribute_signup(user, ref_code) if ref_code else None
            except Exception:
                ref = None  # referrals must never break registration
            try:
                # Phase 4: referral-driven signups become CRM leads
                if ref is not None:
                    from .crm import referral_signup_lead
                    referral_signup_lead(
                        user, ref.referrer.name if ref.referrer else "")
                    db.session.commit()
            except Exception:
                db.session.rollback()  # CRM must never break registration
            login_user(user)
            try:
                from .emailer import send_welcome_email
                send_welcome_email(user)
            except Exception:
                pass  # email must never break registration
            flash("Account created — welcome to Sayyed EdVantage!", "success")
            return redirect(url_for("student.dashboard"))
    return render_template("register.html")
