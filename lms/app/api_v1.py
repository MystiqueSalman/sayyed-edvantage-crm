"""Phase 10 — versioned REST API (§25.1, §25.4).

``/api/v1`` with API-key auth (admin issues keys at /admin/api-keys),
per-key scopes and per-key rate limiting. Consistent error envelope::

    {"error": {"code": "...", "message": "..."}}

Note: the pre-existing ``/api/*`` agent-API routes belong to the separate
agent-api Railway service — this blueprint only serves ``/api/v1``.
"""
import hashlib
import json
import secrets
import time
from datetime import datetime
from functools import wraps

from flask import Blueprint, g, jsonify, request

from . import db
from .models import (ApiKey, Batch, Certificate, Course, Enrollment, Lead,
                     Quiz, QuizAttempt, User)

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

API_VERSION = "1"


# ------------------------------------------------------------ error envelope

def api_error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


# --------------------------------------------------------------- key issuing

def generate_raw_key():
    """Create a new raw API key (shown once, never stored)."""
    return "se_live_" + secrets.token_urlsafe(32)


def hash_key(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_key(name, scopes, rate_limit_per_min=300, created_by_id=None):
    """Mint an ApiKey row; returns (row, raw_key)."""
    raw = generate_raw_key()
    row = ApiKey(name=name or "", key_prefix=raw[:16],
                 key_hash=hash_key(raw),
                 rate_limit_per_min=int(rate_limit_per_min or 300),
                 created_by_id=created_by_id)
    row.scopes = scopes
    db.session.add(row)
    db.session.commit()
    return row, raw


def _presented_key():
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-API-Key", "").strip()


# ------------------------------------------------------------- rate limiting
# In-memory sliding window per key (per worker process). Documented on
# /developers as a known single-process limitation.

_rate_buckets = {}  # key_id -> [timestamps]


def _check_rate_limit(key):
    limit = key.rate_limit_per_min or 300
    now = time.time()
    bucket = _rate_buckets.get(key.id, [])
    bucket = [t for t in bucket if now - t < 60]
    if len(bucket) >= limit:
        retry_after = max(1, int(60 - (now - bucket[0])))
        _rate_buckets[key.id] = bucket
        return retry_after
    bucket.append(now)
    _rate_buckets[key.id] = bucket
    return 0


def require_api_key(*scopes):
    """Authenticate the request and enforce scopes + rate limit."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            raw = _presented_key()
            if not raw:
                return api_error("missing_api_key",
                                 "Provide an API key via Authorization: "
                                 "Bearer <key> or X-API-Key.", 401)
            key = ApiKey.query.filter_by(
                key_hash=hash_key(raw), is_active=True).first()
            if not key:
                return api_error("invalid_api_key",
                                 "API key is invalid or revoked.", 401)
            retry_after = _check_rate_limit(key)
            if retry_after:
                resp = api_error("rate_limited",
                                 "Rate limit exceeded. Slow down.", 429)
                resp[0].headers["Retry-After"] = str(retry_after)
                return resp
            missing = [s for s in scopes if not key.has_scope(s)]
            if missing:
                return api_error("insufficient_scope",
                                 "Key lacks required scope(s): "
                                 + ", ".join(missing), 403)
            g.api_key = key
            try:
                key.last_used_at = datetime.utcnow()
                db.session.commit()
            except Exception:
                db.session.rollback()
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# --------------------------------------------------------------- serializers

def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def ser_course(c):
    return {"id": c.id, "title": c.title, "slug": c.slug, "fee": c.fee,
            "short_desc": c.short_desc or "", "is_bonus": bool(c.is_bonus),
            "meta_title": c.meta_title or "",
            "meta_description": c.meta_description or ""}


def ser_enrollment(e):
    return {"id": e.id, "user_id": e.user_id,
            "course_id": e.course_id,
            "course_title": e.course.title if e.course else "",
            "status": e.status, "paid": bool(e.paid),
            "amount_paid": e.amount_paid or 0,
            "enrolled_at": _iso(e.enrolled_at)}


def paginate(query):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 50, type=int)))
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"page": page, "per_page": per_page, "total": total,
            "items": items}


# ---------------------------------------------------------------- endpoints

@api_v1_bp.route("/courses")
@require_api_key("courses.read")
def courses():
    q = Course.query.order_by(Course.id)
    data = paginate(q)
    data["items"] = [ser_course(c) for c in data["items"]]
    return jsonify({"version": API_VERSION, **data})


@api_v1_bp.route("/courses/<int:course_id>")
@require_api_key("courses.read")
def course_detail(course_id):
    c = db.session.get(Course, course_id)
    if not c:
        return api_error("not_found", "Course not found.", 404)
    out = ser_course(c)
    out["modules"] = [{"id": m.id, "title": m.title,
                       "lessons": [{"id": l.id, "title": l.title}
                                   for l in m.lessons]}
                      for m in c.modules]
    out["quiz_count"] = len(c.quizzes)
    return jsonify(out)


@api_v1_bp.route("/enrollments")
@require_api_key("enrollments.read")
def enrollments():
    q = Enrollment.query.order_by(Enrollment.id.desc())
    if request.args.get("course_id", type=int):
        q = q.filter_by(course_id=request.args.get("course_id", type=int))
    if request.args.get("status"):
        q = q.filter_by(status=request.args.get("status"))
    data = paginate(q)
    data["items"] = [ser_enrollment(e) for e in data["items"]]
    return jsonify({"version": API_VERSION, **data})


@api_v1_bp.route("/quizzes/<int:quiz_id>/attempts")
@require_api_key("quizzes.read")
def quiz_attempts(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return api_error("not_found", "Quiz not found.", 404)
    q = (QuizAttempt.query.filter_by(quiz_id=quiz_id)
         .filter(QuizAttempt.submitted_at.isnot(None))
         .order_by(QuizAttempt.submitted_at.desc()))
    data = paginate(q)
    data["items"] = [{"id": a.id, "quiz_id": a.quiz_id,
                      "user_id": a.user_id,
                      "user_name": a.user.name if a.user else "",
                      "score": a.score, "total": a.total,
                      "percent": a.percent,
                      "submitted_at": _iso(a.submitted_at)}
                     for a in data["items"]]
    return jsonify({"version": API_VERSION, **data})


@api_v1_bp.route("/leads", methods=["GET"])
@require_api_key("leads.read")
def leads():
    q = Lead.query.order_by(Lead.id.desc())
    if request.args.get("status"):
        q = q.filter_by(status=request.args.get("status"))
    data = paginate(q)
    data["items"] = [{"id": l.id, "name": l.name, "phone": l.phone,
                      "email": l.email or "", "source": l.source,
                      "status": l.status, "score": l.score,
                      "course_id": l.course_id,
                      "created_at": _iso(l.created_at)}
                     for l in data["items"]]
    return jsonify({"version": API_VERSION, **data})


@api_v1_bp.route("/leads", methods=["POST"])
@require_api_key("leads.write")
def lead_create():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    if not phone:
        return api_error("validation_error",
                         "Field 'phone' is required.", 422)
    from .crm import create_lead
    try:
        lead = create_lead(
            name=name, phone=phone,
            email=(payload.get("email") or "").strip(),
            source=Lead.SOURCE_MANUAL,
            course_id=payload.get("course_id"),
            note="Created via REST API v1")
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return api_error("server_error", str(exc)[:200], 500)
    return jsonify({"id": lead.id, "name": lead.name, "phone": lead.phone,
                    "status": lead.status}), 201


@api_v1_bp.route("/batches")
@require_api_key("batches.read")
def batches():
    q = Batch.query.order_by(Batch.id.desc())
    data = paginate(q)
    data["items"] = [{"id": b.id, "name": b.name,
                      "course_id": b.course_id,
                      "course_title": b.course.title if b.course else "",
                      "capacity": b.capacity,
                      "member_count": len(b.members),
                      "start_date": b.start_date.isoformat()
                      if b.start_date else None,
                      "end_date": b.end_date.isoformat()
                      if b.end_date else None}
                     for b in data["items"]]
    return jsonify({"version": API_VERSION, **data})


@api_v1_bp.route("/payments")
@require_api_key("payments.read")
def payments():
    q = (Enrollment.query.filter_by(paid=True)
         .order_by(Enrollment.enrolled_at.desc()))
    data = paginate(q)
    data["items"] = [{"id": e.id, "user_id": e.user_id,
                      "user_email": e.user.email if e.user else "",
                      "course_id": e.course_id,
                      "course_title": e.course.title if e.course else "",
                      "amount_paid": e.amount_paid or 0,
                      "razorpay_payment_id": e.razorpay_payment_id or "",
                      "paid_at": _iso(e.enrolled_at)}
                     for e in data["items"]]
    return jsonify({"version": API_VERSION, **data})


@api_v1_bp.route("/certificates/verify/<code>")
@require_api_key("certificates.verify")
def certificate_verify(code):
    cert = Certificate.query.filter_by(code=(code or "").strip()).first()
    if not cert:
        return jsonify({"valid": False, "code": code})
    return jsonify({"valid": True, "code": cert.code,
                    "user_name": cert.user.name if cert.user else "",
                    "course_title": cert.course.title if cert.course else "",
                    "issued_at": _iso(cert.issued_at)})


# JSON 404/405 inside /api/v1 keep the envelope
@api_v1_bp.errorhandler(404)
def _v1_404(_e):
    return api_error("not_found", "Unknown /api/v1 endpoint.", 404)


@api_v1_bp.errorhandler(405)
def _v1_405(_e):
    return api_error("method_not_allowed",
                     "Method not allowed for this endpoint.", 405)
