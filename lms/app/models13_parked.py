"""Phase 13 - Stream 6 (parked pre-launch fixes): bounded chat-lead error log.

LeadCaptureLog13 persists every website-chat lead-capture failure so a
production-only failure becomes diagnosable from the admin diagnostics page
(/admin/diagnostics/chat-leads) instead of vanishing inside a bare
``except: db.session.rollback()``.

Bounded: rows older than 30 days are pruned on every write.

NOTE (coordinator): the combined Phase-13 Alembic revision must create this
table. Importing app.parked13 (the diagnostics blueprint) also registers the
model, so the startup ``db.create_all()`` picks it up on fresh databases.
"""
from datetime import datetime, timedelta

from . import db


class LeadCaptureLog13(db.Model):
    """One row per failed website-chat lead-capture attempt (bounded: 30 days)."""

    __tablename__ = "lead_capture_log13"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    # Pipeline stage that failed: validate | write | enrich | fee_asks
    stage = db.Column(db.String(40), default="")
    # Phone (or email, if a future flow supplies one) identifying the attempt.
    lead_email_or_phone = db.Column(db.String(120), default="")
    # Exception text / validation reason.
    error = db.Column(db.Text, default="")
    # Short safe context: conversation id, flags seen, etc. (no secrets).
    payload_summary = db.Column(db.Text, default="")

    def __repr__(self):  # pragma: no cover - debug helper
        return (f"<LeadCaptureLog13 id={self.id} stage={self.stage!r} "
                f"at={self.created_at}>")


LOG13_RETENTION_DAYS = 30


def log_capture_error(stage, identifier="", error_text="", payload_summary=""):
    """Persist a chat-lead failure and prune rows older than 30 days.

    Never raises: logging must not break the request it is diagnosing.
    """
    try:
        db.session.add(LeadCaptureLog13(
            stage=(stage or "")[:40],
            lead_email_or_phone=(identifier or "")[:120],
            error=(error_text or "")[:4000],
            payload_summary=(payload_summary or "")[:2000],
        ))
        cutoff = datetime.utcnow() - timedelta(days=LOG13_RETENTION_DAYS)
        (LeadCaptureLog13.query
         .filter(LeadCaptureLog13.created_at < cutoff)
         .delete(synchronize_session=False))
        db.session.commit()
    except Exception:
        db.session.rollback()
