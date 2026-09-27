"""WhatsApp notifications via Meta Cloud API (Phase 3, brief §12.1).

Mirrors the email automation pattern: all sends go through a daemon thread
and NEVER raise into the request. When WhatsAppSettings is missing or
disabled, sends are silent no-ops. The access token is never logged and
never rendered back into any page.
"""
import threading

import requests
from flask import current_app

GRAPH_VERSION = "v19.0"


# ---------------------------------------------------------------- low level
def _snapshot_settings():
    """Plain-dict copy of the settings row (safe to use off-thread)."""
    from .models import WhatsAppSettings
    s = WhatsAppSettings.query.get(1)
    if not s or not s.enabled or not s.phone_number_id or not s.access_token:
        return None
    return {"phone_number_id": s.phone_number_id,
            "access_token": s.access_token}


def _post_message(settings, to_phone, text):
    """Blocking Cloud API send. Raises on failure — callers must catch.

    NOTE: never log `settings['access_token']`.
    """
    url = (f"https://graph.facebook.com/{GRAPH_VERSION}/"
           f"{settings['phone_number_id']}/messages")
    resp = requests.post(
        url,
        headers={"Authorization": "Bearer " + settings["access_token"]},
        json={"messaging_product": "whatsapp", "to": to_phone,
              "type": "text", "body": text},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def normalize_phone(raw):
    """Digits only; bare 10-digit Indian numbers get the 91 prefix."""
    digits = "".join(c for c in (raw or "") if c.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def send_whatsapp_async(to_phone, text):
    """Queue a WhatsApp message on a daemon thread. Never raises.

    Returns True if queued, False if WhatsApp is disabled/unconfigured or
    there is no usable phone number (silent no-op).
    """
    try:
        app = current_app._get_current_object()
    except Exception:
        return False
    settings = _snapshot_settings()
    to_phone = normalize_phone(to_phone)
    if not settings or not to_phone or not text:
        return False

    def _run():
        try:
            with app.app_context():
                _post_message(settings, to_phone, text)
        except Exception:
            pass  # WhatsApp must never break the app

    threading.Thread(target=_run, name="lms-whatsapp", daemon=True).start()
    return True


def send_whatsapp_sync(to_phone, text):
    """Blocking send (used by the admin 'send test' button). Returns (ok, msg)."""
    settings = _snapshot_settings()
    to_phone = normalize_phone(to_phone)
    if not settings:
        return False, "WhatsApp is not configured or not enabled."
    if not to_phone:
        return False, "Enter a valid phone number."
    try:
        _post_message(settings, to_phone, text)
        return True, f"Test WhatsApp message sent to +{to_phone}."
    except Exception as exc:  # noqa: BLE001 - report to the admin UI
        return False, f"Send failed: {exc}"


# ---------------------------------------------------------------- templates
def _brand():
    return "Sayyed EdVantage LMS"


def send_enrollment_whatsapp(user, enrollment):
    course = enrollment.course
    base = current_app.config.get("APP_BASE_URL", "")
    text = (f"*{_brand()}* ✅\nHi {user.name}! You are enrolled in "
            f"*{course.title}*.\nAmount paid: ₹{enrollment.amount_paid:,}\n"
            f"Open your dashboard: {base}/dashboard")
    return send_whatsapp_async(user.phone, text)


def send_payment_receipt_whatsapp(user, enrollment):
    course = enrollment.course
    text = (f"*{_brand()}* 🧾 *Payment receipt*\nHi {user.name}, we received "
            f"₹{enrollment.amount_paid:,} for *{course.title}*.\n"
            f"Payment ID: {enrollment.razorpay_payment_id or '—'}\n"
            f"Thank you for learning with us! 🎓")
    return send_whatsapp_async(user.phone, text)


def send_graded_whatsapp(submission):
    user, assignment = submission.user, submission.assignment
    base = current_app.config.get("APP_BASE_URL", "")
    text = (f"*{_brand()}* 📝\nHi {user.name}! Your assignment "
            f"*{assignment.title}* ({assignment.course.title}) was graded: "
            f"*{submission.grade} / {assignment.max_marks}*.\n"
            f"Feedback: {submission.feedback or '—'}\n"
            f"View: {base}/assignment/{assignment.id}")
    return send_whatsapp_async(user.phone, text)


def send_live_reminder_whatsapp(student, session):
    when = session.starts_at.strftime("%d %b %Y, %I:%M %p UTC")
    text = (f"*{_brand()}* 🔴 *Live class in ~1 hour*\nHi {student.name}! "
            f"*{session.title}* ({session.course.title}) starts at {when}.\n"
            f"Join here: {session.join_url}\n"
            f"The join button also appears on your dashboard 15 min before.")
    return send_whatsapp_async(student.phone, text)
