"""Phase 12: advanced scale/SaaS (§21).

- New tables: tenants, tenant_settings, lab_exercises, lab_attempts,
  vlab_scenarios, vlab_progress
- Column adds (all nullable, default NULL = default Sayyed EdVantage
  tenant): users.tenant_id, courses.tenant_id, enrollments.tenant_id,
  leads.tenant_id, batches.tenant_id

All changes are guarded so the migration is re-runnable and blank-chain
upgrades stay clean. No SQLite-specific DDL — the same revision runs on
Postgres.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "9c1d2e3f4a5b"
down_revision = "f11a9c0d3e7b"
branch_labels = None
depends_on = None


def _has_table(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _has_column(table, column):
    return column in {c["name"] for c in
                      sa_inspect(op.get_bind()).get_columns(table)}


def _add_tenant_id(table):
    # NOTE: plain INTEGER, no ForeignKey — Alembic/SQLite cannot ADD COLUMN
    # with a REFERENCES clause ("No support for ALTER of constraints").
    # The FK lives in the SQLAlchemy model metadata only.
    if not _has_column(table, "tenant_id"):
        op.add_column(table, sa.Column("tenant_id", sa.Integer(),
                                       nullable=True))
    # index (name it explicitly; guard by checking existing indexes)
    try:
        existing = {i["name"] for i in
                    sa_inspect(op.get_bind()).get_indexes(table)}
    except Exception:
        existing = set()
    idx = f"ix_{table}_tenant_id"
    if idx not in existing:
        op.create_index(idx, table, ["tenant_id"])


def upgrade():
    if not _has_table("tenants"):
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("slug", sa.String(80), nullable=False, unique=True,
                      index=True),
            sa.Column("active", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("tenant_settings"):
        op.create_table(
            "tenant_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(),
                      sa.ForeignKey("tenants.id"), nullable=False,
                      unique=True, index=True),
            sa.Column("brand_name", sa.String(160), default=""),
            sa.Column("tagline", sa.String(300), default=""),
            sa.Column("primary_color", sa.String(20), default=""),
            sa.Column("accent_color", sa.String(20), default=""),
            sa.Column("logo_file", sa.String(200), default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("lab_exercises"):
        op.create_table(
            "lab_exercises",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lesson_id", sa.Integer(),
                      sa.ForeignKey("lessons.id"), nullable=False,
                      index=True),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("instructions", sa.Text(), default=""),
            sa.Column("starter_code", sa.Text(), default=""),
            sa.Column("expected_output", sa.Text(), default=""),
            sa.Column("is_published", sa.Boolean(), default=True),
            sa.Column("created_by", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("lab_attempts"):
        op.create_table(
            "lab_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exercise_id", sa.Integer(),
                      sa.ForeignKey("lab_exercises.id"), nullable=False,
                      index=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("code", sa.Text(), default=""),
            sa.Column("output", sa.Text(), default=""),
            sa.Column("passed", sa.Boolean(), default=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("vlab_scenarios"):
        op.create_table(
            "vlab_scenarios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=True, index=True),
            sa.Column("description", sa.Text(), default=""),
            sa.Column("scenario_json", sa.Text(), default="{}"),
            sa.Column("is_published", sa.Boolean(), default=True),
            sa.Column("created_by", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("vlab_progress"):
        op.create_table(
            "vlab_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scenario_id", sa.Integer(),
                      sa.ForeignKey("vlab_scenarios.id"), nullable=False,
                      index=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("completed", sa.Boolean(), default=False),
            sa.Column("log", sa.Text(), default=""),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    for table in ("users", "courses", "enrollments", "leads", "batches"):
        _add_tenant_id(table)


def downgrade():
    for table in ("users", "courses", "enrollments", "leads", "batches"):
        if _has_column(table, "tenant_id"):
            try:
                op.drop_index(f"ix_{table}_tenant_id", table_name=table)
            except Exception:
                pass
            op.drop_column(table, "tenant_id")
    for table in ("vlab_progress", "vlab_scenarios", "lab_attempts",
                  "lab_exercises", "tenant_settings", "tenants"):
        if _has_table(table):
            op.drop_table(table)
