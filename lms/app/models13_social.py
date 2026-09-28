"""Phase 13, Stream 4 — Direct messaging + leaderboard models.

Additive tables (plain PG-compatible SQLAlchemy types; the Alembic
revision is added by the coordinator as one combined Phase 13 revision):

  - dm_conversations   — one student + one staff member (faculty/admin/counsellor)
  - dm_messages        — append-only messages in a conversation
  - leaderboard_privacy — per-user opt-out for the public leaderboard
"""
from datetime import datetime

from . import db


class Conversation13(db.Model):
    """A controlled direct-messaging thread: exactly one student and one
    staff-side user (faculty, admin or counsellor). Only staff can start
    a conversation; students can only reply inside their own threads."""
    __tablename__ = "dm_conversations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                           nullable=False, index=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                           nullable=False, index=True)
    subject = db.Column(db.String(160), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    last_message_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("User", foreign_keys=[student_id])
    faculty = db.relationship("User", foreign_keys=[faculty_id])
    messages = db.relationship("DirectMessage13", backref="conversation",
                               cascade="all, delete-orphan",
                               order_by="DirectMessage13.created_at")

    def other_party(self, user_id):
        """The participant that is NOT user_id (for the inbox list)."""
        return self.faculty if user_id == self.student_id else self.student


class DirectMessage13(db.Model):
    """One message inside a Conversation13. read_at is NULL while the
    other party has not opened the thread."""
    __tablename__ = "dm_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer,
                               db.ForeignKey("dm_conversations.id"),
                               nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                          nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id])


class PrivacyPrefs13(db.Model):
    """Per-user leaderboard privacy preference. Rows are created lazily;
    absence of a row == visible on the leaderboard."""
    __tablename__ = "leaderboard_privacy"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True,
                       nullable=False, index=True)
    leaderboard_opt_out = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
