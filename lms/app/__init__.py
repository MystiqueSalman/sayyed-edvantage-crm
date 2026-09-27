"""Sayyed EdVantage LMS — application factory."""
import os
import threading
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"
migrate = Migrate()


def _database_uri(app):
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):  # SQLAlchemy 2.x needs postgresql://
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    sqlite_path = os.environ.get("SQLITE_PATH", "").strip()
    if not sqlite_path:
        os.makedirs(app.instance_path, exist_ok=True)
        sqlite_path = os.path.join(app.instance_path, "lms.db")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)), exist_ok=True)
    return f"sqlite:///{sqlite_path}"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri(app)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB uploads

    upload_dir = os.environ.get("UPLOAD_DIR", "").strip() or os.path.join(
        os.path.dirname(app.instance_path), "uploads"
    )
    os.makedirs(upload_dir, exist_ok=True)
    app.config["UPLOAD_DIR"] = upload_dir
    app.config["RAZORPAY_KEY_ID"] = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    app.config["RAZORPAY_KEY_SECRET"] = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    app.config["PAYMENTS_LIVE"] = bool(
        app.config["RAZORPAY_KEY_ID"] and app.config["RAZORPAY_KEY_SECRET"]
    )
    app.config["APP_BASE_URL"] = os.environ.get("APP_BASE_URL", "http://localhost:5000")

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    from .models import User  # noqa: E402

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        from .models import Announcement  # noqa: E402
        announcement = (Announcement.query.filter_by(active=True)
                        .order_by(Announcement.created_at.desc()).first())
        return {"now": datetime.utcnow(), "payments_live": app.config["PAYMENTS_LIVE"],
                "announcement": announcement}

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404

    # Blueprints
    from .routes_auth import auth_bp  # noqa: E402
    from .routes_main import main_bp  # noqa: E402
    from .routes_student import student_bp  # noqa: E402
    from .routes_faculty import faculty_bp  # noqa: E402
    from .routes_admin import admin_bp  # noqa: E402
    from .routes_manage import manage_bp  # noqa: E402
    from .routes_discuss import discuss_bp  # noqa: E402
    from .routes_growth import growth_bp  # noqa: E402
    from .routes_crm import crm_bp  # noqa: E402  (Phase 4: CRM/admissions)
    from .routes_tutor import tutor_bp  # noqa: E402  (Phase 5: AI tutor/planner)
    from .routes_career import career_bp  # noqa: E402  (Phase 7: career/placements)
    from .routes_game import game_bp  # noqa: E402  (Phase 8: gamification)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(discuss_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(tutor_bp)
    app.register_blueprint(career_bp)
    app.register_blueprint(game_bp)

    with app.app_context():
        if os.environ.get("LMS_SKIP_CREATE_ALL") != "1":
            db.create_all()  # ensures tables exist (Alembic migrations for upgrades)
        _ensure_schema_patches(app)
        # Phase 8: gamification defaults + one-time backfill (guarded).
        # Skipped when the gamification tables don't exist yet (e.g. while
        # `flask db upgrade` is still running the Phase 8 migration).
        from . import gamification as _G  # noqa: E402
        try:
            from sqlalchemy import inspect as _insp  # noqa: E402
            if "point_settings" in _insp(db.engine).get_table_names():
                _G.ensure_gamification_defaults()
                try:
                    _G.run_backfill()
                except Exception:
                    db.session.rollback()
        except Exception:
            db.session.rollback()

    _start_reminder_scheduler(app)

    return app


def _ensure_schema_patches(app):
    """Idempotent schema patches for databases created before Alembic.

    db.create_all() creates missing *tables* but never adds *columns* to
    existing tables. This adds any columns that older databases lack, so a
    plain deploy upgrades the production DB with zero manual steps.
    Works on SQLite and Postgres.
    """
    from sqlalchemy import inspect, text
    patches = [
        ("lessons", "available_after_days",
         "ALTER TABLE lessons ADD COLUMN available_after_days INTEGER DEFAULT 0"),
        ("users", "phone",
         "ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT ''"),
        ("users", "referral_code",
         "ALTER TABLE users ADD COLUMN referral_code VARCHAR(20)"),
        # Phase 5 — AI learning layer
        ("questions", "lesson_id",
         "ALTER TABLE questions ADD COLUMN lesson_id INTEGER REFERENCES lessons(id)"),
        ("coupons", "valid_from",
         "ALTER TABLE coupons ADD COLUMN valid_from DATE"),
        ("coupons", "valid_until",
         "ALTER TABLE coupons ADD COLUMN valid_until DATE"),
        ("ai_settings", "tutor_enabled",
         "ALTER TABLE ai_settings ADD COLUMN tutor_enabled BOOLEAN DEFAULT TRUE"),
        ("ai_settings", "tutor_daily_limit",
         "ALTER TABLE ai_settings ADD COLUMN tutor_daily_limit INTEGER DEFAULT 30"),
        ("courses", "ai_tutor_enabled",
         "ALTER TABLE courses ADD COLUMN ai_tutor_enabled BOOLEAN DEFAULT TRUE"),
        # Phase 6 — advanced assessments
        ("quizzes", "time_limit_min",
         "ALTER TABLE quizzes ADD COLUMN time_limit_min INTEGER DEFAULT 0"),
        ("quizzes", "shuffle_questions",
         "ALTER TABLE quizzes ADD COLUMN shuffle_questions BOOLEAN DEFAULT FALSE"),
        ("quizzes", "shuffle_options",
         "ALTER TABLE quizzes ADD COLUMN shuffle_options BOOLEAN DEFAULT FALSE"),
        ("quizzes", "negative_marking",
         "ALTER TABLE quizzes ADD COLUMN negative_marking FLOAT DEFAULT 0.0"),
        ("quizzes", "max_attempts",
         "ALTER TABLE quizzes ADD COLUMN max_attempts INTEGER DEFAULT 0"),
        ("quizzes", "score_policy",
         "ALTER TABLE quizzes ADD COLUMN score_policy VARCHAR(10) DEFAULT 'best'"),
        ("questions", "qtype",
         "ALTER TABLE questions ADD COLUMN qtype VARCHAR(20) DEFAULT 'mcq_single'"),
        ("questions", "difficulty",
         "ALTER TABLE questions ADD COLUMN difficulty VARCHAR(10) DEFAULT 'medium'"),
        ("questions", "topic",
         "ALTER TABLE questions ADD COLUMN topic VARCHAR(120) DEFAULT ''"),
        ("questions", "skills",
         "ALTER TABLE questions ADD COLUMN skills VARCHAR(200) DEFAULT ''"),
        ("questions", "marks",
         "ALTER TABLE questions ADD COLUMN marks FLOAT DEFAULT 1.0"),
        ("questions", "is_active",
         "ALTER TABLE questions ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
        ("questions", "answer_data",
         "ALTER TABLE questions ADD COLUMN answer_data TEXT DEFAULT ''"),
        ("quiz_attempts", "started_at",
         "ALTER TABLE quiz_attempts ADD COLUMN started_at DATETIME"),
        ("quiz_attempts", "submitted_at",
         "ALTER TABLE quiz_attempts ADD COLUMN submitted_at DATETIME"),
        ("quiz_attempts", "question_order",
         "ALTER TABLE quiz_attempts ADD COLUMN question_order TEXT DEFAULT '[]'"),
        ("quiz_attempts", "time_expired",
         "ALTER TABLE quiz_attempts ADD COLUMN time_expired BOOLEAN DEFAULT FALSE"),
        ("quiz_attempts", "pending_review",
         "ALTER TABLE quiz_attempts ADD COLUMN pending_review BOOLEAN DEFAULT FALSE"),
        ("quiz_answers", "marks_awarded",
         "ALTER TABLE quiz_answers ADD COLUMN marks_awarded FLOAT DEFAULT 0.0"),
        ("quiz_answers", "needs_review",
         "ALTER TABLE quiz_answers ADD COLUMN needs_review BOOLEAN DEFAULT FALSE"),
        ("quiz_answers", "feedback",
         "ALTER TABLE quiz_answers ADD COLUMN feedback TEXT DEFAULT ''"),
        ("quiz_answers", "reviewed_by",
         "ALTER TABLE quiz_answers ADD COLUMN reviewed_by INTEGER REFERENCES users(id)"),
        ("quiz_answers", "reviewed_at",
         "ALTER TABLE quiz_answers ADD COLUMN reviewed_at DATETIME"),
        # Phase 7 — career & placements
        ("users", "company",
         "ALTER TABLE users ADD COLUMN company VARCHAR(160) DEFAULT ''"),
        ("jobs", "employer_id",
         "ALTER TABLE jobs ADD COLUMN employer_id INTEGER REFERENCES users(id)"),
        ("job_applications", "employer_note",
         "ALTER TABLE job_applications ADD COLUMN employer_note TEXT DEFAULT ''"),
    ]
    try:
        with app.app_context():
            insp = inspect(db.engine)
            existing_tables = set(insp.get_table_names())
            for table, column, ddl in patches:
                if table not in existing_tables:
                    continue
                cols = {c["name"] for c in insp.get_columns(table)}
                if column in cols:
                    continue
                with db.engine.begin() as conn:
                    conn.execute(text(ddl))
                app.logger.info("schema patch applied: %s.%s", table, column)
            # Phase 6: legacy attempts (pre-Phase-6) were completed-at-POST, so
            # mark them submitted — otherwise they'd look like in-progress
            # attempts to the new exam flow. Idempotent.
            if "quiz_attempts" in existing_tables:
                cols = {c["name"] for c in insp.get_columns("quiz_attempts")}
                if {"started_at", "submitted_at", "taken_at"} <= cols:
                    with db.engine.begin() as conn:
                        conn.execute(text(
                            "UPDATE quiz_attempts SET submitted_at = taken_at "
                            "WHERE submitted_at IS NULL AND taken_at IS NOT NULL"))
                        conn.execute(text(
                            "UPDATE quiz_attempts SET started_at = taken_at "
                            "WHERE started_at IS NULL AND taken_at IS NOT NULL"))
    except Exception:
        app.logger.exception("schema patch check failed (non-fatal)")


def _start_reminder_scheduler(app):
    """Background daemon: email live-class reminders ~1h before start.

    Guarded so the reloader / test runs don't spawn it: set LMS_SCHEDULER=off
    to disable. The sent_reminder flag is committed BEFORE sending so that
    multiple gunicorn workers can't double-send.
    """
    if os.environ.get("LMS_SCHEDULER", "").lower() == "off":
        return
    if getattr(app, "_reminder_scheduler_started", False):
        return
    app._reminder_scheduler_started = True

    def loop():
        import time
        while True:
            try:
                time.sleep(300)
                with app.app_context():
                    from .emailer import send_live_reminders  # noqa: E402
                    send_live_reminders()
            except Exception:  # never crash the process on scheduler errors
                continue

    t = threading.Thread(target=loop, name="lms-reminder-scheduler", daemon=True)
    t.start()
