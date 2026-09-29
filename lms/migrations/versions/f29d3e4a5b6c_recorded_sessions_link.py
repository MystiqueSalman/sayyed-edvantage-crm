"""recorded_sessions_link

Revision ID: f29d3e4a5b6c
Revises: u14a1b2c3d4e5
Create Date: 2026-09-29

Live Classes page — new tabs:
  - recordings.live_session_id (nullable FK -> live_sessions.id): links a
    recorded session to the live class it was captured from.
  - recordings.notes (TEXT): faculty notes / attached-material links shown to
    students under each recording.
  - course_materials table: faculty-uploaded files (xlsx, pdf, ppt, …) per
    course, shown under the "Course Materials" tab.

SQLite- and PostgreSQL-compatible: the new table is created from the model
metadata (never drifts); only plain SQLAlchemy types, no server defaults
beyond a harmless '' , no PG-only constructs.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f29d3e4a5b6c"
down_revision = "u14a1b2c3d4e5"
branch_labels = None
depends_on = None


def _tables():
    # Imported lazily so `flask db` never pays the cost at collection time.
    from app import models  # noqa: F401

    return [models.CourseMaterial.__table__]


def upgrade():
    bind = op.get_bind()
    for table in _tables():
        table.create(bind=bind, checkfirst=True)
    # Idempotent: _ensure_schema_patches() also adds these columns at app
    # startup (production doesn't run `flask db upgrade`), so they may
    # already exist when this migration runs against a live database.
    # Plain ADD COLUMN: SQLite supports it natively, so no batch
    # table-rebuild is needed. The live_sessions FK is declared in the
    # model for the ORM; like the other schema patches in this project,
    # no DB-level named constraint is created here.
    insp = sa.inspect(bind)
    rec_cols = {c["name"] for c in insp.get_columns("recordings")}
    if "live_session_id" not in rec_cols:
        op.add_column("recordings",
                      sa.Column("live_session_id", sa.Integer(),
                                nullable=True))
    if "notes" not in rec_cols:
        op.add_column("recordings",
                      sa.Column("notes", sa.Text(), nullable=True,
                                server_default=""))


def downgrade():
    with op.batch_alter_table("recordings") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("live_session_id")
    op.drop_table("course_materials")
