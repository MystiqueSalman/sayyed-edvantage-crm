"""Phase 11: marketing suite (§20).

- New tables: landing_pages, page_views, campaigns, affiliates,
  affiliate_clicks, affiliate_earnings, affiliate_payouts, email_campaigns
- Column adds: leads.campaign_id, leads.affiliate_id,
  enrollments.source, enrollments.campaign_id, enrollments.affiliate_id

All changes are guarded so the migration is re-runnable and blank-chain
upgrades stay clean. No SQLite-specific DDL — the same revision runs on
Postgres (JSON blocks/segments use sa.JSON, portable on both).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "f11a9c0d3e7b"
down_revision = "e10a3f2b8c4d"
branch_labels = None
depends_on = None


def _has_table(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _has_column(table, column):
    return column in {c["name"] for c in
                      sa_inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has_table("landing_pages"):
        op.create_table(
            "landing_pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(80), nullable=False, unique=True,
                      index=True),
            sa.Column("title", sa.String(160), nullable=False, default=""),
            sa.Column("status", sa.String(16), default="draft"),
            sa.Column("blocks", sa.JSON(), default=list),
            sa.Column("views", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("campaigns"):
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False, default=""),
            sa.Column("channel", sa.String(20), default="other"),
            sa.Column("landing_page_id", sa.Integer(),
                      sa.ForeignKey("landing_pages.id"), nullable=True),
            sa.Column("coupon_id", sa.Integer(),
                      sa.ForeignKey("coupons.id"), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("budget", sa.Integer(), nullable=True),
            sa.Column("active", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("page_views"):
        op.create_table(
            "page_views",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("landing_page_id", sa.Integer(),
                      sa.ForeignKey("landing_pages.id"), nullable=True,
                      index=True),
            sa.Column("campaign_id", sa.Integer(),
                      sa.ForeignKey("campaigns.id"), nullable=True,
                      index=True),
            sa.Column("viewed_at", sa.DateTime(), nullable=True, index=True),
        )
    if not _has_table("affiliates"):
        op.create_table(
            "affiliates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False, default=""),
            sa.Column("contact", sa.String(160), default=""),
            sa.Column("code", sa.String(24), nullable=False, unique=True,
                      index=True),
            sa.Column("commission_type", sa.String(10), default="flat"),
            sa.Column("commission_value", sa.Float(), default=0.0),
            sa.Column("active", sa.Boolean(), default=True),
            sa.Column("token", sa.String(48), nullable=False, unique=True,
                      index=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("affiliate_clicks"):
        op.create_table(
            "affiliate_clicks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("affiliate_id", sa.Integer(),
                      sa.ForeignKey("affiliates.id"), nullable=False,
                      index=True),
            sa.Column("clicked_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("affiliate_payouts"):
        op.create_table(
            "affiliate_payouts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("affiliate_id", sa.Integer(),
                      sa.ForeignKey("affiliates.id"), nullable=False,
                      index=True),
            sa.Column("amount", sa.Float(), default=0.0),
            sa.Column("status", sa.String(10), default="pending"),
            sa.Column("note", sa.String(255), default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("affiliate_earnings"):
        op.create_table(
            "affiliate_earnings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("affiliate_id", sa.Integer(),
                      sa.ForeignKey("affiliates.id"), nullable=False,
                      index=True),
            sa.Column("enrollment_id", sa.Integer(),
                      sa.ForeignKey("enrollments.id"), nullable=False,
                      unique=True),
            sa.Column("amount", sa.Float(), default=0.0),
            sa.Column("status", sa.String(10), default="pending"),
            sa.Column("payout_id", sa.Integer(),
                      sa.ForeignKey("affiliate_payouts.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("email_campaigns"):
        op.create_table(
            "email_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False, default=""),
            sa.Column("template_id", sa.Integer(),
                      sa.ForeignKey("message_templates.id"), nullable=True),
            sa.Column("segment", sa.JSON(), default=dict),
            sa.Column("status", sa.String(16), default="draft"),
            sa.Column("sent_count", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
        )
    # Attribution columns on existing tables.
    # NOTE: plain INTEGER here — SQLite cannot ALTER in a FOREIGN KEY
    # constraint (same Phase 6 lesson). The ORM relationships in models.py
    # keep the logical FK; runtime schema patches use inline REFERENCES.
    if _has_table("leads"):
        if not _has_column("leads", "campaign_id"):
            op.add_column("leads", sa.Column("campaign_id", sa.Integer(),
                                             nullable=True))
        if not _has_column("leads", "affiliate_id"):
            op.add_column("leads", sa.Column("affiliate_id", sa.Integer(),
                                             nullable=True))
    if _has_table("enrollments"):
        if not _has_column("enrollments", "source"):
            op.add_column("enrollments", sa.Column("source", sa.String(20),
                                                   default=""))
        if not _has_column("enrollments", "campaign_id"):
            op.add_column("enrollments", sa.Column("campaign_id", sa.Integer(),
                                                   nullable=True))
        if not _has_column("enrollments", "affiliate_id"):
            op.add_column("enrollments", sa.Column("affiliate_id",
                                                   sa.Integer(),
                                                   nullable=True))


def downgrade():
    for table in ("email_campaigns", "affiliate_earnings",
                  "affiliate_payouts", "affiliate_clicks", "affiliates",
                  "page_views", "campaigns", "landing_pages"):
        if _has_table(table):
            op.drop_table(table)
    if _has_table("leads"):
        for col in ("affiliate_id", "campaign_id"):
            if _has_column("leads", col):
                op.drop_column("leads", col)
    if _has_table("enrollments"):
        for col in ("affiliate_id", "campaign_id", "source"):
            if _has_column("enrollments", col):
                op.drop_column("enrollments", col)
