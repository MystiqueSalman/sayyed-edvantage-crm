"""Admin routes: dashboard, users, course catalog admin, coupons, enrollments.
Manager gets dashboard + course/enrollment views; user management & coupons are
admin-only."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from . import db
from .decorators import admin_required, manager_or_admin
from .models import (Assignment, Certificate, Course, Enrollment, Submission, User,
                     ROLES)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@manager_or_admin
def dashboard():
    stats = {
        "users": User.query.count(),
        "courses": Course.query.count(),
        "enrollments": Enrollment.query.count(),
        "certificates": Certificate.query.count(),
        "revenue": db.session.query(func.coalesce(func.sum(Enrollment.amount_paid), 0))
                 .filter_by(paid=True).scalar(),
        "pending_submissions": Submission.query.filter_by(grade=None).count(),
    }
    recent = (Enrollment.query.order_by(Enrollment.enrolled_at.desc()).limit(8).all())
    return render_template("admin_dashboard.html", stats=stats, recent=recent)


# ---------------------------------------------------------------- users (admin only)
@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "student")
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6 or role not in ROLES:
            flash("All fields required (password min 6 chars, valid role).", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
        else:
            u = User(name=name, email=email, role=role)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash(f"User {email} created as {role}.", "success")
        return redirect(url_for("admin.users"))
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=all_users, roles=ROLES,
                           current_id=current_user.id)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"{user.email} {'activated' if user.is_active else 'deactivated'}.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def user_role(user_id):
    user = User.query.get_or_404(user_id)
    role = request.form.get("role", "")
    if role in ROLES and user.id != current_user.id:
        user.role = role
        db.session.commit()
        flash(f"{user.email} is now {role}.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------- courses (admin + manager)
@admin_bp.route("/courses", methods=["GET", "POST"])
@manager_or_admin
def courses():
    if request.method == "POST":
        if not current_user.is_admin():
            flash("Only admins can create courses.", "danger")
            return redirect(url_for("admin.courses"))
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip().lower().replace(" ", "-")
        if not title or not slug:
            flash("Title and slug are required.", "danger")
        elif Course.query.filter_by(slug=slug).first():
            flash("Slug already in use.", "danger")
        else:
            try:
                fee = int(request.form.get("fee", 0) or 0)
            except ValueError:
                fee = 0
            db.session.add(Course(
                title=title, slug=slug,
                short_desc=request.form.get("short_desc", ""),
                description=request.form.get("description", ""),
                fee=fee,
                is_bonus=bool(request.form.get("is_bonus")),
                banner=request.form.get("banner", ""),
                instructor_id=int(request.form.get("instructor_id") or 0) or None))
            db.session.commit()
            flash("Course created.", "success")
        return redirect(url_for("admin.courses"))
    all_courses = Course.query.order_by(Course.title).all()
    faculty = User.query.filter_by(role="faculty", is_active=True).all()
    return render_template("admin_courses.html", courses=all_courses, faculty=faculty)


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@manager_or_admin
def course_edit(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        course.title = request.form.get("title", "").strip() or course.title
        course.short_desc = request.form.get("short_desc", "")
        course.description = request.form.get("description", "")
        try:
            course.fee = int(request.form.get("fee", course.fee) or 0)
        except ValueError:
            pass
        course.is_bonus = bool(request.form.get("is_bonus"))
        course.banner = request.form.get("banner", "")
        if current_user.is_admin():  # only admin reassigns instructors
            course.instructor_id = int(request.form.get("instructor_id") or 0) or None
        db.session.commit()
        flash("Course updated.", "success")
        return redirect(url_for("admin.courses"))
    faculty = User.query.filter_by(role="faculty", is_active=True).all()
    return render_template("admin_course_edit.html", course=course, faculty=faculty)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@admin_required
def course_delete(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash("Course deleted.", "info")
    return redirect(url_for("admin.courses"))


# ---------------------------------------------------------------- coupons (admin only)
@admin_bp.route("/coupons", methods=["GET", "POST"])
@admin_required
def coupons():
    from .models import Coupon
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        try:
            pct = int(request.form.get("percent_off", 10) or 10)
        except ValueError:
            pct = 10
        if not code:
            flash("Code is required.", "danger")
        elif Coupon.query.filter_by(code=code).first():
            flash("Code already exists.", "danger")
        else:
            db.session.add(Coupon(code=code, percent_off=max(1, min(100, pct)),
                                  active=bool(request.form.get("active"))))
            db.session.commit()
            flash(f"Coupon {code} created.", "success")
        return redirect(url_for("admin.coupons"))
    all_coupons = Coupon.query.order_by(Coupon.code).all()
    return render_template("admin_coupons.html", coupons=all_coupons)


@admin_bp.route("/coupons/<int:coupon_id>/toggle", methods=["POST"])
@admin_required
def coupon_toggle(coupon_id):
    from .models import Coupon
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.active = not coupon.active
    db.session.commit()
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<int:coupon_id>/delete", methods=["POST"])
@admin_required
def coupon_delete(coupon_id):
    from .models import Coupon
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    flash("Coupon deleted.", "info")
    return redirect(url_for("admin.coupons"))


# ---------------------------------------------------------------- enrollments (admin + manager)
@admin_bp.route("/enrollments")
@manager_or_admin
def enrollments():
    items = Enrollment.query.order_by(Enrollment.enrolled_at.desc()).limit(100).all()
    return render_template("admin_enrollments.html", enrollments=items)
