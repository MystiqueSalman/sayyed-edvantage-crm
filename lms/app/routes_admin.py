"""Admin routes: dashboard, users, course catalog admin, coupons, enrollments,
email settings, announcements, analytics.
Manager gets dashboard + course/enrollment views; user management, coupons,
email settings, announcements and analytics are admin-only."""
from flask import (Blueprint, current_app, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from sqlalchemy import func

from . import db
from .decorators import admin_required, manager_or_admin
from .models import (Announcement, Assignment, Certificate, Course, EmailSettings,
                     Enrollment, QuizAttempt, Submission, User, ROLES)
from .roles13 import EXTENDED_ROLES  # Phase 13: new roles in the user admin

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
    try:
        from .crm import todays_followups
        stats["followups_due"] = len(todays_followups())
    except Exception:
        stats["followups_due"] = 0
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
        if not name or not email or len(password) < 6 or (
                role not in ROLES and role not in EXTENDED_ROLES):
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
    return render_template("admin_users.html", users=all_users,
                           roles=ROLES + EXTENDED_ROLES,
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
        from . import operations as _OPS  # Phase 9: audit log
        _OPS.audit(current_user, "user.toggle", "user", user.id,
                   f"{user.email} -> {'active' if user.is_active else 'inactive'}",
                   request.remote_addr)
        flash(f"{user.email} {'activated' if user.is_active else 'deactivated'}.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def user_role(user_id):
    user = User.query.get_or_404(user_id)
    role = request.form.get("role", "")
    if role in ROLES or role in EXTENDED_ROLES:
        if user.id != current_user.id:
            old = user.role
            user.role = role
            db.session.commit()
            from . import operations as _OPS  # Phase 9: audit log
            _OPS.audit(current_user, "user.role_change", "user", user.id,
                       f"{user.email}: {old} -> {role}", request.remote_addr)
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
        # Phase 10 §20.6: SEO fields
        course.meta_title = request.form.get("meta_title", "").strip()[:160]
        course.meta_description = request.form.get(
            "meta_description", "").strip()[:300]
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
            from . import operations as _OPS  # Phase 9: audit log
            _OPS.audit(current_user, "coupon.create", "coupon", None,
                       f"Created coupon {code} ({pct}% off)",
                       request.remote_addr)
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
    from . import operations as _OPS  # Phase 9: audit log
    _OPS.audit(current_user, "coupon.toggle", "coupon", coupon.id,
               f"{'Activated' if coupon.active else 'Deactivated'} coupon {coupon.code}",
               request.remote_addr)
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<int:coupon_id>/delete", methods=["POST"])
@admin_required
def coupon_delete(coupon_id):
    from .models import Coupon
    coupon = Coupon.query.get_or_404(coupon_id)
    code = coupon.code
    db.session.delete(coupon)
    db.session.commit()
    from . import operations as _OPS  # Phase 9: audit log
    _OPS.audit(current_user, "coupon.delete", "coupon", coupon_id,
               f"Deleted coupon {code}", request.remote_addr)
    flash("Coupon deleted.", "info")
    return redirect(url_for("admin.coupons"))


# ---------------------------------------------------------------- enrollments (admin + manager)
@admin_bp.route("/enrollments")
@manager_or_admin
def enrollments():
    items = Enrollment.query.order_by(Enrollment.enrolled_at.desc()).limit(100).all()
    return render_template("admin_enrollments.html", enrollments=items)


# ---------------------------------------------------------------- email settings (admin only)
@admin_bp.route("/email-settings", methods=["GET", "POST"])
@admin_required
def email_settings():
    settings = EmailSettings.get()
    if request.method == "POST":
        if "send_test" in request.form:
            from .emailer import send_email_sync
            to = request.form.get("test_email", "").strip() or settings.from_email
            ok, msg = send_email_sync(
                to, "Sayyed EdVantage LMS — test email ✅",
                "<p>This is a test email from your LMS. Email automation is working.</p>")
            flash(msg, "success" if ok else "danger")
        else:
            settings.smtp_host = request.form.get("smtp_host", "").strip()
            try:
                settings.smtp_port = int(request.form.get("smtp_port", 587) or 587)
            except ValueError:
                settings.smtp_port = 587
            settings.smtp_user = request.form.get("smtp_user", "").strip()
            if request.form.get("smtp_pass"):
                settings.smtp_pass = request.form.get("smtp_pass")
            settings.from_email = request.form.get("from_email", "").strip()
            settings.from_name = (request.form.get("from_name", "").strip()
                                  or "Sayyed EdVantage LMS")
            settings.enabled = bool(request.form.get("enabled"))
            db.session.commit()
            flash("Email settings saved.", "success")
        return redirect(url_for("admin.email_settings"))
    return render_template("admin_email_settings.html", settings=settings)


# ---------------------------------------------------------------- announcements (admin only)
@admin_bp.route("/announcements", methods=["GET", "POST"])
@admin_required
def announcements():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title:
            flash("Title is required.", "danger")
        else:
            if request.form.get("deactivate_others"):
                Announcement.query.update({"active": False})
            batch_id = request.form.get("batch_id", type=int) or None
            db.session.add(Announcement(title=title, body=body,
                                        active=bool(request.form.get("active")),
                                        batch_id=batch_id))
            db.session.commit()
            from . import operations as _OPS  # Phase 9: audit log
            _OPS.audit(current_user, "announcement.create", "announcement",
                       None, f"Posted announcement '{title}'",
                       request.remote_addr)
            flash("Announcement posted.", "success")
        return redirect(url_for("admin.announcements"))
    items = Announcement.query.order_by(Announcement.created_at.desc()).limit(20).all()
    from .models import Batch
    batches = Batch.query.order_by(Batch.name).all()
    return render_template("admin_announcements.html", announcements=items,
                           batches=batches)


@admin_bp.route("/announcements/<int:ann_id>/toggle", methods=["POST"])
@admin_required
def announcement_toggle(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    ann.active = not ann.active
    db.session.commit()
    from . import operations as _OPS  # Phase 9: audit log
    _OPS.audit(current_user, "announcement.toggle", "announcement", ann.id,
               f"'{ann.title}' -> {'active' if ann.active else 'inactive'}",
               request.remote_addr)
    return redirect(url_for("admin.announcements"))


@admin_bp.route("/announcements/<int:ann_id>/delete", methods=["POST"])
@admin_required
def announcement_delete(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    title = ann.title
    db.session.delete(ann)
    db.session.commit()
    from . import operations as _OPS  # Phase 9: audit log
    _OPS.audit(current_user, "announcement.delete", "announcement", ann_id,
               f"Deleted announcement '{title}'", request.remote_addr)
    flash("Announcement deleted.", "info")
    return redirect(url_for("admin.announcements"))


# ---------------------------------------------------------------- analytics (admin only)
@admin_bp.route("/analytics")
@admin_required
def analytics():
    return render_template("admin_analytics.html")


@admin_bp.route("/analytics/api/enrollments-per-course")
@admin_required
def api_enrollments_per_course():
    rows = (db.session.query(Course.title, func.count(Enrollment.id))
            .outerjoin(Enrollment, Enrollment.course_id == Course.id)
            .group_by(Course.id).order_by(Course.title).all())
    return jsonify({"labels": [r[0] for r in rows],
                    "data": [r[1] for r in rows]})


@admin_bp.route("/analytics/api/revenue-per-course")
@admin_required
def api_revenue_per_course():
    rows = (db.session.query(
                Course.title,
                func.coalesce(func.sum(Enrollment.amount_paid), 0))
            .outerjoin(Enrollment,
                       (Enrollment.course_id == Course.id) & (Enrollment.paid.is_(True)))
            .group_by(Course.id).order_by(Course.title).all())
    return jsonify({"labels": [r[0] for r in rows],
                    "data": [int(r[1]) for r in rows],
                    "test_mode": not current_app.config.get("PAYMENTS_LIVE")})


@admin_bp.route("/analytics/api/quiz-scores")
@admin_required
def api_quiz_scores():
    from .models import Module, Quiz
    rows = (db.session.query(
                Course.title,
                func.avg(QuizAttempt.score * 100.0 / QuizAttempt.total))
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .join(Module, Module.id == Quiz.module_id)
            .join(Course, Course.id == Module.course_id)
            .filter(QuizAttempt.total > 0)
            .group_by(Course.id).order_by(Course.title).all())
    return jsonify({"labels": [r[0] for r in rows],
                    "data": [round(float(r[1]), 1) if r[1] else 0 for r in rows]})


@admin_bp.route("/analytics/api/signups-30d")
@admin_required
def api_signups_30d():
    from datetime import date, timedelta
    today = date.today()
    labels, data = [], []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        nxt = day + timedelta(days=1)
        n = User.query.filter(User.created_at >= day,
                              User.created_at < nxt).count()
        labels.append(day.strftime("%d %b"))
        data.append(n)
    return jsonify({"labels": labels, "data": data})


# ------------------------------------------------- Phase 5: AI settings
@admin_bp.route("/ai-settings", methods=["GET", "POST"])
@admin_required
def ai_settings():
    """AI sales agent + AI tutor configuration (single-row AISettings)."""
    from .models import AISettings, Course
    settings = AISettings.get()
    if request.method == "POST":
        settings.enabled = bool(request.form.get("enabled"))
        settings.model = request.form.get("model", "gpt-4o-mini").strip() or "gpt-4o-mini"
        settings.tutor_enabled = bool(request.form.get("tutor_enabled"))
        try:
            settings.tutor_daily_limit = max(
                1, min(200, int(request.form.get("tutor_daily_limit", 30) or 30)))
        except ValueError:
            settings.tutor_daily_limit = 30
        # per-course tutor toggles: checkbox present => enabled
        for course in Course.query.all():
            course.ai_tutor_enabled = bool(
                request.form.get(f"tutor_course_{course.id}"))
        db.session.commit()
        flash("AI settings saved.", "success")
        return redirect(url_for("admin.ai_settings"))
    courses = Course.query.order_by(Course.title).all()
    return render_template("admin_ai_settings.html", settings=settings,
                           courses=courses)


# ------------------------------------------------- Phase 8: gamification
@admin_bp.route("/gamification", methods=["GET", "POST"])
@admin_required
def gamification():
    """Point values per activity + bonus rates + one-time backfill (§15.2)."""
    from . import gamification as G
    from .models import GamificationSetting, PointSetting
    G.ensure_gamification_defaults()
    if request.method == "POST":
        if request.form.get("run_backfill"):
            stats = G.run_backfill(force=True)
            flash(f"Backfill complete: {stats.get('users', 0)} students, "
                  f"{stats.get('transactions', 0)} point records, "
                  f"{stats.get('badges', 0)} badges.", "success")
            return redirect(url_for("admin.gamification"))
        for action in list(G.POINT_DEFAULTS):
            row = PointSetting.query.filter_by(action=action).first()
            if not row:
                continue
            try:
                row.points = max(0, int(request.form.get(
                    f"points_{action}", row.points) or 0))
            except ValueError:
                pass
        for setting_action, default in (
                (G.QUIZ_BONUS_RATE_SETTING, 0.2),
                (G.PROJECT_BONUS_RATE_SETTING, 0.3)):
            row = PointSetting.query.filter_by(action=setting_action).first()
            if row:
                try:
                    rate = float(request.form.get(setting_action, default)
                                 or default)
                    row.label = f"rate:{max(0.0, min(2.0, rate))}"
                except ValueError:
                    pass
        db.session.commit()
        flash("Point values saved — they apply to future awards.", "success")
        return redirect(url_for("admin.gamification"))
    settings = PointSetting.query.order_by(PointSetting.action).all()
    quiz_rate = G.bonus_rate(G.QUIZ_BONUS_RATE_SETTING, 0.2)
    proj_rate = G.bonus_rate(G.PROJECT_BONUS_RATE_SETTING, 0.3)
    backfill = GamificationSetting.get()
    return render_template("admin_gamification.html", settings=settings,
                           actions=G.POINT_DEFAULTS, quiz_rate=quiz_rate,
                           proj_rate=proj_rate, backfill_done=backfill.backfill_done)


@admin_bp.route("/gamification/badges", methods=["GET", "POST"])
@admin_required
def badge_list():
    """Badge definitions: create + toggle (§15.1)."""
    from .models import Badge, Course
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        criterion = request.form.get("criterion", "").strip()
        if not name or not criterion:
            flash("Name and criterion are required.", "danger")
        else:
            try:
                threshold = float(request.form.get("threshold", 1) or 1)
            except ValueError:
                threshold = 1.0
            course_id = request.form.get("course_id", type=int) or None
            db.session.add(Badge(
                name=name[:80], icon=request.form.get("icon", "🏅").strip() or "🏅",
                description=request.form.get("description", "").strip()[:200],
                criterion=criterion, threshold=threshold,
                course_id=course_id))
            db.session.commit()
            flash(f"Badge '{name}' created.", "success")
        return redirect(url_for("admin.badge_list"))
    badges = Badge.query.order_by(Badge.is_system.desc(), Badge.id).all()
    courses = Course.query.order_by(Course.title).all()
    criteria = ["lessons_completed", "quizzes_attempted", "quiz_mastery",
                "courses_completed", "project_star", "projects_evaluated",
                "streak_days", "discussion_posts", "interviews_completed",
                "resume_complete", "points_total"]
    return render_template("admin_badges.html", badges=badges,
                           courses=courses, criteria=criteria)


@admin_bp.route("/gamification/badges/<int:badge_id>/edit",
                methods=["GET", "POST"])
@admin_required
def badge_edit(badge_id):
    from .models import Badge, Course
    badge = Badge.query.get_or_404(badge_id)
    if request.method == "POST":
        if badge.is_system and request.form.get("criterion", "").strip() != badge.criterion:
            flash("System badge criteria can't be changed.", "warning")
            return redirect(url_for("admin.badge_edit", badge_id=badge.id))
        badge.name = request.form.get("name", "").strip()[:80] or badge.name
        badge.icon = request.form.get("icon", "🏅").strip() or "🏅"
        badge.description = request.form.get("description", "").strip()[:200]
        if not badge.is_system:
            badge.criterion = request.form.get("criterion", "").strip() or badge.criterion
        try:
            badge.threshold = float(request.form.get("threshold", 1) or 1)
        except ValueError:
            pass
        badge.course_id = request.form.get("course_id", type=int) or None
        db.session.commit()
        flash("Badge updated.", "success")
        return redirect(url_for("admin.badge_list"))
    courses = Course.query.order_by(Course.title).all()
    criteria = ["lessons_completed", "quizzes_attempted", "quiz_mastery",
                "courses_completed", "project_star", "projects_evaluated",
                "streak_days", "discussion_posts", "interviews_completed",
                "resume_complete", "points_total"]
    return render_template("admin_badge_form.html", badge=badge,
                           courses=courses, criteria=criteria)


@admin_bp.route("/gamification/badges/<int:badge_id>/toggle",
                methods=["POST"])
@admin_required
def badge_toggle(badge_id):
    from .models import Badge
    badge = Badge.query.get_or_404(badge_id)
    badge.is_active = not badge.is_active
    db.session.commit()
    flash(f"Badge '{badge.name}' "
          f"{'activated' if badge.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.badge_list"))
