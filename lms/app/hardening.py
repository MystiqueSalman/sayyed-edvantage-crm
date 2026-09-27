"""Phase 10 — platform hardening logic (§24, §25, §12.4, §12.5).

Central library for: message-template rendering, the notify() helper,
webhook dispatch (HMAC-SHA256 signing + retry + delivery log), SQLite
backups, and monitoring helpers. All side effects are fail-safe: a
notification/webhook/backup problem must never break the flow that
triggered it.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import threading
import time
from collections import deque
from datetime import datetime

import requests
from sqlalchemy import text

from . import db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- templates

#: Plain {{variable}} placeholder matcher — the ONLY template syntax that
#: renders. Anything else inside {{ }} is dropped (no expressions).
_SIMPLE_VAR = re.compile(r"\s*[A-Za-z_][A-Za-z0-9_]*\s*")

#: Allow-listed variables available inside {{...}} message templates (§12.5).
TEMPLATE_VARS = (
    "site_name", "user_name", "user_email", "course_title", "course_fee",
    "event", "title", "body", "link", "code", "amount", "quiz_title",
    "score", "percent", "badge_name", "challenge_title", "job_title",
    "application_status", "session_title", "starts_at", "lead_name",
    "lead_phone",
)

SAMPLE_CONTEXT = {
    "site_name": "Sayyed EdVantage",
    "user_name": "Aarav Sharma",
    "user_email": "aarav@example.com",
    "course_title": "Data Science",
    "course_fee": "₹50,000",
    "event": "enrollment.created",
    "title": "Welcome aboard!",
    "body": "Your enrollment is confirmed.",
    "link": "https://lms.sayyededvantage.in/dashboard",
    "code": "SE-ABC123",
    "amount": "₹50,000",
    "quiz_title": "Module 1 Quiz",
    "score": "8/10",
    "percent": "80",
    "badge_name": "Quiz Whiz",
    "challenge_title": "7-Day Streak Sprint",
    "job_title": "Junior Data Analyst",
    "application_status": "shortlisted",
    "session_title": "Doubt Clearing — Week 3",
    "starts_at": "28 Sep 2026, 07:00 PM IST",
    "lead_name": "Priya Verma",
    "lead_phone": "+91 98765 43210",
}


def render_template_string(body, context, _bump=None):
    """Render a {{variable}} template with a safe allow-list context.

    Sandboxed by construction: ONLY plain ``{{var_name}}`` placeholders
    are substituted (from TEMPLATE_VARS; unknown/missing -> ""). Jinja
    statement blocks (``{% ... %}``) are stripped and any other
    ``{{ ... }}`` expression is dropped — no expression evaluation, no
    attribute access, no code execution is possible. Never raises.
    Returns the rendered string.
    """
    safe = {k: str(context.get(k, "")) for k in TEMPLATE_VARS}
    text = body or ""
    try:
        text = re.sub(r"\{%.*?%\}", "", text, flags=re.S)  # no statements
        def _one(m):
            inner = m.group(1)
            if _SIMPLE_VAR.fullmatch(inner or ""):
                return safe.get(inner.strip(), "")
            return ""  # not a plain variable -> drop it
        text = re.sub(r"\{\{(.*?)\}\}", _one, text, flags=re.S)
    except Exception:
        text = body or ""
    if _bump is not None:
        # best-effort usage counter; must never break rendering
        try:
            from flask import has_app_context
            if has_app_context():
                from .models import MessageTemplate
                tpl = db.session.get(MessageTemplate, _bump)
                if tpl:
                    tpl.use_count = (tpl.use_count or 0) + 1
                    db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
    return text


def render_event_template(event_key, channel, context, fallback_subject="",
                          fallback_body=""):
    """Render the active template for (event_key, channel).

    Falls back to the supplied subject/body when no active template
    exists. Returns (subject, body, template_id_or_None).
    """
    from .models import MessageTemplate
    tpl = (MessageTemplate.query
           .filter_by(event_key=event_key, channel=channel, is_active=True)
           .order_by(MessageTemplate.updated_at.desc()).first())
    if not tpl:
        return fallback_subject, fallback_body, None
    subject = render_template_string(tpl.subject, context, _bump=tpl.id)
    body = render_template_string(tpl.body, context, _bump=tpl.id)
    return subject, body, tpl.id


def notify(user_id, ntype, title, body="", link="", context=None,
           _commit=True):
    """Create an in-app notification (§12.4). Never raises.

    If an active ``notification``-channel template exists for the event
    key == ntype, its subject/body override the supplied title/body.
    """
    try:
        from .models import Notification
        if not user_id:
            return None
        ctx = dict(context or {})
        ctx.setdefault("title", title)
        ctx.setdefault("body", body)
        ctx.setdefault("link", link)
        ctx.setdefault("event", ntype)
        rtitle, rbody, _tpl = render_event_template(
            ntype, "notification", ctx,
            fallback_subject=title, fallback_body=body)
        n = Notification(user_id=user_id, ntype=ntype, title=rtitle[:200],
                         body=rbody, link=link or "")
        db.session.add(n)
        if _commit:
            db.session.commit()
        else:
            db.session.flush()
        return n
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        log.exception("notify failed (non-fatal)")
        return None


def unread_count(user_id):
    from .models import Notification
    try:
        return Notification.query.filter_by(
            user_id=user_id, is_read=False).count()
    except Exception:
        return 0


# ------------------------------------------------------- event emitters (§25.2)

def emit_enrollment(user, enrollment, payment_completed=False):
    """Fire enrollment.created (+ optionally payment.completed).

    Called from the REAL enrollment sites only. Never raises.
    """
    try:
        course = getattr(enrollment, "course", None)
        ctx = {"user_name": getattr(user, "name", ""),
               "user_email": getattr(user, "email", ""),
               "course_title": getattr(course, "title", "") if course else "",
               "amount": f"₹{enrollment.amount_paid:,}"}
        notify(getattr(user, "id", None), "enrollment.created",
               f"Enrolled in {ctx['course_title']} 🎉",
               "Your enrollment is confirmed. Happy learning!",
               link="/dashboard", context=ctx)
        dispatch_webhook("enrollment.created", {
            "enrollment_id": enrollment.id,
            "user_id": getattr(user, "id", None),
            "user_name": getattr(user, "name", ""),
            "course_id": getattr(course, "id", None) if course else None,
            "course_title": ctx["course_title"],
            "amount_paid": enrollment.amount_paid or 0,
            "paid": bool(enrollment.paid)})
        if payment_completed:
            dispatch_webhook("payment.completed", {
                "enrollment_id": enrollment.id,
                "user_id": getattr(user, "id", None),
                "user_name": getattr(user, "name", ""),
                "course_id": getattr(course, "id", None) if course else None,
                "course_title": ctx["course_title"],
                "amount_paid": enrollment.amount_paid or 0,
                "razorpay_payment_id":
                    getattr(enrollment, "razorpay_payment_id", "") or ""})
    except Exception:
        log.exception("emit_enrollment failed (non-fatal)")


def emit_lead_created(lead):
    """Fire lead.created for a genuinely new lead. Never raises."""
    try:
        dispatch_webhook("lead.created", {
            "lead_id": lead.id, "name": lead.name, "phone": lead.phone,
            "email": lead.email or "", "source": lead.source,
            "status": lead.status,
            "course_id": lead.course_id,
            "course_title": lead.course.title if lead.course else ""})
    except Exception:
        log.exception("emit_lead_created failed (non-fatal)")


# ------------------------------------------------------------------ webhooks

def sign_payload(secret, payload_bytes):
    """HMAC-SHA256 hex signature for a webhook payload (§25.2)."""
    return hmac.new((secret or "").encode(), payload_bytes,
                    hashlib.sha256).hexdigest()


def _webhook_targets(event):
    from .models import Webhook
    try:
        return [w for w in Webhook.query.filter_by(is_active=True).all()
                if w.wants(event)]
    except Exception:
        return []


def _post_with_retry(webhook_id, event, payload, sync=False,
                   max_attempts=3):
    """POST the payload, retrying with exponential backoff.

    Every attempt is logged to webhook_deliveries. In async (default)
    mode this runs in a daemon thread so event flows never block; the
    webhook row is re-fetched inside the thread's app context.
    """
    from flask import current_app
    try:
        _app = current_app._get_current_object()
    except Exception:
        _app = None

    body = json.dumps(payload, default=str).encode()

    def attempt(url, secret):
        signature = sign_payload(secret, body)
        headers = {"Content-Type": "application/json",
                   "X-SE-Signature": signature,
                   "X-SE-Event": event,
                   "User-Agent": "SayyedEdVantage-LMS/1.0"}
        started = time.time()
        try:
            r = requests.post(url, data=body, headers=headers, timeout=8)
            return r.status_code, int((time.time() - started) * 1000), ""
        except Exception as exc:  # noqa: BLE001 - recorded in delivery log
            return None, int((time.time() - started) * 1000), str(exc)[:500]

    def run():
        from .models import Webhook, WebhookDelivery
        ctx = _app.app_context() if _app else nullcontext()
        with ctx:
            wh = db.session.get(Webhook, webhook_id)
            if not wh:
                return False
            ok, last_status, last_err, last_ms = False, None, "", None
            n = 0
            for n in range(1, max_attempts + 1):
                status, ms, err = attempt(wh.url, wh.secret)
                last_status, last_ms, last_err = status, ms, err
                if status and 200 <= status < 300:
                    ok = True
                    break
                if n < max_attempts:
                    time.sleep(2 ** (n - 1))  # 1s, 2s backoff
            try:
                db.session.add(WebhookDelivery(
                    webhook_id=wh.id, event=event,
                    payload=body.decode("utf-8", "replace"),
                    attempts=n, status_code=last_status,
                    latency_ms=last_ms, success=ok,
                    error="" if ok else (last_err or
                                        f"HTTP {last_status}")))
                wh.last_triggered_at = datetime.utcnow()
                db.session.commit()
            except Exception:
                db.session.rollback()
            return ok

    if sync:
        return run()

    t = threading.Thread(target=run, name="lms-webhook-dispatch",
                         daemon=True)
    t.start()
    return True


class nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def dispatch_webhook(event, payload, sync=False):
    """Fire a webhook event to all subscribed active webhooks (§25.2).

    Never raises. ``payload`` must be JSON-serializable. The standard
    envelope is ``{"event": ..., "sent_at": ..., "data": payload}``.
    """
    try:
        targets = _webhook_targets(event)
        if not targets:
            return 0
        envelope = {"event": event,
                    "sent_at": datetime.utcnow().isoformat() + "Z",
                    "data": payload}
        for wh in targets:
            try:
                _post_with_retry(wh.id, event, envelope, sync=sync)
            except Exception:
                log.exception("webhook dispatch failed (non-fatal)")
        return len(targets)
    except Exception:
        log.exception("dispatch_webhook failed (non-fatal)")
        return 0


# ------------------------------------------------------------------- backups

def backup_dir():
    """Directory that holds SQLite backup files (§24.3)."""
    base = os.environ.get("SE_DATA_DIR", "").strip()
    if not base:
        # fall back to the directory holding the sqlite file (test
        # suites point SQLITE_PATH at isolated temp files)
        sp = ""
        try:
            sp = sqlite_path()
        except Exception:
            sp = ""
        if sp:
            base = os.path.dirname(os.path.abspath(sp))
    if not base:
        from flask import current_app
        try:
            base = current_app.instance_path
        except Exception:
            base = os.path.expanduser("~/workspace/lms/instance")
    d = os.path.join(base, "backups")
    os.makedirs(d, exist_ok=True)
    return d


def sqlite_path():
    from flask import current_app
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        return uri.replace("sqlite:///", "", 1)
    return ""


def is_sqlite_mode():
    from flask import current_app
    return current_app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")


def get_setting(key, default=""):
    from .models import AppSetting
    try:
        return AppSetting.get(key, default)
    except Exception:
        return default


def retention_days():
    try:
        return max(1, int(get_setting("backup.retention_days", "7")))
    except Exception:
        return 7


def create_backup(note="manual"):
    """Create a timestamped SQLite backup. Returns the Backup row.

    SQLite-only (Postgres deployments use provider-level backups).
    Uses the online backup API so the live DB is never locked.
    """
    from .models import Backup
    if not is_sqlite_mode():
        raise RuntimeError("backups are only supported in SQLite mode")
    src = sqlite_path()
    if not src or not os.path.exists(src):
        raise FileNotFoundError("live database file not found")
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"lms-backup-{ts}.db"
    dest = os.path.join(backup_dir(), filename)
    import sqlite3
    src_conn = sqlite3.connect(src)
    try:
        dst_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    row = Backup(filename=filename,
                 size_bytes=os.path.getsize(dest), note=note or "")
    db.session.add(row)
    db.session.commit()
    prune_backups()
    return row



def prune_backups():
    """Delete oldest backup files beyond the retention count (§24.3)."""
    from .models import Backup
    keep = retention_days()
    rows = Backup.query.order_by(Backup.created_at.desc()).all()
    for old in rows[keep:]:
        try:
            p = os.path.join(backup_dir(), old.filename)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        db.session.delete(old)
    if rows[keep:]:
        db.session.commit()


def list_backups():
    from .models import Backup
    rows = Backup.query.order_by(Backup.created_at.desc()).all()
    out = []
    for r in rows:
        p = os.path.join(backup_dir(), r.filename)
        out.append({"id": r.id, "filename": r.filename,
                    "size_bytes": r.size_bytes, "created_at": r.created_at,
                    "note": r.note, "exists": os.path.exists(p)})
    return out


def verify_backup_file(path):
    """True if the file is a readable SQLite database."""
    import sqlite3
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def restore_backup(backup_id, actor=None):
    """Restore a backup over the live SQLite DB (§24.3).

    SQLite mode only. Disposes the engine so no pooled connection holds
    the old file. The audit entry is written AFTER the swap so it
    survives in the restored database.
    """
    from .models import Backup, AuditLog
    from . import operations as OPS  # noqa: F401 (kept for callers)
    if not is_sqlite_mode():
        raise RuntimeError("restore is only supported in SQLite mode")
    row = db.session.get(Backup, backup_id)
    if not row:
        raise FileNotFoundError("backup not found")
    filename = row.filename
    src = os.path.join(backup_dir(), filename)
    if not os.path.exists(src):
        raise FileNotFoundError("backup file missing from disk")
    if not verify_backup_file(src):
        raise ValueError("backup file is not a valid SQLite database")
    dest = sqlite_path()
    db.session.remove()
    db.engine.dispose()
    shutil.copy2(src, dest)
    db.engine.dispose()
    # Audit AFTER the swap so the entry lives in the restored DB.
    try:
        db.session.add(AuditLog(
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", "") or "",
            action="backup.restore", target_type="backup",
            target_id=backup_id,
            detail=f"Restored {filename} over live database", ip=""))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return True


def backup_due():
    """True when no backup exists in the last 24h (for the scheduler)."""
    from .models import Backup
    if not is_sqlite_mode():
        return False
    if get_setting("backup.enabled", "1") != "1":
        return False
    try:
        latest = Backup.query.order_by(Backup.created_at.desc()).first()
    except Exception:
        return False
    if not latest:
        return True
    return (datetime.utcnow() - latest.created_at).total_seconds() > 24 * 3600


def run_scheduled_backup():
    """Daily-backup worker body: create one backup if due (§24.3)."""
    try:
        if backup_due():
            create_backup(note="scheduled-daily")
            log.info("scheduled backup created")
    except Exception:
        log.exception("scheduled backup failed (non-fatal)")


# ---------------------------------------------------------------- monitoring

_req_stats = {"started_at": datetime.utcnow(), "requests": 0, "errors": 0,
              "by_endpoint": {}}
_recent_errors = deque(maxlen=50)  # (timestamp, method, path, status, note)


def record_request(endpoint, status_code, note=""):
    _req_stats["requests"] += 1
    ep = endpoint or "?"
    d = _req_stats["by_endpoint"]
    d[ep] = d.get(ep, 0) + 1
    if status_code >= 500:
        _req_stats["errors"] += 1
        _recent_errors.appendleft(
            (datetime.utcnow().isoformat(timespec="seconds") + "Z",
             note, ep, status_code))


def request_stats():
    uptime = (datetime.utcnow() - _req_stats["started_at"]).total_seconds()
    return {"uptime_seconds": int(uptime),
            "requests": _req_stats["requests"],
            "errors": _req_stats["errors"],
            "by_endpoint": dict(
                sorted(_req_stats["by_endpoint"].items(),
                       key=lambda kv: -kv[1])[:25]),
            "recent_errors": [
                {"at": t, "request": n, "endpoint": e, "status": s}
                for t, n, e, s in _recent_errors]}


def app_log_path():
    base = os.environ.get("SE_DATA_DIR", "").strip()
    if not base:
        try:
            from flask import current_app
            base = current_app.instance_path
        except Exception:
            base = "/tmp"
    d = os.path.join(base, "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "app.log")


def tail_app_log(n=200):
    """Last n lines of the app log file (§24.4)."""
    p = app_log_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 8192
            data = b""
            while len(data.splitlines()) <= n and f.tell() > 0:
                step = min(block, f.tell())
                f.seek(-step - len(data), os.SEEK_CUR)
                data = f.read(step) + data
                f.seek(-len(data), os.SEEK_CUR)
            return data.decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []


def health_checks():
    """DB connectivity + disk-space checks for /health (§24.4)."""
    from flask import current_app
    checks = {}
    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = {"ok": True,
                        "dialect": db.engine.dialect.name}
    except Exception as exc:  # noqa: BLE001
        checks["db"] = {"ok": False, "error": str(exc)[:200]}
    try:
        base = os.environ.get("SE_DATA_DIR", "").strip() or \
            current_app.instance_path
        usage = shutil.disk_usage(base)
        free_mb = usage.free // (1024 * 1024)
        checks["disk"] = {"ok": free_mb > 100, "free_mb": free_mb,
                          "path": base}
    except Exception as exc:  # noqa: BLE001
        checks["disk"] = {"ok": False, "error": str(exc)[:200]}
    ok = all(c.get("ok") for c in checks.values())
    return ok, checks


# ------------------------------------------------------------------ defaults

DEFAULT_TEMPLATES = [
    # (name, event_key, channel, subject, body)
    ("Enrollment confirmation", "enrollment.created", "notification",
     "Enrolled in {{course_title}} 🎉",
     "Hi {{user_name}}! Your enrollment in <b>{{course_title}}</b> is "
     "confirmed. Happy learning!"),
    ("Enrollment email", "enrollment.created", "email",
     "Welcome to {{course_title}} — Sayyed EdVantage",
     "<p>Hi {{user_name}},</p><p>Your enrollment in <b>{{course_title}}</b> "
     "is confirmed. Log in to start learning.</p>"),
    ("Quiz graded", "quiz.graded", "notification",
     "{{quiz_title}} graded: {{score}}",
     "Hi {{user_name}}! Your attempt at <b>{{quiz_title}}</b> was graded: "
     "<b>{{score}}</b> ({{percent}}%)."),
    ("Assignment graded", "assignment.graded", "notification",
     "Assignment graded: {{score}}",
     "Hi {{user_name}}! Your assignment submission was graded: "
     "<b>{{score}}</b>."),
    ("Certificate issued", "certificate.issued", "notification",
     "Certificate ready for {{course_title}} 🏅",
     "Congratulations {{user_name}}! Your certificate for "
     "<b>{{course_title}}</b> is ready. Code: {{code}}."),
    ("Live class reminder", "live.reminder", "notification",
     "🔴 Live class in 1 hour: {{session_title}}",
     "Hi {{user_name}}! <b>{{session_title}}</b> ({{course_title}}) starts "
     "at {{starts_at}}. Join from your dashboard."),
    ("Badge earned", "badge.earned", "notification",
     "Badge unlocked: {{badge_name}} 🏆",
     "Well done {{user_name}}! You earned the <b>{{badge_name}}</b> badge."),
    ("Challenge completed", "challenge.won", "notification",
     "Challenge complete: {{challenge_title}} 🏁",
     "Amazing {{user_name}}! You completed <b>{{challenge_title}}</b>."),
    ("Application update", "application.status", "notification",
     "Application update: {{job_title}}",
     "Hi {{user_name}}! Your application for <b>{{job_title}}</b> is now "
     "<b>{{application_status}}</b>."),
    ("New lead", "lead.created", "notification",
     "New lead: {{lead_name}}",
     "New lead {{lead_name}} ({{lead_phone}}) via {{event}}."),
]


def ensure_hardening_defaults():
    """Seed default message templates + app settings (idempotent, guarded)."""
    from sqlalchemy import inspect as _insp
    from .models import MessageTemplate
    try:
        if "message_templates" not in _insp(db.engine).get_table_names():
            return
        existing = {t.name for t in MessageTemplate.query.all()}
        for name, event_key, channel, subject, body in DEFAULT_TEMPLATES:
            if name not in existing:
                db.session.add(MessageTemplate(
                    name=name, event_key=event_key, channel=channel,
                    subject=subject, body=body, is_active=True))
        db.session.commit()
    except Exception:
        db.session.rollback()
    defaults = {"backup.enabled": "1", "backup.retention_days": "7",
                "api.default_rate_limit": "300"}
    try:
        from .models import AppSetting
        if "app_settings" in _insp(db.engine).get_table_names():
            for k, v in defaults.items():
                if db.session.get(AppSetting, k) is None:
                    db.session.add(AppSetting(key=k, value=v))
            db.session.commit()
    except Exception:
        db.session.rollback()
