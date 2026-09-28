"""Phase 13 Stream 5 (Money + International) models.

Additive-only: all new tables live here. Existing tables in app/models.py
are untouched. Plain SQLAlchemy column types (Postgres-compatible).
"""
from datetime import datetime

from . import db


class InstallmentPlan13(db.Model):
    """Admin-defined installment plan for a course (Phase 13 §5.2)."""
    __tablename__ = "installment_plans_13"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                         nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, default="")
    num_installments = db.Column(db.Integer, nullable=False, default=1)
    # per-installment INR amounts, e.g. [20000, 15000, 15000]
    amounts = db.Column(db.JSON, nullable=False, default=list)
    # days after enrollment each installment is due, e.g. [0, 30, 60]
    due_days = db.Column(db.JSON, nullable=False, default=list)
    active = db.Column(db.Boolean, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref(
        "installment_plans_13", cascade="all, delete-orphan",
        order_by="InstallmentPlan13.id"))

    @property
    def total_amount(self):
        try:
            return sum(int(a) for a in (self.amounts or []))
        except (TypeError, ValueError):
            return 0


class StudentInstallment13(db.Model):
    """One installment owed by a student (Phase 13 §5.2)."""
    __tablename__ = "student_installments_13"

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                       nullable=False, index=True)
    plan_id = db.Column(db.Integer,
                       db.ForeignKey("installment_plans_13.id"),
                       nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                         nullable=False, index=True)
    installment_no = db.Column(db.Integer, nullable=False, default=1)
    amount_inr = db.Column(db.Integer, nullable=False, default=0)
    due_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(16), default=STATUS_PENDING, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    payment_ref = db.Column(db.String(120), default="")

    user = db.relationship("User", backref=db.backref(
        "installments_13", cascade="all, delete-orphan",
        order_by="StudentInstallment13.due_date"))
    plan = db.relationship("InstallmentPlan13", backref=db.backref(
        "student_installments", cascade="all, delete-orphan"))
    course = db.relationship("Course")


class FxRate13(db.Model):
    """Admin-editable currency estimates for display conversion (Phase 13 §5.3).

    rate_to_inr: how many INR one unit of this currency buys
    (e.g. USD 83.5 means $1 ≈ ₹83.5). Estimates only — checkout always
    charges INR.
    """
    __tablename__ = "fx_rates_13"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False, index=True)
    rate_to_inr = db.Column(db.Float, nullable=False, default=1.0)
    symbol = db.Column(db.String(12), nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class LocalePrefs13(db.Model):
    """Per-user display timezone preference (Phase 13 §5.4)."""
    __tablename__ = "locale_prefs_13"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                       unique=True, nullable=False, index=True)
    timezone = db.Column(db.String(64), nullable=False,
                        default="Asia/Kolkata")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref(
        "locale_prefs_13", uselist=False, cascade="all, delete-orphan"))
