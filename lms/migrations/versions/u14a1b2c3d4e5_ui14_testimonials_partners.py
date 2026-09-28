"""ui14_public_homepage_redesign

Revision ID: u14a1b2c3d4e5
Revises: p13f1a2b3c4d5
Create Date: 2026-09-28

UI14 — homepage/student-dashboard redesign (backend):

  - testimonials table (admin-managed student stories for the homepage
    carousel; is_sample flags the one seeded sample row)
  - partners table (admin-managed partner logo strip; seeded empty)
  - lesson_progress.time_spent_sec (real learning-time tracking, fed by
    the lesson heartbeat endpoint)

Tables are created directly from the model metadata so the revision can
never drift from the models. SQLite- and PostgreSQL-compatible: only
plain SQLAlchemy types (Integer/String/Text/DateTime/Boolean) — no
server defaults, no PG-only constructs.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "u14a1b2c3d4e5"
down_revision = "p13f1a2b3c4d5"
branch_labels = None
depends_on = None


def _tables():
    # Imported lazily so `flask db` never pays the cost at collection time.
    from app import models_ui  # noqa: F401
    from app import models  # noqa: F401

    return [
        models_ui.Testimonial.__table__,
        models_ui.Partner.__table__,
    ]


def upgrade():
    bind = op.get_bind()
    for table in _tables():
        table.create(bind=bind)
    from app.models import LessonProgress
    op.add_column("lesson_progress",
                  LessonProgress.__table__.c.time_spent_sec.copy())


def downgrade():
    bind = op.get_bind()
    op.drop_column("lesson_progress", "time_spent_sec")
    for table in reversed(_tables()):
        table.drop(bind=bind)
