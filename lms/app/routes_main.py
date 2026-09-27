"""Public routes: landing, catalog, course detail, recordings, enrollment & payments."""
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
    courses = Course.query.filter_by(is_bonus=False).order_by(Course.title).all()
    return render_template("courses.html", courses=courses)


@main_bp.route("/bonus-courses")
def bonus_courses():
    courses = Course.query.filter_by(is_bonus=True).order_by(Course.title).all()
    return render_template("bonus.html", courses=courses)


@main_bp.route("/course/<slug>")
def course_detail(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    enrollment = None
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id).first()
    return render_template("course_detail.html", course=course, enrollment=enrollment)


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
    flash("Payment successful — you are enrolled!", "success")
    return redirect(url_for("student.dashboard"))
