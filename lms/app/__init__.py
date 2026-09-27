"""Sayyed EdVantage LMS — application factory."""
import os
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


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

    from .models import User  # noqa: E402

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return {"now": datetime.utcnow(), "payments_live": app.config["PAYMENTS_LIVE"]}

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manage_bp)

    with app.app_context():
        db.create_all()  # MVP: auto-create tables (Alembic migrations = Phase 2)

    return app
