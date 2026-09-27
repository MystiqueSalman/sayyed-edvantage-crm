"""Email automation for the LMS.

All sends go through a daemon thread and NEVER raise into the request:
failures are swallowed after a best-effort attempt. When EmailSettings is
missing or disabled, sends are silent no-ops.
"""
import smtplib
import threading
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


# ---------------------------------------------------------------- low level
def _build_message(settings, to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.from_name} <{settings.from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    return msg


def _deliver(settings, to_email, subject, html_body):
    """Blocking SMTP send. Raises on failure — callers must catch."""
    msg = _build_message(settings, to_email, subject, html_body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        try:
            smtp.starttls()
            smtp.ehlo()
        except smtplib.SMTPException:
            pass  # some hosts (port 465-style) don't do STARTTLS
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_pass or "")
        smtp.sendmail(settings.from_email, [to_email], msg.as_string())


def _snapshot_settings():
    """Plain-dict copy of the settings row (safe to use off-thread)."""
    from .models import EmailSettings
    s = EmailSettings.query.get(1)
    if not s or not s.enabled or not s.smtp_host or not s.from_email:
        return None
    return {
        "smtp_host": s.smtp_host, "smtp_port": s.smtp_port or 587,
        "smtp_user": s.smtp_user or "", "smtp_pass": s.smtp_pass or "",
        "from_email": s.from_email, "from_name": s.from_name or "Sayyed EdVantage LMS",
    }


class _Settings:
    def __init__(self, d):
        self.__dict__.update(d)


def send_email_async(to_email, subject, html_body):
    """Queue an email on a daemon thread. Never raises.

    Returns True if queued, False if email is disabled/unconfigured
    (silent no-op) so callers can tell.
    """
    try:
        app = current_app._get_current_object()
    except Exception:
        return False
    settings = _snapshot_settings()
    if not settings or not to_email:
        return False

    def _run():
        try:
            with app.app_context():
                _deliver(_Settings(settings), to_email, subject, html_body)
        except Exception:
            pass  # email must never break the app

    threading.Thread(target=_run, name="lms-email", daemon=True).start()
    return True


def send_email_sync(to_email, subject, html_body):
    """Blocking send (used by the 'send test email' button). Returns (ok, msg)."""
    settings = _snapshot_settings()
    if not settings:
        return False, "Email is not configured or not enabled."
    try:
        _deliver(_Settings(settings), to_email, subject, html_body)
        return True, f"Test email sent to {to_email}."
    except Exception as exc:  # noqa: BLE001 - report to the admin UI
        return False, f"Send failed: {exc}"


# ---------------------------------------------------------------- templates
def _wrap(title, body_html):
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;
background:#0a1628;color:#eef3fb;padding:28px;border-radius:12px">
<h2 style="color:#d4af37;margin-top:0">{title}</h2>{body_html}
<p style="color:#9fb3d1;font-size:.85rem;margin-top:24px">Sayyed EdVantage —
Empowering Students for Success · Mumbai, India</p></div>"""


def send_welcome_email(user):
    return send_email_async(
        user.email, "Welcome to Sayyed EdVantage LMS 🎓",
        _wrap("Welcome aboard!", f"""<p>Hi {user.name},</p>
<p>Your Sayyed EdVantage LMS account is ready. Browse the course catalog,
enroll, and start learning — live classes, quizzes, assignments and
certificates are all waiting inside.</p>
<p><a href="{current_app.config['APP_BASE_URL']}/courses"
style="color:#d4af37">Browse courses →</a></p>"""))


def send_enrollment_email(user, enrollment):
    course = enrollment.course
    return send_email_async(
        user.email, f"You're enrolled: {course.title} ✅",
        _wrap("Enrollment confirmed", f"""<p>Hi {user.name},</p>
<p>You are now enrolled in <b>{course.title}</b>.</p>
<p>Amount paid: <b>₹{enrollment.amount_paid:,}</b></p>
<p><a href="{current_app.config['APP_BASE_URL']}/dashboard"
style="color:#d4af37">Go to My Learning →</a></p>"""))


def send_graded_email(submission):
    user, assignment = submission.user, submission.assignment
    return send_email_async(
        user.email, f"Assignment graded: {assignment.title} 📝",
        _wrap("Your assignment was graded", f"""<p>Hi {user.name},</p>
<p><b>{assignment.title}</b> ({assignment.course.title}) has been graded.</p>
<p>Grade: <b>{submission.grade} / {assignment.max_marks}</b></p>
<p>Feedback: {submission.feedback or '—'}</p>
<p><a href="{current_app.config['APP_BASE_URL']}/assignment/{assignment.id}"
style="color:#d4af37">View feedback →</a></p>"""))


# ---------------------------------------------------------------- live-class reminders
def send_live_reminders(now=None):
    """Email enrolled students ~1 hour before a session starts.

    The sent_reminder flag is committed BEFORE sending so concurrent
    workers can't double-send. Safe to call repeatedly.
    """
    from . import db
    from .models import Enrollment, LiveSession, User
    now = now or datetime.utcnow()
    window_start = now + timedelta(minutes=50)
    window_end = now + timedelta(minutes=70)
    sessions = (LiveSession.query
                .filter(LiveSession.sent_reminder.is_(False),
                        LiveSession.starts_at >= window_start,
                        LiveSession.starts_at <= window_end).all())
    for sess in sessions:
        sess.sent_reminder = True
        db.session.commit()  # claim first — prevents duplicate sends
        students = (User.query.join(Enrollment,
                                   Enrollment.user_id == User.id)
                    .filter(Enrollment.course_id == sess.course_id,
                            Enrollment.status.in_(
                                [Enrollment.STATUS_ACTIVE,
                                 Enrollment.STATUS_COMPLETED]),
                            User.is_active.is_(True)).all())
        when = sess.starts_at.strftime("%d %b %Y, %I:%M %p UTC")
        for stu in students:
            send_email_async(
                stu.email, f"🔴 Live class in 1 hour: {sess.title}",
                _wrap("Live class starting soon", f"""<p>Hi {stu.name},</p>
<p>Your live class <b>{sess.title}</b> for <b>{sess.course.title}</b>
starts at <b>{when}</b> (about an hour from now).</p>
<p><a href="{sess.join_url}" style="color:#d4af37">Join Live Class →</a></p>
<p style="color:#9fb3d1;font-size:.85rem">The join button also appears on your
dashboard 15 minutes before the class begins.</p>"""))
    return len(sessions)
