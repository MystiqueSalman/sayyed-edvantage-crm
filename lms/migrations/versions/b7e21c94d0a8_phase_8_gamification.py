"""Phase 8: gamification & engagement.

- New tables: point_settings, point_transactions, game_profiles, badges,
  user_badges, challenges, challenge_enrollments, gamification_settings
  (single-row flags, id=1)
- No changes to existing tables (purely additive)

All changes are guarded so the migration is re-runnable and blank-chain
upgrades stay clean.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "b7e21c94d0a8"
down_revision = "30af5d3f1651"
branch_labels = None
depends_on = None


def _has_table(name):
    return sa_inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _has_table("point_settings"):
        op.create_table(
            "point_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("action", sa.String(40), nullable=False, unique=True,
                      index=True),
            sa.Column("points", sa.Integer(), default=0),
            sa.Column("label", sa.String(120), default=""),
            sa.Column("counts_for_streak", sa.Boolean(), default=True),
        )
    if not _has_table("point_transactions"):
        op.create_table(
            "point_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("action", sa.String(40), nullable=False, index=True),
            sa.Column("ref_type", sa.String(40), default=""),
            sa.Column("ref_id", sa.String(60), default=""),
            sa.Column("points", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime(), index=True),
            sa.UniqueConstraint("user_id", "action", "ref_type", "ref_id",
                               name="uq_point_txn"),
        )
    if not _has_table("game_profiles"):
        op.create_table(
            "game_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, unique=True, index=True),
            sa.Column("points_total", sa.Integer(), default=0),
            sa.Column("current_streak", sa.Integer(), default=0),
            sa.Column("longest_streak", sa.Integer(), default=0),
            sa.Column("last_active_date", sa.Date(), nullable=True),
        )
    if not _has_table("badges"):
        op.create_table(
            "badges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("icon", sa.String(16), default="🏅"),
            sa.Column("description", sa.String(200), default=""),
            sa.Column("criterion", sa.String(40), nullable=False, index=True),
            sa.Column("threshold", sa.Float(), default=1.0),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=True),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("is_system", sa.Boolean(), default=False),
            sa.Column("created_at", sa.DateTime()),
        )
    if not _has_table("user_badges"):
        op.create_table(
            "user_badges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("badge_id", sa.Integer(), sa.ForeignKey("badges.id"),
                      nullable=False),
            sa.Column("awarded_at", sa.DateTime()),
            sa.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
        )
    if not _has_table("challenges"):
        op.create_table(
            "challenges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), default=""),
            sa.Column("criterion", sa.String(40), nullable=False),
            sa.Column("target_json", sa.Text(), default="{}"),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=True),
            sa.Column("starts_at", sa.DateTime()),
            sa.Column("ends_at", sa.DateTime(), nullable=True),
            sa.Column("reward_points", sa.Integer(), default=50),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
    if not _has_table("challenge_enrollments"):
        op.create_table(
            "challenge_enrollments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("challenge_id", sa.Integer(),
                      sa.ForeignKey("challenges.id"), nullable=False,
                      index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("joined_at", sa.DateTime()),
            sa.Column("progress", sa.Float(), default=0.0),
            sa.Column("completed", sa.Boolean(), default=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("challenge_id", "user_id",
                               name="uq_challenge_enroll"),
        )
    if not _has_table("gamification_settings"):
        op.create_table(
            "gamification_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("backfill_done", sa.Boolean(), default=False),
        )


def downgrade():
    for table in ("gamification_settings", "challenge_enrollments",
                  "challenges", "user_badges", "badges", "game_profiles",
                  "point_transactions", "point_settings"):
        if _has_table(table):
            op.drop_table(table)
