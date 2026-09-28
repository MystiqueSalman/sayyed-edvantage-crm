"""Phase 13 — Auth & accounts routes (Stream 1).

One Blueprint (auth13_bp) holding everything Stream 1 owns:

  1. Password reset:   /auth/forgot-password  +  /auth/reset/<token>
  2. Email OTP login:  /auth/otp-login         (two steps)
  3. TOTP MFA:         /auth/mfa-setup | /auth/mfa-verify | /auth/mfa-disable
  4. Google OAuth:     /auth/google/login | /auth/google/callback
                       + admin settings page /admin/integrations/google

All routes use full explicit paths. Email flows reuse app/emailer's
SMTP gating (send_email_async returns False when unconfigured); the
OAuth settings reuse the AppSetting key/value infra from Phase 10.

Coordinator: register auth13_bp in app/__init__.py with the other
blueprints (snippet in the stream report).
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_required, login_user

from . import db
from .decorators import admin_required
from .emailer import send_email_async
from .models import AppSetting, ROLE_STUDENT, User
from .models13_auth import (EmailOTP, PasswordResetToken, UserSecurity13)

log = logging.getLogger(__name__)

auth13_bp = Blueprint("auth13", __name__)

# ------------------------------------------------------------------ tunables
RESET_TTL = timedelta(hours=1)
OTP_TTL = timedelta(minutes=10)
OTP_CODES_PER_HOUR = 5
OTP_MAX_ATTEMPTS = 5
BACKUP_CODE_COUNT = 10

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


# ------------------------------------------------------------------- helpers
def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def email_configured():
    """True when the Phase 2 email infra is enabled and usable."""
    try:
        from .models import EmailSettings
        s = EmailSettings.query.get(1)
        return bool(s and s.enabled and s.smtp_host and s.from_email)
    except Exception:
        return False


def google_oauth_configured():
    """True when an admin has saved a client id + secret and enabled OAuth."""
    try:
        enabled = AppSetting.get("GOOGLE_OAUTH_ENABLED", "0") == "1"
        cid = AppSetting.get("GOOGLE_CLIENT_ID", "")
        csecret = AppSetting.get("GOOGLE_CLIENT_SECRET", "")
        return enabled and bool(cid) and bool(csecret)
    except Exception:
        return False


def _base_url():
    return (current_app.config.get("APP_BASE_URL") or "").rstrip("/")


def _landing(user):
    from .routes_auth import _landing_for
    return _landing_for(user)


def _award_daily_login(user_id):
    try:
        from . import gamification as G
        G.award_points(user_id, "daily_login", "day",
                       G.kolkata_today().isoformat())
    except Exception:
        pass  # points must never break auth


def mfa_gate(user):
    """Phase 13: called after a password/OTP check passes.

    Returns a redirect response to /auth/mfa-verify when the user has
    TOTP enabled (stashing their id in the session), else None meaning
    "proceed with the normal login". Safe no-op when the MFA tables
    don't exist yet (mid-migration) or the blueprint isn't registered.
    """
    try:
        sec = UserSecurity13.query.filter_by(user_id=user.id).first()
    except Exception:
        return None
    if sec is not None and sec.mfa_enabled:
        session["mfa_pending_user_id"] = user.id
        flash("Enter the code from your authenticator app.", "info")
        try:
            return redirect(url_for("auth13.mfa_verify"))
        except Exception:
            session.pop("mfa_pending_user_id", None)
            return None
    return None


# ============================================================ 1. password reset
_RESET_EMAIL_SUBJECT = "Reset your Sayyed EdVantage password 🔐"


def _reset_email_html(user, reset_url):
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;
background:#0a1628;color:#eef3fb;padding:28px;border-radius:12px">
<h2 style="color:#d4af37;margin-top:0">Reset your password</h2>
<p>Hi {user.name},</p>
<p>Someone requested a password reset for your Sayyed EdVantage LMS
account. Click the button below — the link works once and expires in
1 hour.</p>
<p><a href="{reset_url}" style="display:inline-block;background:#d4af37;
color:#0a1628;padding:12px 24px;border-radius:8px;text-decoration:none;
font-weight:bold">Set a new password</a></p>
<p style="color:#9fb3d1;font-size:.85rem">If you didn't ask for this, just
ignore this email — your password stays unchanged.</p>
<p style="color:#9fb3d1;font-size:.85rem;margin-top:24px">Sayyed EdVantage —
Empowering Students for Success · Mumbai, India</p></div>"""


@auth13_bp.route("/auth/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = (User.query.filter_by(email=email).first()
                if email else None)
        if user is None or not user.is_active:
            flash("If an account exists with that email, a reset link has "
                  "been sent.", "info")
        elif not email_configured():
            log.warning("Password reset requested for %s but email is not "
                        "configured.", email)
            flash("Email is not configured — please ask your admin to set "
                  "it up before requesting a reset link.", "danger")
        else:
            # Invalidate any outstanding tokens, then issue one.
            (PasswordResetToken.query
             .filter_by(user_id=user.id, used=False)
             .update({"used": True}))
            token = secrets.token_urlsafe(32)
            db.session.add(PasswordResetToken(
                user_id=user.id, token_hash=_sha256(token),
                expires_at=datetime.utcnow() + RESET_TTL))
            db.session.commit()
            reset_url = (_base_url()
                         + url_for("auth13.reset_password", token=token))
            sent = send_email_async(user.email, _RESET_EMAIL_SUBJECT,
                                    _reset_email_html(user, reset_url))
            if not sent:
                # Config raced us — drop the token nobody can receive.
                (PasswordResetToken.query
                 .filter_by(user_id=user.id,
                            token_hash=_sha256(token))
                 .delete())
                db.session.commit()
                log.warning("Password reset requested for %s but email "
                            "delivery failed (unconfigured).", email)
                flash("Email is not configured — please ask your admin to "
                      "set it up before requesting a reset link.", "danger")
            else:
                flash("If an account exists with that email, a reset link "
                      "has been sent.", "info")
        return redirect(url_for("auth13.forgot_password"))
    return render_template("p13_forgot_password.html")


def _valid_reset_token(token):
    if not token:
        return None
    row = PasswordResetToken.query.filter_by(
        token_hash=_sha256(token)).first()
    if row is None or row.used:
        return None
    if row.expires_at < datetime.utcnow():
        return None
    # constant-time compare, belt & braces next to the hash lookup
    if not hmac.compare_digest(row.token_hash, _sha256(token)):
        return None
    return row


@auth13_bp.route("/auth/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    row = _valid_reset_token(token)
    if row is None:
        flash("This reset link is invalid or has expired. Please request a "
              "new one.", "danger")
        return redirect(url_for("auth13.forgot_password"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        pw2 = request.form.get("confirm", "")
        if len(pw) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif pw != pw2:
            flash("Passwords do not match.", "danger")
        else:
            user = db.session.get(User, row.user_id)
            row.used = True
            user.set_password(pw)
            db.session.commit()
            flash("Your password has been reset — please sign in.",
                  "success")
            return redirect(url_for("auth.login"))
    return render_template("p13_reset_password.html", token=token)


# ============================================================ 2. email OTP login
_OTP_EMAIL_SUBJECT = "Your Sayyed EdVantage login code 🔑"


def _otp_email_html(user, code):
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;
background:#0a1628;color:#eef3fb;padding:28px;border-radius:12px">
<h2 style="color:#d4af37;margin-top:0">Your login code</h2>
<p>Hi {user.name},</p>
<p>Use this 6-digit code to sign in. It expires in 10 minutes and works
only once:</p>
<p style="font-size:2rem;letter-spacing:.4rem;color:#d4af37;font-weight:bold">
{code}</p>
<p style="color:#9fb3d1;font-size:.85rem">If you didn't request this, just
ignore this email.</p>
<p style="color:#9fb3d1;font-size:.85rem;margin-top:24px">Sayyed EdVantage —
Empowering Students for Success · Mumbai, India</p></div>"""


@auth13_bp.route("/auth/otp-login", methods=["GET", "POST"])
def otp_login():
    if request.method == "POST":
        stage = request.form.get("stage", "email")
        email = request.form.get("email", "").strip().lower()
        if stage == "email":
            user = User.query.filter_by(email=email).first() if email else None
            if user is None or not user.is_active:
                flash("No active account is registered with this email.",
                      "danger")
                return redirect(url_for("auth13.otp_login"))
            if not email_configured():
                log.warning("OTP login requested for %s but email is not "
                            "configured.", email)
                flash("Email is not configured — please ask your admin to "
                      "set it up.", "danger")
                return redirect(url_for("auth13.otp_login"))
            since = datetime.utcnow() - timedelta(hours=1)
            recent = (EmailOTP.query
                      .filter(EmailOTP.email == email,
                              EmailOTP.created_at >= since)
                      .count())
            if recent >= OTP_CODES_PER_HOUR:
                flash("Too many codes requested — please try again in an "
                      "hour.", "danger")
                return redirect(url_for("auth13.otp_login"))
            code = f"{secrets.randbelow(1_000_000):06d}"
            db.session.add(EmailOTP(email=email, code_hash=_sha256(code),
                                    expires_at=datetime.utcnow() + OTP_TTL))
            db.session.commit()
            sent = send_email_async(email, _OTP_EMAIL_SUBJECT,
                                    _otp_email_html(user, code))
            if not sent:
                (EmailOTP.query
                 .filter_by(email=email, code_hash=_sha256(code),
                            consumed=False)
                 .delete())
                db.session.commit()
                log.warning("OTP login requested for %s but email delivery "
                            "failed (unconfigured).", email)
                flash("Email is not configured — please ask your admin to "
                      "set it up.", "danger")
                return redirect(url_for("auth13.otp_login"))
            session["otp_email"] = email
            flash("A 6-digit code has been emailed to you — it expires in "
                  "10 minutes.", "info")
            return render_template("p13_otp_login.html", step="code",
                                   email=email)
        # stage == "code"
        email = email or session.get("otp_email", "")
        code = request.form.get("code", "").strip()
        row = (EmailOTP.query
               .filter_by(email=email, consumed=False)
               .order_by(EmailOTP.id.desc()).first())
        if row is None or row.expires_at < datetime.utcnow():
            flash("This code is invalid or has expired — request a new "
                  "one.", "danger")
            return render_template("p13_otp_login.html", step="code",
                                   email=email)
        if row.attempts >= OTP_MAX_ATTEMPTS:
            row.consumed = True
            db.session.commit()
            flash("Too many wrong attempts — this code is now invalid. "
                  "Request a new one.", "danger")
            return render_template("p13_otp_login.html", step="code",
                                   email=email)
        if not hmac.compare_digest(row.code_hash, _sha256(code)):
            row.attempts = (row.attempts or 0) + 1
            db.session.commit()
            left = OTP_MAX_ATTEMPTS - row.attempts
            flash(f"Wrong code. {left} attempt(s) left.", "danger")
            return render_template("p13_otp_login.html", step="code",
                                   email=email)
        row.consumed = True
        db.session.commit()
        user = User.query.filter_by(email=email).first()
        if user is None or not user.is_active:
            flash("No active account is registered with this email.",
                  "danger")
            return redirect(url_for("auth13.otp_login"))
        session.pop("otp_email", None)
        gate = mfa_gate(user)
        if gate is not None:
            return gate
        login_user(user)
        _award_daily_login(user.id)
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(_landing(user))
    step = "code" if session.get("otp_email") else "email"
    return render_template("p13_otp_login.html", step=step,
                           email=session.get("otp_email", ""))


# ============================================================ 3. TOTP MFA
def _render_mfa_setup(secret):
    """Show the secret + provisioning URI; QR only if `qrcode` is present."""
    import pyotp
    uri = (pyotp.totp.TOTP(secret)
           .provisioning_uri(name=current_user.email,
                             issuer_name="Sayyed EdVantage LMS"))
    qr_data_uri = None
    try:
        import base64
        import io

        import qrcode
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_data_uri = ("data:image/png;base64,"
                       + base64.b64encode(buf.getvalue()).decode())
    except Exception:
        qr_data_uri = None  # qrcode not installed — manual-key path instead
    return render_template("p13_mfa_setup.html", secret=secret,
                           otpauth_uri=uri, qr_data_uri=qr_data_uri)


@auth13_bp.route("/auth/mfa-setup", methods=["GET", "POST"])
@login_required
def mfa_setup():
    import pyotp
    existing = UserSecurity13.query.filter_by(
        user_id=current_user.id).first()
    if existing is not None and existing.mfa_enabled:
        flash("Two-factor authentication is already enabled.", "info")
        return redirect(url_for("auth13.mfa_disable"))
    if request.method == "POST":
        secret = session.get("mfa_enroll_secret")
        code = request.form.get("code", "").strip().replace(" ", "")
        if not secret:
            flash("Your setup session expired — please start again.",
                  "danger")
            return redirect(url_for("auth13.mfa_setup"))
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            flash("That code didn't match — check the authenticator app "
                  "and try again.", "danger")
            return _render_mfa_setup(secret)
        backup = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}"
                  for _ in range(BACKUP_CODE_COUNT)]
        row = existing or UserSecurity13(user_id=current_user.id,
                                         totp_secret="")
        # Security hardening: TOTP secrets are encrypted at rest (Fernet key
        # derived from SECRET_KEY) — never store plaintext.
        from app.totp_crypto import encrypt_totp_secret as _enc_totp  # noqa: E402
        row.totp_secret = _enc_totp(secret)
        row.mfa_enabled = True
        row.backup_codes = [_sha256(c) for c in backup]
        db.session.add(row)
        db.session.commit()
        session.pop("mfa_enroll_secret", None)
        # Shown once — afterwards only the hashes remain in the DB.
        return render_template("p13_mfa_backup_codes.html", codes=backup)
    secret = session.get("mfa_enroll_secret")
    if not secret:
        secret = pyotp.random_base32()
        session["mfa_enroll_secret"] = secret
    return _render_mfa_setup(secret)


@auth13_bp.route("/auth/mfa-verify", methods=["GET", "POST"])
def mfa_verify():
    user_id = session.get("mfa_pending_user_id")
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        flash("Please sign in first.", "danger")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        import pyotp
        code = request.form.get("code", "").strip().replace(" ", "")
        sec = UserSecurity13.query.filter_by(user_id=user.id).first()
        ok = False
        if sec is not None and sec.mfa_enabled:
            from app.totp_crypto import decrypt_totp_secret as _dec_totp  # noqa: E402
            if pyotp.TOTP(_dec_totp(sec.totp_secret)).verify(code, valid_window=1):
                ok = True
            else:
                # Single-use backup codes (stored as hashes).
                hashes = list(sec.backup_codes or [])
                digest = _sha256(code)
                if any(hmac.compare_digest(h, digest) for h in hashes):
                    hashes.remove(digest)
                    sec.backup_codes = hashes  # new list => dirty => saved
                    db.session.commit()
                    ok = True
        if ok:
            session.pop("mfa_pending_user_id", None)
            login_user(user)
            _award_daily_login(user.id)
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(_landing(user))
        flash("That code didn't work — try again.", "danger")
    return render_template("p13_mfa_verify.html")


@auth13_bp.route("/auth/mfa-disable", methods=["GET", "POST"])
@login_required
def mfa_disable():
    sec = UserSecurity13.query.filter_by(user_id=current_user.id).first()
    if sec is None or not sec.mfa_enabled:
        flash("Two-factor authentication is not enabled.", "info")
        return redirect(url_for("auth13.mfa_setup"))
    if request.method == "POST":
        if current_user.check_password(request.form.get("password", "")):
            db.session.delete(sec)
            db.session.commit()
            flash("Two-factor authentication has been disabled.",
                  "success")
            return redirect(_landing(current_user))
        flash("Incorrect password.", "danger")
    return render_template("p13_mfa_disable.html")


# ============================================================ 4. Google OAuth
def _google_redirect_uri():
    return url_for("auth13.google_callback", _external=True)


@auth13_bp.route("/auth/google/login")
def google_login():
    if not google_oauth_configured():
        flash("Google login is coming soon — admin setup required.", "info")
        return redirect(url_for("auth.login"))
    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    params = {
        "client_id": AppSetting.get("GOOGLE_CLIENT_ID", ""),
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@auth13_bp.route("/auth/google/callback")
def google_callback():
    if not google_oauth_configured():
        flash("Google login is coming soon — admin setup required.", "info")
        return redirect(url_for("auth.login"))
    state = session.pop("google_oauth_state", None)
    if not state or request.args.get("state") != state:
        flash("Google sign-in failed (bad request). Please try again.",
              "danger")
        return redirect(url_for("auth.login"))
    code = request.args.get("code", "")
    if not code:
        flash("Google sign-in was cancelled.", "info")
        return redirect(url_for("auth.login"))
    try:
        token_r = requests.post(
            GOOGLE_TOKEN_URL,
            data={"client_id": AppSetting.get("GOOGLE_CLIENT_ID", ""),
                  "client_secret": AppSetting.get("GOOGLE_CLIENT_SECRET", ""),
                  "code": code,
                  "grant_type": "authorization_code",
                  "redirect_uri": _google_redirect_uri()},
            timeout=15)
        token_r.raise_for_status()
        access = token_r.json().get("access_token")
        if not access:
            raise ValueError("no access token in response")
        ui_r = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"}, timeout=15)
        ui_r.raise_for_status()
        info = ui_r.json()
        email = (info.get("email") or "").strip().lower()
        if not email or not info.get("email_verified"):
            raise ValueError("Google email not verified")
    except Exception as exc:  # noqa: BLE001 - surfaced as a flash message
        log.warning("Google OAuth failed: %s", exc)
        flash("Google sign-in failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if user is None:
        # Find-or-create: new Google users become students.
        user = User(name=(info.get("name") or email.split("@")[0])[:120],
                    email=email, role=ROLE_STUDENT)
        user.set_password(secrets.token_urlsafe(32))  # unguessable: OAuth only
        db.session.add(user)
        db.session.commit()
        try:
            from .growth import get_or_create_referral_code
            get_or_create_referral_code(user)  # referral-safe like register()
        except Exception:
            pass
        try:
            from .emailer import send_welcome_email
            send_welcome_email(user)
        except Exception:
            pass  # email must never break OAuth signup
    elif not user.is_active:
        flash("This account is deactivated — please contact support.",
              "danger")
        return redirect(url_for("auth.login"))

    gate = mfa_gate(user)
    if gate is not None:
        return gate
    login_user(user)
    _award_daily_login(user.id)
    flash(f"Welcome, {user.name}!", "success")
    return redirect(_landing(user))


@auth13_bp.route("/admin/integrations/google", methods=["GET", "POST"])
@admin_required
def oauth_settings():
    """Admin page to store the Google OAuth client credentials (AppSetting)."""
    if request.method == "POST":
        AppSetting.set("GOOGLE_CLIENT_ID",
                       request.form.get("client_id", "").strip())
        secret = request.form.get("client_secret", "").strip()
        if secret:  # blank => keep the currently saved secret
            AppSetting.set("GOOGLE_CLIENT_SECRET", secret)
        AppSetting.set("GOOGLE_OAUTH_ENABLED",
                       "1" if request.form.get("enabled") else "0")
        flash("Google OAuth settings saved.", "success")
        return redirect(url_for("auth13.oauth_settings"))
    return render_template(
        "p13_oauth_settings.html",
        client_id=AppSetting.get("GOOGLE_CLIENT_ID", ""),
        secret_set=bool(AppSetting.get("GOOGLE_CLIENT_SECRET", "")),
        enabled=AppSetting.get("GOOGLE_OAUTH_ENABLED", "0") == "1",
        configured=google_oauth_configured())
