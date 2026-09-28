"""Public routes: landing, catalog, course detail, recordings, enrollment & payments."""
import os
from datetime import timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import current_user, login_required

from . import db
from .models import Course, Enrollment, Coupon
from . import payments

main_bp = Blueprint("main", __name__)


@main_bp.route("/files/<path:filename>")
@login_required
def uploaded_file(filename):
    """Serve user-uploaded files (lesson PDFs). Login required."""
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)


@main_bp.route("/")
def index():
    courses = Course.query.filter_by(is_bonus=False).order_by(Course.fee.desc()).all()
    bonus = Course.query.filter_by(is_bonus=True).all()
    return render_template("index.html", courses=courses, bonus=bonus)


@main_bp.route("/courses")
def catalog():
    q = request.args.get("q", "").strip()
    query = Course.query.filter_by(is_bonus=False)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Course.title.ilike(like)) | (Course.short_desc.ilike(like)) |
            (Course.description.ilike(like)))
    courses = query.order_by(Course.title).all()
    wishlist_ids = set()
    if current_user.is_authenticated and current_user.role == "student":
        from .models import Wishlist
        wishlist_ids = {w.course_id for w in
                        Wishlist.query.filter_by(user_id=current_user.id).all()}
    return render_template("courses.html", courses=courses, q=q,
                           wishlist_ids=wishlist_ids)


@main_bp.route("/bonus-courses")
def bonus_courses():
    # Bonus courses hidden from public view for now (Salman, 2026-09-28).
    # Restore by rendering bonus.html again when ready.
    return redirect(url_for("main.catalog"))


@main_bp.route("/course/<slug>")
def course_detail(slug):
    from datetime import datetime
    from .models import LiveSession, Review, Wishlist
    course = Course.query.filter_by(slug=slug).first_or_404()
    enrollment = None
    my_review = None
    wishlisted = False
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id).first()
        my_review = Review.query.filter_by(
            user_id=current_user.id, course_id=course.id).first()
        wishlisted = Wishlist.query.filter_by(
            user_id=current_user.id, course_id=course.id).first() is not None
    now = datetime.utcnow()
    live_sessions = (LiveSession.query
                     .filter(LiveSession.course_id == course.id,
                             LiveSession.starts_at >= now - timedelta(hours=3))
                     .order_by(LiveSession.starts_at).all())
    avg_rating, rating_count = course.average_rating
    reviews = (Review.query.filter_by(course_id=course.id)
               .order_by(Review.created_at.desc()).limit(20).all())
    return render_template("course_detail.html", course=course, enrollment=enrollment,
                           live_sessions=live_sessions, now=now,
                           avg_rating=avg_rating, rating_count=rating_count,
                           reviews=reviews, my_review=my_review,
                           wishlisted=wishlisted)


@main_bp.route("/verify/<code>")
def verify_certificate(code):
    """Public certificate verification — no login required."""
    from .models import Certificate
    cert = Certificate.query.filter_by(code=code.strip().upper()).first()
    return render_template("verify.html", cert=cert, code=code.strip().upper())


@main_bp.route("/manifest.json")
def manifest():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"), "manifest.json",
        mimetype="application/manifest+json")


@main_bp.route("/sw.js")
def service_worker():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"), "sw.js",
        mimetype="application/javascript")


@main_bp.route("/course/<slug>/recordings")
def recordings(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    return render_template("recordings.html", course=course)


def _apply_coupon(code, fee):
    code = (code or "").strip().upper()
    if not code:
        return None, 0
    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon or not coupon.active:
        return None, 0
    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        return None, 0
    return coupon, coupon.discount_for(fee)


@main_bp.route("/enroll/<slug>", methods=["GET", "POST"])
@login_required
def enroll(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    existing = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id).first()
    if existing and existing.status != Enrollment.STATUS_PENDING:
        return redirect(url_for("main.course_detail", slug=slug))

    coupon = None
    discount = 0
    if request.method == "POST":
        coupon, discount = _apply_coupon(request.form.get("coupon_code"), course.fee)
        if request.form.get("coupon_code", "").strip() and not coupon:
            flash("Coupon code is invalid or expired.", "warning")

    final_fee = max(0, course.fee - discount)

    if request.method == "POST" and "confirm" in request.form:
        # (Re)create a pending enrollment, then go to checkout
        if existing:
            db.session.delete(existing)
            db.session.flush()
        enrollment = Enrollment(
            user_id=current_user.id, course_id=course.id,
            status=Enrollment.STATUS_PENDING, paid=False,
            amount_paid=final_fee,
            coupon_code=coupon.code if coupon else "",
        )
        db.session.add(enrollment)
        db.session.commit()
        if final_fee == 0:
            enrollment.paid = True
            enrollment.status = Enrollment.STATUS_ACTIVE
            if coupon:
                coupon.used_count += 1
            db.session.commit()
            try:
                from . import hardening as _H
                _H.emit_enrollment(current_user, enrollment)
            except Exception:
                pass  # events must never break enrollment
            try:
                from .emailer import send_enrollment_email
                send_enrollment_email(current_user, enrollment)
            except Exception:
                pass
            try:
                from .growth import maybe_reward_referral
                from .whatsapp import send_enrollment_whatsapp
                maybe_reward_referral(current_user)
                send_enrollment_whatsapp(current_user, enrollment)
            except Exception:
                pass  # growth/WhatsApp must never break enrollment
            try:
                from .marketing import (attribute_enrollment,
                                        record_affiliate_earning)
                attribute_enrollment(enrollment)
                db.session.commit()
                record_affiliate_earning(enrollment)
            except Exception:
                pass  # attribution must never break enrollment
            flash("Enrolled successfully — happy learning!", "success")
            return redirect(url_for("student.dashboard"))
        return redirect(url_for("main.checkout", enrollment_id=enrollment.id))

    return render_template("enroll.html", course=course, coupon=coupon,
                           discount=discount, final_fee=final_fee,
                           payments_live=current_app.config["PAYMENTS_LIVE"])


@main_bp.route("/checkout/<int:enrollment_id>")
@login_required
def checkout(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.user_id != current_user.id:
        return redirect(url_for("main.index"))
    if enrollment.status != Enrollment.STATUS_PENDING:
        return redirect(url_for("student.dashboard"))
    try:
        order = payments.create_order(
            enrollment.amount_paid,
            receipt=f"enr_{enrollment.id}",
            notes={"course": enrollment.course.title, "user": current_user.email},
        )
    except Exception as exc:  # noqa: BLE001 - surface gateway errors cleanly
        flash(f"Payment gateway error: {exc}", "danger")
        return redirect(url_for("main.enroll", slug=enrollment.course.slug))
    enrollment.razorpay_order_id = order["id"]
    db.session.commit()
    return render_template(
        "checkout.html", enrollment=enrollment, order=order,
        key_id=current_app.config["RAZORPAY_KEY_ID"],
    )


@main_bp.route("/payment/confirm/<int:enrollment_id>", methods=["POST"])
@login_required
def payment_confirm(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.user_id != current_user.id:
        return redirect(url_for("main.index"))
    if enrollment.status != Enrollment.STATUS_PENDING:
        return redirect(url_for("student.dashboard"))

    if payments.is_live():
        payment_id = request.form.get("razorpay_payment_id", "")
        signature = request.form.get("razorpay_signature", "")
        order_id = request.form.get("razorpay_order_id", "")
        if not (payment_id and signature and order_id):
            flash("Payment verification data missing.", "danger")
            return redirect(url_for("main.checkout", enrollment_id=enrollment.id))
        if not payments.verify_payment_signature(order_id, payment_id, signature):
            flash("Payment signature verification failed.", "danger")
            return redirect(url_for("main.checkout", enrollment_id=enrollment.id))
        enrollment.razorpay_payment_id = payment_id
    else:
        # Stub/test mode — no real money moves.
        enrollment.razorpay_payment_id = "pay_stub_" + enrollment.razorpay_order_id[-8:]

    enrollment.paid = True
    enrollment.status = Enrollment.STATUS_ACTIVE
    if enrollment.coupon_code:
        coupon = Coupon.query.filter_by(code=enrollment.coupon_code).first()
        if coupon:
            coupon.used_count += 1
    db.session.commit()
    try:
        from . import hardening as _H
        _H.emit_enrollment(current_user, enrollment, payment_completed=True)
    except Exception:
        pass  # events must never break payment confirmation
    try:
        from .emailer import send_enrollment_email
        send_enrollment_email(current_user, enrollment)
    except Exception:
        pass
    try:
        from .growth import maybe_reward_referral
        from .whatsapp import (send_enrollment_whatsapp,
                               send_payment_receipt_whatsapp)
        maybe_reward_referral(current_user)
        send_enrollment_whatsapp(current_user, enrollment)
        send_payment_receipt_whatsapp(current_user, enrollment)
    except Exception:
        pass  # growth/WhatsApp must never break payment confirmation
    try:
        from .marketing import attribute_enrollment, record_affiliate_earning
        attribute_enrollment(enrollment)
        db.session.commit()
        record_affiliate_earning(enrollment)
    except Exception:
        pass  # attribution must never break payment confirmation
    flash("Payment successful — you are enrolled!", "success")
    return redirect(url_for("student.dashboard"))


# ------------------------------------------------- Phase 10: health + SEO (§24.4, §20.6)

@main_bp.route("/health")
def health():
    """Liveness + DB connectivity + disk-space checks (§24.4)."""
    from datetime import datetime as _dt
    from flask import jsonify  # noqa: E402
    from . import hardening as _H  # noqa: E402
    ok, checks = _H.health_checks()
    stats = _H.request_stats()
    return jsonify({
        "status": "ok" if ok else "degraded",
        "version": "phase-11",
        "time": _dt.utcnow().isoformat() + "Z",
        "uptime_seconds": stats["uptime_seconds"],
        "checks": checks,
    }), 200 if ok else 503


@main_bp.route("/sitemap.xml")
def sitemap():
    """XML sitemap: courses + public pages (§20.6)."""
    from flask import Response  # noqa: E402
    base = current_app.config["APP_BASE_URL"].rstrip("/")
    urls = [
        ("/", "weekly", "1.0"),
        ("/courses", "weekly", "0.9"),
        ("/bonus-courses", "weekly", "0.8"),
        ("/jobs", "daily", "0.8"),
        ("/enquiry", "monthly", "0.7"),
        ("/developers", "monthly", "0.5"),
    ]
    for c in Course.query.order_by(Course.id).all():
        urls.append((f"/course/{c.slug}", "weekly", "0.9"))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, freq, prio in urls:
        xml.append(
            f"  <url><loc>{base}{path}</loc>"
            f"<changefreq>{freq}</changefreq>"
            f"<priority>{prio}</priority></url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")


@main_bp.route("/robots.txt")
def robots():
    """Robots file pointing at the sitemap (§20.6)."""
    from flask import Response  # noqa: E402
    base = current_app.config["APP_BASE_URL"].rstrip("/")
    return Response(
        f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n",
        mimetype="text/plain")


@main_bp.route("/developers")
def developers():
    """Versioned developer docs, generated from live routes (§25.5)."""
    from .api_v1 import API_VERSION  # noqa: E402
    from .models import ApiKey, Webhook  # noqa: E402
    routes = []
    for rule in current_app.url_map.iter_rules():
        if not rule.rule.startswith("/api/v1"):
            continue
        if rule.endpoint.startswith("api_v1._v1_"):
            continue  # error handlers, not real endpoints
        view = current_app.view_functions[rule.endpoint]
        doc = (view.__doc__ or "").strip().split("\n")[0]
        routes.append({
            "rule": str(rule),
            "methods": sorted(m for m in rule.methods
                              if m in ("GET", "POST", "PUT", "PATCH",
                                       "DELETE")),
            "endpoint": rule.endpoint,
            "doc": doc,
        })
    routes.sort(key=lambda r: r["rule"])
    return render_template("developers.html", routes=routes,
                           version=API_VERSION,
                           scopes=ApiKey.SCOPES,
                           events=Webhook.EVENTS,
                           base_url=current_app.config[
                               "APP_BASE_URL"].rstrip("/"))
