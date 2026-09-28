"""Phase 13 Stream 2 (Learning extras) — new models.

All tables use plain PG-compatible SQLAlchemy types only (no Alembic
revision is created here; the coordinator folds these into one combined
revision). Table names are suffixed ``13`` so they can never collide
with existing tables.

Tables:
  lesson_notes13        private per-lesson notes (one doc per student/lesson)
  sql_exercises13        SQL lab exercises (seeded)
  sql_attempts13         per-attempt log of SQL lab runs
  ds_exercises13         Data-Science notebook-lab exercises (seeded, JSON steps)
  ds_progress13          per-student per-step progress in DS exercises
  course_versions13      published snapshots of a course's structure
  enrollment_versions13  links an enrollment to the course version it joined on
  video_policies13       per-lesson signed-URL video policy

The ``after_insert`` listener on the existing ``Enrollment`` model links
every new enrollment to the latest published CourseVersion13 of its
course (no-op when no version was ever published). It uses
``connection.execute`` so it is safe inside the flush.
"""
from datetime import datetime

from sqlalchemy import event, select

from . import db
from .models import Enrollment


class LessonNote13(db.Model):
    """Private note doc: exactly one per (student, lesson)."""
    __tablename__ = "lesson_notes13"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"),
                          nullable=False, index=True)
    title = db.Column(db.String(160), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "lesson_id",
                            name="uq_lesson_note13"),
    )


class SqlExercise13(db.Model):
    """Seeded read-only SQL practice exercise."""
    __tablename__ = "sql_exercises13"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    setup_sql = db.Column(db.Text, default="")     # builds the practice tables
    expected_sql = db.Column(db.Text, default="")  # reference query (trusted)
    hint = db.Column(db.String(300), default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SqlAttempt13(db.Model):
    """One logged attempt at an SQL exercise."""
    __tablename__ = "sql_attempts13"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, index=True)
    exercise_id = db.Column(db.Integer,
                            db.ForeignKey("sql_exercises13.id"),
                            nullable=False, index=True)
    # NB: attribute is sql_query (not `query`) so it does not shadow
    # Flask-SQLAlchemy's Model.query descriptor; DB column stays "query".
    sql_query = db.Column("query", db.Text, default="")
    passed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DsExercise13(db.Model):
    """Guided Data-Science exercise.

    steps is a JSON list of {"instruction", "starter_code",
    "validation_code", "dataset"} dicts. "dataset" names a CSV under
    app/static/datasets/ (optional).
    """
    __tablename__ = "ds_exercises13"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    steps = db.Column(db.JSON, default=list)
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DsProgress13(db.Model):
    """Latest known state of one student on one DS step (upserted)."""
    __tablename__ = "ds_progress13"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, index=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey("ds_exercises13.id"),
                            nullable=False, index=True)
    step_idx = db.Column(db.Integer, nullable=False, default=0)
    passed = db.Column(db.Boolean, default=False)
    output = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "exercise_id", "step_idx",
                            name="uq_ds_progress13"),
    )


class CourseVersion13(db.Model):
    """Published snapshot of a course's module/lesson structure."""
    __tablename__ = "course_versions13"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                          nullable=False, index=True)
    version_no = db.Column(db.Integer, nullable=False)  # 1,2,3… per course
    snapshot = db.Column(db.JSON, default=dict)  # {modules:[{title, lessons:[{title, kind}]}]}
    note = db.Column(db.String(300), default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"),
                           nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("course_id", "version_no",
                            name="uq_course_version13"),
    )


class EnrollmentVersion13(db.Model):
    """Which published course version an enrollment joined on."""
    __tablename__ = "enrollment_versions13"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"),
                             nullable=False, unique=True, index=True)
    version_id = db.Column(db.Integer,
                           db.ForeignKey("course_versions13.id"),
                           nullable=True)
    linked_at = db.Column(db.DateTime, default=datetime.utcnow)


class VideoPolicy13(db.Model):
    """Per-lesson signed-URL policy. Absence of a row = defaults."""
    __tablename__ = "video_policies13"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"),
                          nullable=False, unique=True, index=True)
    allow_download = db.Column(db.Boolean, default=False)
    token_expiry_hours = db.Column(db.Integer, default=2)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Enrollment -> version linkage (flush-safe, covers every enrollment writer:
# student self-enroll, CRM admission conversion, batch enroll, bulk enroll).


@event.listens_for(Enrollment, "after_insert")
def _link_enrollment_to_latest_version(mapper, connection, target):
    latest_id = connection.execute(
        select(CourseVersion13.id)
        .where(CourseVersion13.course_id == target.course_id)
        .order_by(CourseVersion13.version_no.desc())
        .limit(1)
    ).scalar()
    if latest_id is not None:
        connection.execute(
            EnrollmentVersion13.__table__.insert().values(
                enrollment_id=target.id,
                version_id=latest_id,
                linked_at=datetime.utcnow(),
            )
        )


def version_for_enrollment(enrollment):
    """Return the CourseVersion13 an enrollment is linked to.

    Falls back to the course's latest published version (backfill-on-view)
    so enrollments created before any version was published still resolve.
    Returns None when the course has no published versions at all.
    """
    link = (EnrollmentVersion13.query
            .filter_by(enrollment_id=enrollment.id).first())
    if link and link.version_id:
        v = CourseVersion13.query.get(link.version_id)
        if v:
            return v
    return (CourseVersion13.query
            .filter_by(course_id=enrollment.course_id)
            .order_by(CourseVersion13.version_no.desc()).first())
