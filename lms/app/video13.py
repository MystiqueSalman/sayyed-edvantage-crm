"""Phase 13 Stream 2 — signed video URLs (video security).

Token format (URL-safe base64 of a dot-joined payload)::

    base64url("<lesson_id>.<user_id>.<exp_unix>.<sig_hex>")

``sig_hex`` = HMAC-SHA256(app SECRET_KEY, "<lesson_id>.<user_id>.<exp_unix>").

Properties:
  * bound to one lesson AND one user (tokens cannot be shared between
    accounts — the watch route requires the logged-in user to equal the
    token's user_id);
  * short expiry (per-lesson VideoPolicy13.token_expiry_hours, else the
    ``p13_video_default_expiry_hours`` app setting, else 2h);
  * validated with hmac.compare_digest (constant-time);
  * the raw stored video URL is never rendered into page source — the
    watch page embeds a same-origin /v/<token>/stream URL which 302s to
    the stored URL.

Rotation: changing the Flask SECRET_KEY instantly invalidates every
outstanding token (they fail signature verification). Previously issued
URLs simply stop working; new URLs are minted on the next lesson-page
render. No per-token revocation list is kept.
"""
import base64
import hashlib
import hmac
import time

from flask import current_app, url_for


def _signing_key():
    key = current_app.config.get("SECRET_KEY", "")
    return key.encode("utf-8") if isinstance(key, str) else bytes(key)


def default_expiry_hours():
    """Global default token lifetime (hours) when a lesson has no policy."""
    try:
        from .models import AppSetting
        raw = AppSetting.get("p13_video_default_expiry_hours", "2")
        return max(1, int(raw))
    except Exception:
        return 2


def policy_for_lesson(lesson_id):
    """Return the VideoPolicy13 row for a lesson, or None."""
    from .models13_learning import VideoPolicy13
    return VideoPolicy13.query.filter_by(lesson_id=lesson_id).first()


def expiry_hours_for_lesson(lesson_id):
    policy = policy_for_lesson(lesson_id)
    if policy and policy.token_expiry_hours:
        return max(1, int(policy.token_expiry_hours))
    return default_expiry_hours()


def download_allowed(lesson_id):
    policy = policy_for_lesson(lesson_id)
    return bool(policy and policy.allow_download)


def mint_video_token(lesson_id, user_id, expiry_hours=None):
    """Create a fresh signed token string (not the full URL)."""
    hours = expiry_hours if expiry_hours else expiry_hours_for_lesson(lesson_id)
    exp = int(time.time()) + int(hours) * 3600
    payload = f"{int(lesson_id)}.{int(user_id)}.{exp}"
    sig = hmac.new(_signing_key(), payload.encode("utf-8"),
                   hashlib.sha256).hexdigest()
    raw = f"{payload}.{sig}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def signed_video_url(lesson_id, user_id, expiry_hours=None):
    """Public helper: full same-origin signed URL for a lesson video."""
    token = mint_video_token(lesson_id, user_id,
                             expiry_hours=expiry_hours)
    return url_for("learn13.video_watch", token=token)


def verify_video_token(token):
    """Validate a token.

    Returns (lesson_id, user_id, exp) on success, else (None, error_str).
    """
    if not token or not isinstance(token, str):
        return None, "missing token"
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:
        return None, "malformed token"
    parts = raw.split(".")
    if len(parts) != 4:
        return None, "malformed token"
    lesson_s, user_s, exp_s, sig = parts
    try:
        lesson_id, user_id, exp = int(lesson_s), int(user_s), int(exp_s)
    except ValueError:
        return None, "malformed token"
    payload = f"{lesson_id}.{user_id}.{exp}"
    expected = hmac.new(_signing_key(), payload.encode("utf-8"),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None, "invalid signature"
    if exp <= int(time.time()):
        return None, "token expired"
    return (lesson_id, user_id, exp), None
