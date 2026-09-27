"""Phase 10: platform hardening.

- New tables: api_keys, webhooks, webhook_deliveries, backups,
  notifications, message_templates, app_settings
- Column adds: courses.meta_title, courses.meta_description (SEO §20.6)

All changes are guarded so the migration is re-runnable and blank-chain
upgrades stay clean. No SQLite-specific DDL — the same revision runs on
Postgres (JSON-ish fields are plain TEXT on both dialects).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "e10a3f2b8c4d"
down_revision = "d9f3a2b1c4e5"
branch_labels = None
depends_on = None


def _has_table(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _has_column(table, column):
    return column in {c["name"] for c in
                      sa_inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has_table("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False, default=""),
            sa.Column("key_prefix", sa.String(24), nullable=False,
                      default=""),
            sa.Column("key_hash", sa.String(64), nullable=False,
                      unique=True, index=True),
            sa.Column("scopes_json", sa.Text(), default="[]"),
            sa.Column("rate_limit_per_min", sa.Integer(), default=300),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=True),
        )
    if not _has_table("webhooks"):
        op.create_table(
            "webhooks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False, default=""),
            sa.Column("url", sa.String(500), nullable=False, default=""),
            sa.Column("events_json", sa.Text(), default="[]"),
            sa.Column("secret", sa.String(128), nullable=False, default=""),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("webhook_deliveries"):
        op.create_table(
            "webhook_deliveries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("webhook_id", sa.Integer(),
                      sa.ForeignKey("webhooks.id"), nullable=False,
                      index=True),
            sa.Column("event", sa.String(40), nullable=False, default=""),
            sa.Column("payload", sa.Text(), default=""),
            sa.Column("attempts", sa.Integer(), default=0),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("success", sa.Boolean(), default=False, index=True),
            sa.Column("error", sa.Text(), default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True,
                      index=True),
        )
    if not _has_table("backups"):
        op.create_table(
            "backups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("filename", sa.String(200), nullable=False,
                      default=""),
            sa.Column("size_bytes", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("note", sa.String(200), default=""),
        )
    if not _has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False,
                      index=True),
            sa.Column("ntype", sa.String(40), nullable=False, default="",
                      index=True),
            sa.Column("title", sa.String(200), nullable=False, default=""),
            sa.Column("body", sa.Text(), default=""),
            sa.Column("link", sa.String(500), default=""),
            sa.Column("is_read", sa.Boolean(), default=False, index=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True,
                      index=True),
        )
    if not _has_table("message_templates"):
        op.create_table(
            "message_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False, unique=True),
            sa.Column("event_key", sa.String(60), default=""),
            sa.Column("channel", sa.String(20), default="notification"),
            sa.Column("subject", sa.String(200), default=""),
            sa.Column("body", sa.Text(), default=""),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("use_count", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("app_settings"):
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(80), primary_key=True),
            sa.Column("value", sa.Text(), default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if _has_table("courses"):
        if not _has_column("courses", "meta_title"):
            op.add_column("courses",
                          sa.Column("meta_title", sa.String(160),
                                    default=""))
        if not _has_column("courses", "meta_description"):
            op.add_column("courses",
                          sa.Column("meta_description", sa.String(300),
                                    default=""))


def downgrade():
    for table in ("app_settings", "message_templates", "notifications",
                  "backups", "webhook_deliveries", "webhooks", "api_keys"):
        if _has_table(table):
            op.drop_table(table)
    if _has_table("courses"):
        if _has_column("courses", "meta_description"):
            op.drop_column("courses", "meta_description")
        if _has_column("courses", "meta_title"):
            op.drop_column("courses", "meta_title")
