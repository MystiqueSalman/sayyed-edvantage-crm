"""Phase 6: advanced assessments.

- Question: qtype, difficulty, topic, skills, marks, is_active, answer_data
  (old MCQ rows keep working via qtype='mcq_single' + legacy columns)
- Quiz: exam settings — time_limit_min, shuffle_questions, shuffle_options,
  negative_marking, max_attempts, score_policy
- QuizAttempt: score/total widened Integer -> Float (partial credit /
  negative marking), started_at, time_expired, pending_review
- QuizAnswer: chosen widened String(1) -> Text (multi/free-form answers),
  marks_awarded, needs_review, feedback, reviewed_by, reviewed_at
- New tables: projects, project_submissions

SQLite cannot ALTER column types in place, so type changes use
batch_alter_table (copy-and-move). All additions are guarded so the
migration is re-runnable and blank-chain upgrades stay clean.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "c6d7e8f9a0b1"
down_revision = "a5f1c2d3e4b5"
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


def _add_column(table, column):
    if not _has_column(table, column.name):
        op.add_column(table, column)


def upgrade():
    # ---- new tables ----
    if not _has_table("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), default=""),
            sa.Column("skills", sa.String(200), default=""),
            sa.Column("deadline", sa.Date(), nullable=True),
            sa.Column("max_marks", sa.Integer(), default=100),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.now()),
        )
    if not _has_table("project_submissions"):
        op.create_table(
            "project_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"),
                      nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("project_url", sa.String(300), default=""),
            sa.Column("file_path", sa.String(260), default=""),
            sa.Column("notes", sa.Text(), default=""),
            sa.Column("status", sa.String(20), default="submitted"),
            sa.Column("marks", sa.Float(), nullable=True),
            sa.Column("feedback", sa.Text(), default=""),
            sa.Column("submitted_at", sa.DateTime(),
                      server_default=sa.func.now()),
            sa.Column("evaluated_at", sa.DateTime(), nullable=True),
            sa.Column("evaluated_by", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=True),
            sa.UniqueConstraint("project_id", "user_id",
                                name="uq_project_submission"),
        )

    # ---- quizzes: exam settings ----
    _add_column("quizzes", sa.Column("time_limit_min", sa.Integer(), default=0))
    _add_column("quizzes", sa.Column("shuffle_questions", sa.Boolean(),
                                     default=False))
    _add_column("quizzes", sa.Column("shuffle_options", sa.Boolean(),
                                     default=False))
    _add_column("quizzes", sa.Column("negative_marking", sa.Float(), default=0.0))
    _add_column("quizzes", sa.Column("max_attempts", sa.Integer(), default=0))
    _add_column("quizzes", sa.Column("score_policy", sa.String(10),
                                     default="best"))

    # ---- questions: types + bank metadata ----
    _add_column("questions", sa.Column("qtype", sa.String(20),
                                       default="mcq_single"))
    _add_column("questions", sa.Column("difficulty", sa.String(10),
                                       default="medium"))
    _add_column("questions", sa.Column("topic", sa.String(120), default=""))
    _add_column("questions", sa.Column("skills", sa.String(200), default=""))
    _add_column("questions", sa.Column("marks", sa.Float(), default=1.0))
    _add_column("questions", sa.Column("is_active", sa.Boolean(), default=True))
    _add_column("questions", sa.Column("answer_data", sa.Text(), default=""))

    # ---- quiz_attempts: float scores + exam fields ----
    _add_column("quiz_attempts", sa.Column("started_at", sa.DateTime(),
                                           nullable=True))
    _add_column("quiz_attempts", sa.Column("submitted_at", sa.DateTime(),
                                           nullable=True))
    _add_column("quiz_attempts", sa.Column("question_order", sa.Text(),
                                           default="[]"))
    _add_column("quiz_attempts", sa.Column("time_expired", sa.Boolean(),
                                           default=False))
    _add_column("quiz_attempts", sa.Column("pending_review", sa.Boolean(),
                                           default=False))
    with op.batch_alter_table("quiz_attempts") as batch_op:
        batch_op.alter_column("score", existing_type=sa.Integer(),
                              type_=sa.Float(), existing_nullable=True)
        batch_op.alter_column("total", existing_type=sa.Integer(),
                              type_=sa.Float(), existing_nullable=True)

    # ---- quiz_answers: wider response + review fields ----
    _add_column("quiz_answers", sa.Column("marks_awarded", sa.Float(),
                                          default=0.0))
    _add_column("quiz_answers", sa.Column("needs_review", sa.Boolean(),
                                          default=False))
    _add_column("quiz_answers", sa.Column("feedback", sa.Text(), default=""))
    # NOTE: no ForeignKey() here — SQLite cannot ADD a constraint via ALTER
    # (the ORM model still declares the relationship; the runtime schema
    # patch uses inline REFERENCES which SQLite accepts).
    _add_column("quiz_answers", sa.Column("reviewed_by", sa.Integer(),
                                          nullable=True))
    _add_column("quiz_answers", sa.Column("reviewed_at", sa.DateTime(),
                                          nullable=True))
    with op.batch_alter_table("quiz_answers") as batch_op:
        batch_op.alter_column("chosen", existing_type=sa.String(1),
                              type_=sa.Text(), existing_nullable=True)


def downgrade():
    with op.batch_alter_table("quiz_answers") as batch_op:
        batch_op.alter_column("chosen", existing_type=sa.Text(),
                              type_=sa.String(1), existing_nullable=True)
    for col in ("reviewed_at", "reviewed_by", "feedback", "needs_review",
                "marks_awarded"):
        if _has_column("quiz_answers", col):
            op.drop_column("quiz_answers", col)
    with op.batch_alter_table("quiz_attempts") as batch_op:
        batch_op.alter_column("total", existing_type=sa.Float(),
                              type_=sa.Integer(), existing_nullable=True)
        batch_op.alter_column("score", existing_type=sa.Float(),
                              type_=sa.Integer(), existing_nullable=True)
    for col in ("pending_review", "time_expired", "question_order",
                "submitted_at", "started_at"):
        if _has_column("quiz_attempts", col):
            op.drop_column("quiz_attempts", col)
    for col in ("answer_data", "is_active", "marks", "skills", "topic",
                "difficulty", "qtype"):
        if _has_column("questions", col):
            op.drop_column("questions", col)
    for col in ("score_policy", "max_attempts", "negative_marking",
                "shuffle_options", "shuffle_questions", "time_limit_min"):
        if _has_column("quizzes", col):
            op.drop_column("quizzes", col)
    if _has_table("project_submissions"):
        op.drop_table("project_submissions")
    if _has_table("projects"):
        op.drop_table("projects")
