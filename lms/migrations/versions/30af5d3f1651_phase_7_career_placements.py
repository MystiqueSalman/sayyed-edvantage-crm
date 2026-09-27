"""Phase 7: career & placements.

- New tables: resumes, portfolios, mock_interviews, mock_interview_qas,
  readiness_weights (single-row admin config, id=1)
- users.company (employer company name)
- jobs.employer_id (plain INTEGER in the migration — SQLite has no support
  for ALTER of constraints; the runtime schema patch adds it with inline
  REFERENCES and the ORM relationship is unchanged)
- job_applications.employer_note (private employer notes)

All changes are additive and guarded so the migration is re-runnable and
blank-chain upgrades stay clean.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "30af5d3f1651"
down_revision = "c6d7e8f9a0b1"
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
    if not _has_table("resumes"):
        op.create_table(
            "resumes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, unique=True),
            sa.Column("headline", sa.String(160), default=""),
            sa.Column("summary", sa.Text(), default=""),
            sa.Column("skills_text", sa.Text(), default=""),
            sa.Column("experience_json", sa.Text(), default="[]"),
            sa.Column("education_json", sa.Text(), default="[]"),
            sa.Column("links_json", sa.Text(), default="{}"),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.func.now()),
        )
    if not _has_table("portfolios"):
        op.create_table(
            "portfolios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, unique=True),
            sa.Column("code", sa.String(24), nullable=False, unique=True),
            sa.Column("is_public", sa.Boolean(), default=False),
            sa.Column("headline", sa.String(160), default=""),
            sa.Column("about", sa.Text(), default=""),
            sa.Column("show_resume", sa.Boolean(), default=True),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.func.now()),
        )
    if not _has_table("mock_interviews"):
        op.create_table(
            "mock_interviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=True),
            sa.Column("target_role", sa.String(160), default=""),
            sa.Column("status", sa.String(20), default="in_progress"),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("weak_areas", sa.Text(), default=""),
            sa.Column("questions_total", sa.Integer(), default=5),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
    if not _has_table("mock_interview_qas"):
        op.create_table(
            "mock_interview_qas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(),
                      sa.ForeignKey("mock_interviews.id"), nullable=False),
            sa.Column("position", sa.Integer(), default=0),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), default=""),
            sa.Column("feedback", sa.Text(), default=""),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.now()),
        )
    if not _has_table("readiness_weights"):
        op.create_table(
            "readiness_weights",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("w_completion", sa.Float(), default=25.0),
            sa.Column("w_quiz", sa.Float(), default=20.0),
            sa.Column("w_projects", sa.Float(), default=15.0),
            sa.Column("w_resume", sa.Float(), default=10.0),
            sa.Column("w_interviews", sa.Float(), default=15.0),
            sa.Column("w_certificates", sa.Float(), default=15.0),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.func.now()),
        )

    # ---- new columns (additive) ----
    _add_column("users", sa.Column("company", sa.String(160), default=""))
    # plain INTEGER: SQLite cannot ALTER constraints (see module docstring)
    _add_column("jobs", sa.Column("employer_id", sa.Integer(), nullable=True))
    _add_column("job_applications",
                sa.Column("employer_note", sa.Text(), default=""))


def downgrade():
    for tbl in ("readiness_weights", "mock_interview_qas", "mock_interviews",
                "portfolios", "resumes"):
        if _has_table(tbl):
            op.drop_table(tbl)
    if _has_column("job_applications", "employer_note"):
        op.drop_column("job_applications", "employer_note")
    if _has_column("jobs", "employer_id"):
        op.drop_column("jobs", "employer_id")
    if _has_column("users", "company"):
        op.drop_column("users", "company")
