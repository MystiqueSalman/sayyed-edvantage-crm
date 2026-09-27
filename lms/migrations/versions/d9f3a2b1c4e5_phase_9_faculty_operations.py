"""Phase 9: faculty & operations.

- New tables: session_attendance, audit_logs, role_permissions,
  invoice_settings (single-row, id=1), invoices, refunds
- Column adds: batches.end_date, announcements.batch_id (plain INTEGER in
  the migration to keep blank-chain SQLite upgrades clean — runtime
  _ensure_schema_patches uses inline REFERENCES)

All changes are guarded so the migration is re-runnable and blank-chain
upgrades stay clean.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "d9f3a2b1c4e5"
down_revision = "b7e21c94d0a8"
branch_labels = None
depends_on = None


def _has_table(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _has_column(table, column):
    return column in {c["name"] for c in
                      sa_inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has_table("session_attendance"):
        op.create_table(
            "session_attendance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(),
                      sa.ForeignKey("live_sessions.id"), nullable=False,
                      index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("status", sa.String(10), default="present"),
            sa.Column("joined_at", sa.DateTime(), nullable=True),
            sa.Column("duration_min", sa.Integer(), nullable=True),
            sa.Column("marked_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.Column("auto", sa.Boolean(), default=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("session_id", "user_id",
                                name="uq_session_attendance"),
        )
    if not _has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.Column("actor_email", sa.String(160), default=""),
            sa.Column("action", sa.String(80), nullable=False, index=True),
            sa.Column("target_type", sa.String(40), default=""),
            sa.Column("target_id", sa.Integer(), nullable=True),
            sa.Column("detail", sa.Text(), default=""),
            sa.Column("ip", sa.String(64), default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True, index=True),
        )
    if not _has_table("role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role", sa.String(20), nullable=False, index=True),
            sa.Column("module", sa.String(40), nullable=False, index=True),
            sa.Column("can_view", sa.Boolean(), default=False),
            sa.Column("can_create", sa.Boolean(), default=False),
            sa.Column("can_edit", sa.Boolean(), default=False),
            sa.Column("can_delete", sa.Boolean(), default=False),
            sa.UniqueConstraint("role", "module", name="uq_role_module"),
        )
    if not _has_table("invoice_settings"):
        op.create_table(
            "invoice_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("business_name", sa.String(160),
                      default="Sayyed EdVantage"),
            sa.Column("address", sa.Text(), default=""),
            sa.Column("email", sa.String(160),
                      default="sayyededvantage@gmail.com"),
            sa.Column("phone", sa.String(30), default="+91 7977877884"),
            sa.Column("gstin", sa.String(20), default=""),
            sa.Column("sac_code", sa.String(10), default="999293"),
            sa.Column("gst_rate", sa.Float(), default=18.0),
            sa.Column("invoice_prefix", sa.String(10), default="SE"),
            sa.Column("next_number", sa.Integer(), default=1),
            sa.Column("notes", sa.Text(), default=""),
        )
    if not _has_table("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("number", sa.String(40), nullable=False, unique=True,
                      index=True),
            sa.Column("enrollment_id", sa.Integer(),
                      sa.ForeignKey("enrollments.id"), nullable=False,
                      unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False),
            sa.Column("base_fee", sa.Integer(), default=0),
            sa.Column("discount", sa.Integer(), default=0),
            sa.Column("taxable", sa.Integer(), default=0),
            sa.Column("gst_amount", sa.Integer(), default=0),
            sa.Column("total", sa.Integer(), default=0),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("issued_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
        )
    if not _has_table("refunds"):
        op.create_table(
            "refunds",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("enrollment_id", sa.Integer(),
                      sa.ForeignKey("enrollments.id"), nullable=False,
                      index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False),
            sa.Column("amount", sa.Integer(), default=0),
            sa.Column("reason", sa.Text(), default=""),
            sa.Column("status", sa.String(20), default="requested",
                      index=True),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
        )
    # Column adds on existing tables (plain INTEGER — see module docstring)
    if _has_table("batches") and not _has_column("batches", "end_date"):
        op.add_column("batches", sa.Column("end_date", sa.Date(), nullable=True))
    if _has_table("announcements") and not _has_column(
            "announcements", "batch_id"):
        op.add_column("announcements",
                      sa.Column("batch_id", sa.Integer(), nullable=True))
    if _has_table("quizzes") and not _has_column("quizzes", "deadline"):
        op.add_column("quizzes", sa.Column("deadline", sa.Date(),
                                           nullable=True))


def downgrade():
    for table in ("refunds", "invoices", "invoice_settings",
                  "role_permissions", "audit_logs", "session_attendance"):
        if _has_table(table):
            op.drop_table(table)
    if _has_table("announcements") and _has_column("announcements",
                                                   "batch_id"):
        op.drop_column("announcements", "batch_id")
    if _has_table("batches") and _has_column("batches", "end_date"):
        op.drop_column("batches", "end_date")
    if _has_table("quizzes") and _has_column("quizzes", "deadline"):
        op.drop_column("quizzes", "deadline")
