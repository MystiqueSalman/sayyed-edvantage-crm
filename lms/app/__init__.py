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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(discuss_bp)
    app.register_blueprint(growth_bp)

    with app.app_context():
        if os.environ.get("LMS_SKIP_CREATE_ALL") != "1":
            db.create_all()  # ensures tables exist (Alembic migrations for upgrades)
        _ensure_schema_patches(app)

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
