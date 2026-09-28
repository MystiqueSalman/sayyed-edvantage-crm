"""Phase 13 — Auth & accounts models (Stream 1: auth).

Additive only: every table is new (p13_ prefix). Plain PG-compatible
SQLAlchemy types — no Alembic revision here; the Phase 13 coordinator
creates one combined migration for all streams.
"""
from datetime import datetime

from . import db


class PasswordResetToken(db.Model):
    """Single-use password-reset token.

    Only the SHA-256 hash of the token is stored; the raw token travels
    in the emailed link and is looked up by its deterministic hash.
    """
    __tablename__ = "p13_password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True,
                           index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmailOTP(db.Model):
    """Email one-time code for passwordless login.

    Deterministic SHA-256 hash (needed for lookup); compared with
    hmac.compare_digest. `attempts` counts wrong guesses; after the cap
    the code is invalidated via `consumed`.
    """
    __tablename__ = "p13_email_otps"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserSecurity13(db.Model):
    """TOTP MFA state per user (one row per user).

    totp_secret: base32 TOTP secret, stored in plain text. Encrypting it
    at rest needs a managed key-rotation story; flagged as a follow-up.
    backup_codes: JSON list of SHA-256 hex hashes of single-use codes.
    """
    __tablename__ = "p13_user_security"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, unique=True, index=True)
    totp_secret = db.Column(db.String(64), nullable=False)
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    backup_codes = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ParentLink13(db.Model):
    """Guardian -> student link (parent accounts watch their child's progress)."""
    __tablename__ = "p13_parent_links"

    id = db.Column(db.Integer, primary_key=True)
    parent_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                               nullable=False, index=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("parent_user_id", "student_user_id",
                            name="uq_p13_parent_link"),
    )
