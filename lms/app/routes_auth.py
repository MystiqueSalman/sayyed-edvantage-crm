"""Auth: login / logout / student self-registration."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
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
    if user.role == "faculty":
        return url_for("faculty.dashboard")
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
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            nxt = request.args.get("next")
            return redirect(nxt or _landing_for(user))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


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
