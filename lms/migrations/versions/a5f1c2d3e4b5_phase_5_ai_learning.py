"""Phase 5: AI learning layer.

- AI tutor Q&A exchanges + per-course learning memory
- QuizAnswer rows (per-question results for weak-topic analysis)
- Question.lesson_id (optional link to the tested lesson)
- StudyPlan + StudyPlanItem (student study planner)
- Coupon.valid_from / valid_until (live-offer window)
- AISettings.tutor_enabled / tutor_daily_limit, Course.ai_tutor_enabled

SQLite cannot ALTER constraints, so every foreign-key addition uses
batch_alter_table (copy-and-move). Existing rows get tutor feature flags
defaulting to enabled via server defaults.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "a5f1c2d3e4b5"
down_revision = "feb4b4e0ad96"
branch_labels = None
depends_on = None


def _has_table(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _has_column(table, column):
    insp = sa_inspect(op.get_bind())
    try:
        cols = insp.get_columns(table)
    except Exception:
        return False
    return any(c["name"] == column for c in cols)


def upgrade():
    # ---- AI tutor Q&A history ----
    if not _has_table("ai_tutor_exchanges"):
        op.create_table(
            "ai_tutor_exchanges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("cited_lesson_ids", sa.Text(), default="[]"),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.now()),
        )
        op.create_index("ix_ai_tutor_exchanges_user_course",
                        "ai_tutor_exchanges", ["user_id", "course_id"])

    # ---- per-course AI learning memory ----
    if not _has_table("ai_learning_memory"):
        op.create_table(
            "ai_learning_memory",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False),
            sa.Column("weak_topics", sa.Text(), default="[]"),
            sa.Column("preferences", sa.Text(), default="{}"),
            sa.Column("summary", sa.Text(), default=""),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.func.now(),
                      onupdate=sa.func.now()),
            sa.UniqueConstraint("user_id", "course_id",
                                name="uq_ai_memory_user_course"),
        )

    # ---- per-question quiz results ----
    if not _has_table("quiz_answers"):
        op.create_table(
            "quiz_answers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attempt_id", sa.Integer(),
                      sa.ForeignKey("quiz_attempts.id"), nullable=False),
            sa.Column("question_id", sa.Integer(),
                      sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("chosen", sa.String(4), default=""),
            sa.Column("is_correct", sa.Boolean(), default=False),
        )
        op.create_index("ix_quiz_answers_attempt", "quiz_answers",
                        ["attempt_id"])

    # ---- study planner ----
    if not _has_table("study_plans"):
        op.create_table(
            "study_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False),
            sa.Column("target_date", sa.Date(), nullable=False),
            sa.Column("hours_per_day", sa.Float(), default=1.0),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "course_id",
                                name="uq_study_plan_user_course"),
        )
    if not _has_table("study_plan_items"):
        op.create_table(
            "study_plan_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plan_id", sa.Integer(),
                      sa.ForeignKey("study_plans.id"), nullable=False),
            sa.Column("lesson_id", sa.Integer(),
                      sa.ForeignKey("lessons.id"), nullable=False),
            sa.Column("planned_date", sa.Date(), nullable=False),
            sa.Column("done", sa.Boolean(), default=False),
        )
        op.create_index("ix_study_plan_items_plan", "study_plan_items",
                        ["plan_id"])

    # ---- Question.lesson_id (batch mode: FK needs copy-and-move) ----
    if not _has_column("questions", "lesson_id"):
        with op.batch_alter_table("questions") as batch_op:
            batch_op.add_column(sa.Column("lesson_id", sa.Integer(),
                                          nullable=True))
            batch_op.create_foreign_key("fk_questions_lesson_id", "lessons",
                                        ["lesson_id"], ["id"])

    # ---- coupon live window ----
    if not _has_column("coupons", "valid_from"):
        with op.batch_alter_table("coupons") as batch_op:
            batch_op.add_column(sa.Column("valid_from", sa.Date(),
                                          nullable=True))
            batch_op.add_column(sa.Column("valid_until", sa.Date(),
                                          nullable=True))

    # ---- AI tutor feature flags (default ON for existing rows) ----
    if not _has_column("ai_settings", "tutor_enabled"):
        with op.batch_alter_table("ai_settings") as batch_op:
            batch_op.add_column(sa.Column("tutor_enabled", sa.Boolean(),
                                          nullable=False,
                                          server_default="1"))
            batch_op.add_column(sa.Column("tutor_daily_limit", sa.Integer(),
                                          nullable=False,
                                          server_default="30"))
    if not _has_column("courses", "ai_tutor_enabled"):
        with op.batch_alter_table("courses") as batch_op:
            batch_op.add_column(sa.Column("ai_tutor_enabled", sa.Boolean(),
                                          nullable=False,
                                          server_default="1"))


def downgrade():
    if _has_column("courses", "ai_tutor_enabled"):
        with op.batch_alter_table("courses") as batch_op:
            batch_op.drop_column("ai_tutor_enabled")
    if _has_column("ai_settings", "tutor_daily_limit"):
        with op.batch_alter_table("ai_settings") as batch_op:
            batch_op.drop_column("tutor_daily_limit")
            batch_op.drop_column("tutor_enabled")
    if _has_column("coupons", "valid_until"):
        with op.batch_alter_table("coupons") as batch_op:
            batch_op.drop_column("valid_until")
            batch_op.drop_column("valid_from")
    if _has_column("questions", "lesson_id"):
        with op.batch_alter_table("questions") as batch_op:
            batch_op.drop_constraint("fk_questions_lesson_id",
                                     type_="foreignkey")
            batch_op.drop_column("lesson_id")
    if _has_table("study_plan_items"):
        op.drop_index("ix_study_plan_items_plan",
                      table_name="study_plan_items")
        op.drop_table("study_plan_items")
    if _has_table("study_plans"):
        op.drop_table("study_plans")
    if _has_table("quiz_answers"):
        op.drop_index("ix_quiz_answers_attempt", table_name="quiz_answers")
        op.drop_table("quiz_answers")
    if _has_table("ai_learning_memory"):
        op.drop_table("ai_learning_memory")
    if _has_table("ai_tutor_exchanges"):
        op.drop_index("ix_ai_tutor_exchanges_user_course",
                      table_name="ai_tutor_exchanges")
        op.drop_table("ai_tutor_exchanges")
