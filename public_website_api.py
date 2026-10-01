"""Public website API for the Sayyed EdVantage CRM.

Exposes a small, unauthenticated surface for the public marketing website:

    POST /api/public/request-otp   {phone, email, channel?} -> sends 6-digit OTP
    POST /api/public/verify-otp    {phone, email, code}      -> {verify_token}
    POST /api/public/lead          {name, phone, email, verify_token, ...}

Security model (no dashboard credentials involved; dashboard Basic Auth untouched):
  * CORS enabled for browser calls from the website.
  * Per-target and per-IP rate limits (in-memory sliding windows).
  * OTP: 6 digits, 5-minute expiry, max 5 verify attempts, constant-time compare.
  * Verification tokens: random, 15-minute expiry, single-use, bound to
    phone+email. A lead can only be created with a valid token.
  * Honeypot field on the lead endpoint to catch naive bots.

Configuration (all via environment, nothing secret in code):
    SE_SMTP_HOST, SE_SMTP_PORT (default 587), SE_SMTP_USER, SE_SMTP_PASS,
    SE_SMTP_FROM (default SE_SMTP_USER), SE_SMTP_USE_TLS (default 1)
    SE_SMS_WEBHOOK_URL, SE_SMS_WEBHOOK_METHOD (default POST),
    SE_SMS_WEBHOOK_HEADERS (JSON object, optional),
    SE_SMS_WEBHOOK_BODY (template with {to} and {code} placeholders, optional)

If neither channel is configured, /request-otp answers
{"ok": false, "error": "otp_channel_not_configured"} so the website can show a
"connecting soon" state instead of faking an OTP.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlparse

try:
    from app.leads.lead_manager import (
        create_or_update_lead,
        find_duplicate_lead,
        get_lead,
        update_lead,
    )
except Exception:  # pragma: no cover - import shim for standalone checks
    create_or_update_lead = find_duplicate_lead = get_lead = update_lead = None

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


SMTP_HOST = _env("SE_SMTP_HOST")
SMTP_PORT = int(_env("SE_SMTP_PORT", "587") or 587)
SMTP_USER = _env("SE_SMTP_USER")
SMTP_PASS = _env("SE_SMTP_PASS")
SMTP_FROM = _env("SE_SMTP_FROM", SMTP_USER)
SMTP_USE_TLS = _env("SE_SMTP_USE_TLS", "1") == "1"

SMS_WEBHOOK_URL = _env("SE_SMS_WEBHOOK_URL")
SMS_WEBHOOK_METHOD = _env("SE_SMS_WEBHOOK_METHOD", "POST").upper()
try:
    SMS_WEBHOOK_HEADERS = json.loads(_env("SE_SMS_WEBHOOK_HEADERS", "{}") or "{}")
except Exception:
    SMS_WEBHOOK_HEADERS = {}
SMS_WEBHOOK_BODY = _env("SE_SMS_WEBHOOK_BODY") or (
    '{"to": "{to}", "message": "Your Sayyed EdVantage OTP is {code}. '
    'Valid for 5 minutes. Do not share it."}'
)

PUBLIC_PREFIX = "/api/public/"

OTP_TTL_SEC = 300          # 5 minutes
OTP_MAX_ATTEMPTS = 5
OTP_REQUEST_LIMIT = 3      # per target
OTP_REQUEST_WINDOW = 600   # per 10 minutes
VERIFY_TOKEN_TTL_SEC = 900  # 15 minutes
LEAD_SUBMIT_LIMIT = 10     # per IP
LEAD_SUBMIT_WINDOW = 3600  # per hour


# --------------------------------------------------------------------------
# In-memory stores (ephemeral; fine for OTPs / rate limits)
# --------------------------------------------------------------------------

_lock = threading.Lock()
_otp_store: dict[str, dict] = {}      # target_key -> {code, expires_at, attempts, phone, email}
_verify_tokens: dict[str, dict] = {}  # token -> {phone, email, expires_at}
_rate_limits: dict[str, list[float]] = {}  # key -> [timestamps]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def is_public_path(path: str) -> bool:
    return urlparse(path).path.startswith(PUBLIC_PREFIX)


def _client_ip(handler) -> str:
    fwd = handler.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return handler.client_address[0] if handler.client_address else "unknown"


def _rate_ok(key: str, limit: int, window_sec: int) -> bool:
    now = time.time()
    with _lock:
        hits = [t for t in _rate_limits.get(key, []) if now - t < window_sec]
        if len(hits) >= limit:
            _rate_limits[key] = hits
            return False
        hits.append(now)
        _rate_limits[key] = hits
        return True


def _normalize_phone(raw: str) -> str:
    raw = (raw or "").strip().replace(" ", "").replace("-", "")
    if raw.startswith("+"):
        return "+" + re.sub(r"\D", "", raw[1:])
    return re.sub(r"\D", "", raw)


def _valid_phone(phone: str) -> bool:
    digits = phone.lstrip("+")
    return digits.isdigit() and 10 <= len(digits) <= 15


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (email or "").strip()))


def _mask_phone(phone: str) -> str:
    digits = phone.lstrip("+")
    if len(digits) <= 4:
        return "***"
    return ("+" if phone.startswith("+") else "") + "*" * (len(digits) - 4) + digits[-4:]


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return (local[:2] + "***@" + domain) if len(local) > 2 else ("***@" + domain)


def _send_otp_email(to_email: str, code: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Your Sayyed EdVantage OTP"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Your Sayyed EdVantage verification code is: {code}\n\n"
        f"It is valid for 5 minutes. Do not share it with anyone.\n\n"
        f"- Team Sayyed EdVantage"
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def _send_otp_sms(to_phone: str, code: str) -> None:
    if requests is None:
        raise RuntimeError("requests library not available for SMS webhook")
    body = SMS_WEBHOOK_BODY.replace("{to}", to_phone).replace("{code}", code)
    headers = dict(SMS_WEBHOOK_HEADERS or {})
    kwargs: dict = {"headers": headers, "timeout": 20}
    try:
        payload = json.loads(body)
        kwargs["json"] = payload
    except Exception:
        kwargs["data"] = body.encode("utf-8")
    resp = requests.request(SMS_WEBHOOK_METHOD, SMS_WEBHOOK_URL, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"SMS webhook returned HTTP {resp.status_code}: {resp.text[:200]}")


def _public_json(handler, payload: dict, status: int = 200) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def handle_public_options(handler) -> None:
    handler.send_response(204)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Max-Age", "86400")
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _read_json_body(handler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except Exception:
        length = 0
    raw = handler.rfile.read(length).decode("utf-8") if length > 0 else "{}"
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------
# Endpoint handlers
# --------------------------------------------------------------------------

def _handle_request_otp(handler, data: dict, ip: str) -> None:
    phone = _normalize_phone(data.get("phone", ""))
    email = (data.get("email", "") or "").strip().lower()
    want = (data.get("channel", "") or "").strip().lower()

    if phone and not _valid_phone(phone):
        _public_json(handler, {"ok": False, "error": "invalid_phone"}, 400)
        return
    if email and not _valid_email(email):
        _public_json(handler, {"ok": False, "error": "invalid_email"}, 400)
        return
    if not phone and not email:
        _public_json(handler, {"ok": False, "error": "phone_or_email_required"}, 400)
        return

    sms_ready = bool(SMS_WEBHOOK_URL)
    email_ready = bool(SMTP_HOST and SMTP_FROM)

    if want == "sms":
        channel = "sms" if (phone and sms_ready) else None
    elif want == "email":
        channel = "email" if (email and email_ready) else None
    else:
        if phone and sms_ready:
            channel = "sms"
        elif email and email_ready:
            channel = "email"
        else:
            channel = None

    if not channel:
        _public_json(handler, {"ok": False, "error": "otp_channel_not_configured"}, 503)
        return

    target = phone if channel == "sms" else email
    target_key = f"{channel}:{target}"

    if not _rate_ok(f"otp-req:{target_key}", OTP_REQUEST_LIMIT, OTP_REQUEST_WINDOW):
        _public_json(handler, {"ok": False, "error": "too_many_requests"}, 429)
        return

    code = f"{secrets.randbelow(900000) + 100000:06d}"
    with _lock:
        _otp_store[target_key] = {
            "code": code,
            "expires_at": time.time() + OTP_TTL_SEC,
            "attempts": 0,
            "phone": phone,
            "email": email,
        }

    try:
        if channel == "sms":
            _send_otp_sms(phone, code)
        else:
            _send_otp_email(email, code)
    except Exception as exc:
        with _lock:
            _otp_store.pop(target_key, None)
        print(f"[public-api] OTP send failed ({channel}): {exc}")
        _public_json(handler, {"ok": False, "error": "otp_send_failed"}, 502)
        return

    masked = _mask_phone(phone) if channel == "sms" else _mask_email(email)
    _public_json(handler, {"ok": True, "channel": channel, "masked_target": masked})


def _handle_verify_otp(handler, data: dict, ip: str) -> None:
    phone = _normalize_phone(data.get("phone", ""))
    email = (data.get("email", "") or "").strip().lower()
    code = (data.get("code", "") or "").strip()

    if not code or (not phone and not email):
        _public_json(handler, {"ok": False, "error": "phone_or_email_and_code_required"}, 400)
        return

    # Find the OTP entry by either target key.
    candidates = []
    if phone:
        candidates.append(f"sms:{phone}")
    if email:
        candidates.append(f"email:{email}")

    entry_key = None
    entry = None
    with _lock:
        for key in candidates:
            ent = _otp_store.get(key)
            if ent and ent.get("phone") == phone and ent.get("email") == email:
                entry_key, entry = key, ent
                break

    if not entry:
        _public_json(handler, {"ok": False, "error": "otp_not_found_or_expired"}, 400)
        return

    now = time.time()
    if now > entry["expires_at"]:
        with _lock:
            _otp_store.pop(entry_key, None)
        _public_json(handler, {"ok": False, "error": "otp_expired"}, 400)
        return

    if entry["attempts"] >= OTP_MAX_ATTEMPTS:
        with _lock:
            _otp_store.pop(entry_key, None)
        _public_json(handler, {"ok": False, "error": "too_many_attempts"}, 429)
        return

    if not secrets.compare_digest(code, entry["code"]):
        with _lock:
            entry["attempts"] += 1
            if entry["attempts"] >= OTP_MAX_ATTEMPTS:
                _otp_store.pop(entry_key, None)
        _public_json(handler, {"ok": False, "error": "invalid_code"}, 400)
        return

    # Success: consume OTP, issue single-use verification token.
    token = secrets.token_urlsafe(32)
    with _lock:
        _otp_store.pop(entry_key, None)
        _verify_tokens[token] = {
            "phone": phone,
            "email": email,
            "expires_at": now + VERIFY_TOKEN_TTL_SEC,
        }
    _public_json(handler, {"ok": True, "verify_token": token})


def _handle_public_lead(handler, data: dict, ip: str) -> None:
    # Honeypot: real users leave this empty.
    if (data.get("website", "") or "").strip():
        _public_json(handler, {"ok": True, "lead_id": None})
        return

    if not _rate_ok(f"lead:{ip}", LEAD_SUBMIT_LIMIT, LEAD_SUBMIT_WINDOW):
        _public_json(handler, {"ok": False, "error": "too_many_requests"}, 429)
        return

    name = (data.get("name", "") or "").strip()
    phone = _normalize_phone(data.get("phone", ""))
    email = (data.get("email", "") or "").strip().lower()
    verify_token = (data.get("verify_token", "") or "").strip()

    if not name or not phone or not email or not verify_token:
        _public_json(handler, {"ok": False, "error": "name_phone_email_token_required"}, 400)
        return
    if not _valid_phone(phone):
        _public_json(handler, {"ok": False, "error": "invalid_phone"}, 400)
        return
    if not _valid_email(email):
        _public_json(handler, {"ok": False, "error": "invalid_email"}, 400)
        return

    with _lock:
        token_entry = _verify_tokens.pop(verify_token, None)
    if not token_entry or time.time() > token_entry["expires_at"]:
        _public_json(handler, {"ok": False, "error": "verification_required"}, 403)
        return
    if token_entry["phone"] != phone or token_entry["email"] != email:
        _public_json(handler, {"ok": False, "error": "verification_mismatch"}, 403)
        return

    if create_or_update_lead is None:
        _public_json(handler, {"ok": False, "error": "server_misconfigured"}, 500)
        return

    try:
        existing = find_duplicate_lead(phone=phone, email=email)
        lead = create_or_update_lead(
            name=name,
            phone=phone,
            email=email,
            country=(data.get("country", "") or "").strip(),
            course_interest=(data.get("course_interest", "") or "").strip(),
            message=(data.get("message", "") or "").strip(),
            source="Website",
        )
        if not isinstance(lead, dict) or not lead.get("lead_id"):
            _public_json(handler, {"ok": False, "error": "could_not_save_lead"}, 500)
            return
        if existing is None:
            tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
            update_lead(lead["lead_id"], follow_up_date=tomorrow)
            lead = get_lead(lead["lead_id"]) or lead
        _public_json(handler, {
            "ok": True,
            "lead_id": lead.get("lead_id"),
            "created": existing is None,
        })
    except Exception as exc:
        print(f"[public-api] lead save failed: {exc}")
        _public_json(handler, {"ok": False, "error": "server_error"}, 500)


# --------------------------------------------------------------------------
# Router (called from the main Handler)
# --------------------------------------------------------------------------

def handle_public_post(handler) -> None:
    path = urlparse(handler.path).path
    data = _read_json_body(handler)
    ip = _client_ip(handler)

    if path == "/api/public/request-otp":
        _handle_request_otp(handler, data, ip)
    elif path == "/api/public/verify-otp":
        _handle_verify_otp(handler, data, ip)
    elif path == "/api/public/lead":
        _handle_public_lead(handler, data, ip)
    else:
        _public_json(handler, {"ok": False, "error": "not_found"}, 404)
