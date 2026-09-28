"""Phase 13 — Auth & accounts (Stream 1, end-to-end).

Runs in-process with Flask's test client against a FRESH DB (same
SQLITE_PATH as the other suites): migrations run via `flask db upgrade`
in run_suite.sh, then this file creates the p13_* tables with
db.create_all() (the coordinator's combined Alembic revision will cover
them in production) and registers auth13_bp directly.

Every app-context block re-fetches its rows (never reuse ORM instances
across blocks — the session closes between them).

Coverage: password reset (issue / redeem / expired / reused / tampered /
SMTP-unconfigured), email-OTP login (issue / verify / expired /
attempt-cap / rate-limit / unconfigured), TOTP MFA (setup / login with
code / backup code / wrong code / disable), Google OAuth (mocked token +
userinfo: new-user create / existing-user match / bad state /
unconfigured "coming soon"), extended roles + permission matrix,
ParentLink13 links, admin user-edit role selector.

All email sending and all Google HTTP are mocked.
"""
import os
import re
import sys
from datetime import datetime, timedelta
from html import unescape as _unescape
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app import operations as OPS  # noqa: E402
import app.auth13 as A13  # noqa: E402
from app.models import (AppSetting, EmailSettings, RolePermission,
                        User)  # noqa: E402
from app.models13_auth import (EmailOTP, ParentLink13, PasswordResetToken,
                               UserSecurity13)  # noqa: E402
from app.roles13 import (EXTENDED_ROLES, ROLE_CONTENT_MANAGER,
                         ROLE_FINANCE_OFFICER, ROLE_PARENT,
                         ROLE_PLACEMENT_OFFICER, ROLE_SUPER_ADMIN)  # noqa: E402

app = create_app()
if "auth13" not in app.blueprints:  # create_app() now registers all Phase 13 blueprints
    app.register_blueprint(A13.auth13_bp)
app.config["SERVER_NAME"] = "localhost"  # stable url_for(_external=True)
passed, failed, notes = 0, 0, []


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        notes.append(name)
        print(f"  FAIL {name} {detail}")


def ctx():
    return app.app_context()


def make_user(email, name="Test User", password="secret123", role="student"):
    with ctx():
        u = User(name=name, email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u.id


def logged_in(client):
    with client.session_transaction() as s:
        return bool(s.get("_user_id"))


def page_text(response):
    """Response body with HTML entities decoded (Jinja escapes quotes)."""
    return _unescape(response.get_data(as_text=True))


def new_client():
    return app.test_client()


# ------------------------------------------------------------------ fixtures
with ctx():
    db.create_all()  # p13_* tables (Alembic revision comes from coordinator)
    OPS.ensure_permission_defaults()

sent_emails = []  # (to, subject, html)


def fake_send(to_email, subject, html_body):
    sent_emails.append((to_email, subject, html_body))
    return True


A13.send_email_async = fake_send  # mock all email sending

admin_id = make_user("admin13@x.com", "Admin", "adminpass", role="admin")
reset_uid = make_user("reset13@x.com", "Reset User")
otp_uid = make_user("otp13@x.com", "OTP User")
otp2_uid = make_user("otp2_13@x.com", "OTP User 2")
mfa_uid = make_user("mfa13@x.com", "MFA User")


def fresh_reset_token(user_id, expired=False):
    import hashlib
    import secrets as _s
    with ctx():
        tok = _s.token_urlsafe(32)
        db.session.add(PasswordResetToken(
            user_id=user_id,
            token_hash=hashlib.sha256(tok.encode()).hexdigest(),
            expires_at=(datetime.utcnow() - timedelta(minutes=1)
                        if expired else datetime.utcnow() + timedelta(hours=1))))
        db.session.commit()
        return tok


def token_count(user_id):
    with ctx():
        return (PasswordResetToken.query
                .filter_by(user_id=user_id, used=False).count())


# ============================================================ 1. password reset
print("== password reset ==")
c = new_client()

r = c.post("/auth/forgot-password", data={"email": "nobody@x.com"},
           follow_redirects=True)
check("unknown email: no token created", token_count(reset_uid) == 0)
check("unknown email: generic notice",
      "reset link has been sent" in page_text(r))

# SMTP unconfigured (no EmailSettings row on the fresh DB)
r = c.post("/auth/forgot-password", data={"email": "reset13@x.com"},
           follow_redirects=True)
check("unconfigured email: clear admin notice",
      "Email is not configured" in r.get_data(as_text=True))
check("unconfigured email: no token minted", token_count(reset_uid) == 0)

with ctx():
    db.session.add(EmailSettings(id=1, smtp_host="smtp.example.com",
                                 from_email="noreply@example.com",
                                 enabled=True))
    db.session.commit()

r = c.post("/auth/forgot-password", data={"email": "reset13@x.com"})
check("token minted for known email", token_count(reset_uid) == 1)
check("reset email captured", len(sent_emails) == 1
      and sent_emails[0][0] == "reset13@x.com")
m = re.search(r"/auth/reset/([A-Za-z0-9_\-]+)", sent_emails[0][2])
check("reset link in email", m is not None)
token = m.group(1) if m else ""

r = c.get(f"/auth/reset/{token}")
check("valid token page renders", r.status_code == 200
      and "Choose a new password" in r.get_data(as_text=True))

r = c.post(f"/auth/reset/{token}",
           data={"password": "short", "confirm": "short"})
check("short password rejected",
      "at least 6 characters" in r.get_data(as_text=True))
with ctx():
    row = PasswordResetToken.query.filter_by(
        token_hash=A13._sha256(token)).first()
check("rejected token still unused", row is not None and not row.used)

r = c.post(f"/auth/reset/{token}",
           data={"password": "brandnewpass", "confirm": "brandnewpass"})
check("redeem redirects to login", r.status_code == 302
      and r.headers["Location"].endswith("/login"))
with ctx():
    u = db.session.get(User, reset_uid)
    row = PasswordResetToken.query.filter_by(
        token_hash=A13._sha256(token)).first()
check("password actually changed", u.check_password("brandnewpass"))
check("token marked used", row.used)

r = c.post(f"/auth/reset/{token}",
           data={"password": "anotherpass", "confirm": "anotherpass"},
           follow_redirects=False)
check("reused token rejected",
      r.status_code == 302 and "/auth/forgot-password" in r.headers["Location"])
with ctx():
    u = db.session.get(User, reset_uid)
check("reuse did not change password", u.check_password("brandnewpass"))

old = fresh_reset_token(reset_uid, expired=True)
r = c.get(f"/auth/reset/{old}")
check("expired token GET rejected",
      r.status_code == 302 and "/auth/forgot-password" in r.headers["Location"])
r = c.post(f"/auth/reset/{old}",
           data={"password": "x" * 8, "confirm": "x" * 8})
check("expired token POST rejected",
      r.status_code == 302 and "/auth/forgot-password" in r.headers["Location"])
r = c.get("/auth/reset/" + "A" * 43)
check("tampered token rejected",
      r.status_code == 302 and "/auth/forgot-password" in r.headers["Location"])

# second request invalidates the first outstanding token
t1 = fresh_reset_token(reset_uid)
c.post("/auth/forgot-password", data={"email": "reset13@x.com"})
with ctx():
    old_row = PasswordResetToken.query.filter_by(
        token_hash=A13._sha256(t1)).first()
check("re-request invalidates old token", old_row.used)
check("exactly one live token after re-request", token_count(reset_uid) == 1)

# ============================================================ 2. email OTP login
print("== email OTP login ==")
c2 = new_client()

r = c2.post("/auth/otp-login",
            data={"stage": "email", "email": "ghost@x.com"},
            follow_redirects=True)
check("OTP step1: unknown email rejected",
      "No active account" in r.get_data(as_text=True))

n0 = len(sent_emails)
r = c2.post("/auth/otp-login",
            data={"stage": "email", "email": "otp13@x.com"})
check("OTP step1: code emailed", len(sent_emails) == n0 + 1)
m = re.search(r"font-size:2rem[^>]*>\s*(\d{6})", sent_emails[-1][2])
check("6-digit code in email", m is not None)
code = m.group(1) if m else ""
with c2.session_transaction() as s:
    check("OTP email stashed in session", s.get("otp_email") == "otp13@x.com")

wrong = "000000" if code != "000000" else "111111"
r = c2.post("/auth/otp-login",
            data={"stage": "code", "email": "otp13@x.com", "code": wrong})
check("wrong code rejected",
      "Wrong code" in r.get_data(as_text=True) and not logged_in(c2))
with ctx():
    row = (EmailOTP.query.filter_by(email="otp13@x.com", consumed=False)
           .order_by(EmailOTP.id.desc()).first())
check("attempt counter incremented", row.attempts == 1)

for _ in range(4):
    c2.post("/auth/otp-login",
            data={"stage": "code", "email": "otp13@x.com", "code": wrong})
r = c2.post("/auth/otp-login",
            data={"stage": "code", "email": "otp13@x.com", "code": wrong})
check("5 wrong attempts invalidate the code",
      "Too many wrong attempts" in r.get_data(as_text=True))
r = c2.post("/auth/otp-login",
            data={"stage": "code", "email": "otp13@x.com", "code": code})
check("invalidated code cannot be used",
      "invalid or has expired" in r.get_data(as_text=True)
      and not logged_in(c2))

# expired code
with ctx():
    import hashlib
    exp_code = "424242"
    db.session.add(EmailOTP(email="otp13@x.com",
                            code_hash=hashlib.sha256(
                                exp_code.encode()).hexdigest(),
                            expires_at=datetime.utcnow() - timedelta(minutes=1)))
    db.session.commit()
r = c2.post("/auth/otp-login",
            data={"stage": "code", "email": "otp13@x.com", "code": exp_code})
check("expired code rejected",
      "invalid or has expired" in r.get_data(as_text=True))

# happy path
c2.post("/auth/otp-login", data={"stage": "email", "email": "otp13@x.com"})
m = re.search(r"font-size:2rem[^>]*>\s*(\d{6})", sent_emails[-1][2])
code = m.group(1)
r = c2.post("/auth/otp-login",
            data={"stage": "code", "email": "otp13@x.com", "code": code},
            follow_redirects=True)
check("correct code logs the user in",
      logged_in(c2) and "Logout" in r.get_data(as_text=True))
with ctx():
    row = (EmailOTP.query.filter_by(email="otp13@x.com")
           .order_by(EmailOTP.id.desc()).first())
check("used code marked consumed", row.consumed)

# rate limit: 5 codes/hour per email
c3 = new_client()
for i in range(5):
    r = c3.post("/auth/otp-login",
                data={"stage": "email", "email": "otp2_13@x.com"})
check("5 codes in an hour allowed", r.status_code == 200)
r = c3.post("/auth/otp-login", data={"stage": "email",
                                     "email": "otp2_13@x.com"},
            follow_redirects=True)
check("6th code in an hour rate-limited",
      "Too many codes requested" in r.get_data(as_text=True))
with ctx():
    n = EmailOTP.query.filter_by(email="otp2_13@x.com").count()
check("no extra code row minted", n == 5)

# OTP when SMTP unconfigured
with ctx():
    db.session.delete(EmailSettings.query.get(1))
    db.session.commit()
r = c3.post("/auth/otp-login", data={"stage": "email",
                                     "email": "otp2_13@x.com"},
            follow_redirects=True)
check("OTP unconfigured: clear admin notice",
      "Email is not configured" in r.get_data(as_text=True))
with ctx():
    db.session.add(EmailSettings(id=1, smtp_host="smtp.example.com",
                                 from_email="noreply@example.com",
                                 enabled=True))
    db.session.commit()

# ============================================================ 3. TOTP MFA
print("== TOTP MFA ==")
import pyotp  # noqa: E402

c4 = new_client()
r = c4.post("/login", data={"email": "mfa13@x.com", "password": "secret123"})
check("password login works without MFA (hook is a no-op)",
      logged_in(c4))

r = c4.get("/auth/mfa-setup")
check("mfa-setup page renders", r.status_code == 200
      and "authenticator" in r.get_data(as_text=True).lower())
check("manual key shown (qrcode lib not installed)",
      "Enter a setup key" in r.get_data(as_text=True))
with c4.session_transaction() as s:
    secret = s.get("mfa_enroll_secret")
check("enroll secret stashed in session", bool(secret))

r = c4.post("/auth/mfa-setup", data={"code": "000000"})
check("wrong setup code rejected",
      "didn't match" in page_text(r))
with ctx():
    check("MFA not enabled after wrong code",
          UserSecurity13.query.filter_by(user_id=mfa_uid).first() is None)

good = pyotp.TOTP(secret).now()
r = c4.post("/auth/mfa-setup", data={"code": good})
body = r.get_data(as_text=True)
codes = re.findall(r"([0-9a-f]{6}-[0-9a-f]{6})", body)
check("correct code enables MFA + shows 10 backup codes",
      len(codes) == 10 and "only time" in body)
with ctx():
    sec = UserSecurity13.query.filter_by(user_id=mfa_uid).first()
check("MFA row enabled with hashed codes",
      sec is not None and sec.mfa_enabled
      and len(sec.backup_codes or []) == 10
      and all(len(h) == 64 for h in sec.backup_codes))

c4.get("/logout")
r = c4.post("/login", data={"email": "mfa13@x.com", "password": "secret123"},
            follow_redirects=False)
check("login POST holds at mfa-verify when MFA enabled",
      r.status_code == 302 and r.headers["Location"].endswith("/auth/mfa-verify"))
check("user NOT logged in yet", not logged_in(c4))
with c4.session_transaction() as s:
    check("pending user id stashed", s.get("mfa_pending_user_id") == mfa_uid)

r = c4.get("/auth/mfa-verify")
check("mfa-verify page renders", r.status_code == 200)

r = c4.post("/auth/mfa-verify", data={"code": "000000"})
check("wrong TOTP rejected",
      "didn't work" in page_text(r) and not logged_in(c4))

r = c4.post("/auth/mfa-verify", data={"code": pyotp.TOTP(secret).now()},
            follow_redirects=True)
check("correct TOTP completes login",
      logged_in(c4) and "Logout" in r.get_data(as_text=True))

# backup code: single use
c4.get("/logout")
c4.post("/login", data={"email": "mfa13@x.com", "password": "secret123"})
backup = codes[0]
r = c4.post("/auth/mfa-verify", data={"code": backup},
            follow_redirects=True)
check("backup code logs in", logged_in(c4))
with ctx():
    sec = UserSecurity13.query.filter_by(user_id=mfa_uid).first()
check("backup code consumed (9 left)", len(sec.backup_codes) == 9)

c4.get("/logout")
c4.post("/login", data={"email": "mfa13@x.com", "password": "secret123"})
r = c4.post("/auth/mfa-verify", data={"code": backup})
check("used backup code rejected",
      "didn't work" in page_text(r) and not logged_in(c4))

# disable: needs password confirm
c4.post("/auth/mfa-verify", data={"code": pyotp.TOTP(secret).now()})
r = c4.get("/auth/mfa-disable")
check("mfa-disable page renders", r.status_code == 200)
r = c4.post("/auth/mfa-disable", data={"password": "wrongpass"},
            follow_redirects=True)
check("disable with wrong password refused",
      "Incorrect password" in r.get_data(as_text=True))
with ctx():
    check("MFA still enabled",
          UserSecurity13.query.filter_by(user_id=mfa_uid).first()
          is not None)
r = c4.post("/auth/mfa-disable", data={"password": "secret123"},
            follow_redirects=True)
check("disable with correct password",
      "disabled" in r.get_data(as_text=True))
with ctx():
    check("MFA row removed",
          UserSecurity13.query.filter_by(user_id=mfa_uid).first() is None)
c4.get("/logout")
r = c4.post("/login", data={"email": "mfa13@x.com", "password": "secret123"},
            follow_redirects=True)
check("login needs no MFA after disable", logged_in(c4))

# ============================================================ 4. Google OAuth
print("== Google OAuth ==")
c5 = new_client()
with ctx():
    _gcfg0 = A13.google_oauth_configured()
check("google_oauth_configured() False when unset", _gcfg0 is False)
r = c5.get("/auth/google/login", follow_redirects=True)
check("unconfigured google/login shows coming soon",
      "coming soon" in r.get_data(as_text=True).lower())

with ctx():
    AppSetting.set("GOOGLE_CLIENT_ID", "test-client-id")
    AppSetting.set("GOOGLE_CLIENT_SECRET", "test-client-secret")
    AppSetting.set("GOOGLE_OAUTH_ENABLED", "1")
    _gcfg = A13.google_oauth_configured()
check("google_oauth_configured() True when set", _gcfg is True)

r = c5.get("/auth/google/login", follow_redirects=False)
check("configured google/login redirects to Google",
      r.status_code == 302
      and r.headers["Location"].startswith(A13.GOOGLE_AUTH_URL)
      and "client_id=test-client-id" in r.headers["Location"])
with c5.session_transaction() as s:
    state = s.get("google_oauth_state")
check("oauth state stashed", bool(state))


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def google_ok(post_payload, get_payload):
    return (mock.patch.object(A13.requests, "post",
                             return_value=_Resp(post_payload)),
            mock.patch.object(A13.requests, "get",
                              return_value=_Resp(get_payload)))


ginfo = {"email": "googleuser13@example.com", "email_verified": True,
         "name": "Google User"}
with c5.session_transaction() as s:
    s["google_oauth_state"] = "state-1"
with google_ok({"access_token": "tok-1"}, ginfo)[0], \
        google_ok({"access_token": "tok-1"}, ginfo)[1]:
    r = c5.get("/auth/google/callback?code=authcode&state=state-1",
               follow_redirects=True)
check("google callback creates + logs in new user",
      logged_in(c5) and "Logout" in r.get_data(as_text=True))
with ctx():
    gu = User.query.filter_by(email="googleuser13@example.com").first()
check("new user is a student",
      gu is not None and gu.role == "student" and gu.name == "Google User")

c5.get("/logout")
with ctx():
    n_before = User.query.filter_by(
        email="googleuser13@example.com").count()
with c5.session_transaction() as s:
    s["google_oauth_state"] = "state-2"
with google_ok({"access_token": "tok-2"}, ginfo)[0], \
        google_ok({"access_token": "tok-2"}, ginfo)[1]:
    r = c5.get("/auth/google/callback?code=authcode2&state=state-2")
with ctx():
    n_after = User.query.filter_by(
        email="googleuser13@example.com").count()
check("existing user matched by email (no duplicate)",
      n_before == 1 and n_after == 1 and logged_in(c5))

c5.get("/logout")
with c5.session_transaction() as s:
    s["google_oauth_state"] = "real-state"
with google_ok({"access_token": "tok-3"}, ginfo)[0], \
        google_ok({"access_token": "tok-3"}, ginfo)[1]:
    r = c5.get("/auth/google/callback?code=authcode3&state=wrong-state",
               follow_redirects=True)
check("state mismatch rejected",
      "bad request" in r.get_data(as_text=True) and not logged_in(c5))

# admin oauth settings page
ca = new_client()
ca.post("/login", data={"email": "admin13@x.com", "password": "adminpass"})
r = ca.get("/admin/integrations/google")
check("admin oauth settings page renders", r.status_code == 200
      and "Client ID" in r.get_data(as_text=True))
ca.post("/admin/integrations/google",
        data={"client_id": "cid-2", "client_secret": "csec-2",
              "enabled": "on"})
with ctx():
    check("settings saved",
          AppSetting.get("GOOGLE_CLIENT_ID") == "cid-2"
          and AppSetting.get("GOOGLE_CLIENT_SECRET") == "csec-2"
          and AppSetting.get("GOOGLE_OAUTH_ENABLED") == "1")
ca.post("/admin/integrations/google",
        data={"client_id": "cid-2", "client_secret": ""})  # blank keeps secret
with ctx():
    check("blank secret keeps saved one",
          AppSetting.get("GOOGLE_CLIENT_SECRET") == "csec-2"
          and AppSetting.get("GOOGLE_OAUTH_ENABLED") == "0")

# ============================================================ 5. roles & matrix
print("== roles & permission matrix ==")
check("EXTENDED_ROLES has all five",
      set(EXTENDED_ROLES) == {"parent", "placement_officer",
                              "finance_officer", "content_manager",
                              "super_admin"})


def fake(role):
    return SimpleNamespace(role=role, is_authenticated=True)


perms = [
    ("super_admin", "users", "delete", True),
    ("super_admin", "settings", "view", True),
    ("finance_officer", "finance", "view", True),
    ("finance_officer", "invoices", "delete", True),
    ("finance_officer", "refunds", "edit", True),
    ("finance_officer", "enrollments", "view", True),
    ("finance_officer", "courses", "view", False),
    ("finance_officer", "dashboard", "view", True),
    ("finance_officer", "users", "view", False),
    ("placement_officer", "jobs", "create", True),
    ("placement_officer", "employers", "edit", True),
    ("placement_officer", "applications", "view", True),
    ("placement_officer", "career", "delete", True),
    ("placement_officer", "courses", "view", False),
    ("placement_officer", "finance", "view", False),
    ("content_manager", "courses", "create", True),
    ("content_manager", "lessons", "edit", True),
    ("content_manager", "quizzes", "delete", True),
    ("content_manager", "question_bank", "view", True),
    ("content_manager", "announcements", "create", True),
    ("content_manager", "certificates", "edit", True),
    ("content_manager", "finance", "view", False),
    ("content_manager", "users", "view", False),
    ("content_manager", "dashboard", "view", True),
    ("parent", "progress", "view", True),
    ("parent", "progress", "create", False),
    ("parent", "progress", "edit", False),
    ("parent", "courses", "view", False),
    ("parent", "dashboard", "view", False),
    # old roles unchanged on the new module
    ("admin", "progress", "delete", True),
    ("manager", "progress", "view", True),
    ("faculty", "progress", "view", False),
    ("student", "progress", "view", False),
    ("employer", "progress", "view", False),
]
for role, module, action, want in perms:
    with ctx():
        got = OPS.has_permission(fake(role), module, action)
    check(f"matrix {role}/{module}/{action}={want}", got == want,
          f"got {got}")

with ctx():
    row = RolePermission.query.filter_by(role="parent",
                                         module="progress").first()
check("seeded parent/progress row: view-only",
      row is not None and row.can_view and not row.can_create
      and not row.can_edit and not row.can_delete)
with ctx():
    n = RolePermission.query.filter_by(role="super_admin").count()
check("super_admin fully seeded", n == len(OPS.PERMISSION_MODULES))

# ParentLink13
with ctx():
    db.session.add(ParentLink13(parent_user_id=admin_id,
                                student_user_id=otp_uid))
    db.session.commit()
    link = ParentLink13.query.filter_by(parent_user_id=admin_id).first()
check("parent link created + queryable",
      link is not None and link.student_user_id == otp_uid)
dup_ok = False
with ctx():
    db.session.add(ParentLink13(parent_user_id=admin_id,
                                student_user_id=otp_uid))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        dup_ok = True
check("duplicate parent link rejected", dup_ok)

# admin user-edit page: selector supports the new roles
ca2 = new_client()
ca2.post("/login", data={"email": "admin13@x.com", "password": "adminpass"})
r = ca2.get("/admin/users")
body = r.get_data(as_text=True)
check("user admin lists new roles in selector",
      all(f'value="{role}"' in body for role in EXTENDED_ROLES))
target_id = make_user("target13@x.com", "Target")
r = ca2.post(f"/admin/users/{target_id}/role", data={"role": "parent"},
             follow_redirects=True)
with ctx():
    tu = db.session.get(User, target_id)
check("admin can assign extended role", tu.role == "parent")
check("role change flash", "is now parent" in r.get_data(as_text=True))
r = ca2.post(f"/admin/users/{target_id}/role", data={"role": "nope"},
             follow_redirects=True)
with ctx():
    tu = db.session.get(User, target_id)
check("bogus role rejected", tu.role == "parent")

# login page carries the google flag (coordinator's snippet consumes it)
r = new_client().get("/login")
check("login page still renders", r.status_code == 200)

print(f"\n{passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
