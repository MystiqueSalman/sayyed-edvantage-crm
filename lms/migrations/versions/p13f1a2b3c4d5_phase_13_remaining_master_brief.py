"""phase_13_remaining_master_brief

Revision ID: p13f1a2b3c4d5
Revises: 9c1d2e3f4a5b
Create Date: 2026-09-28

Phase 13 — the remaining ~15% of the master brief, built by six isolated
streams and merged here into ONE revision:

  Stream 1 (auth & accounts):      p13_password_reset_tokens, p13_email_otps,
                                   p13_user_security, p13_parent_links
  Stream 2 (learning extras):      lesson_notes13, sql_exercises13,
                                   sql_attempts13, ds_exercises13,
                                   ds_progress13, course_versions13,
                                   enrollment_versions13, video_policies13
  Stream 3 (AI extras):            ai_drafts13, rubrics13,
                                   project_evaluations13, atrisk_flags13,
                                   student_memory13
  Stream 4 (messaging/leaderboard): dm_conversations, dm_messages,
                                   leaderboard_privacy
  Stream 5 (money/international):  installment_plans_13,
                                   student_installments_13, fx_rates_13,
                                   locale_prefs_13
  Stream 6 (chat-lead diagnostics): lead_capture_log13

Tables are created directly from the model metadata so the revision can
never drift from the models. Ordering respects intra-stream FKs
(parent tables first); all FKs to pre-existing tables (users, lessons,
courses, enrollments) already exist in every environment.

SQLite- and PostgreSQL-compatible: only plain SQLAlchemy types are used
(Integer/String/Text/DateTime/Date/Boolean/JSON/Float) — no server
defaults, no PG-only constructs.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "p13f1a2b3c4d5"
down_revision = "9c1d2e3f4a5b"
branch_labels = None
depends_on = None


def _tables():
    # Imported lazily so `flask db` never pays the cost at collection time.
    from app import models13_auth  # noqa: F401
    from app import models13_learning  # noqa: F401
    from app import models13_ai  # noqa: F401
    from app import models13_social  # noqa: F401
    from app import models13_money  # noqa: F401
    from app import models13_parked  # noqa: F401

    # Parents before children (intra-Phase-13 FKs).
    return [
        # Stream 1
        models13_auth.PasswordResetToken.__table__,
        models13_auth.EmailOTP.__table__,
        models13_auth.UserSecurity13.__table__,
        models13_auth.ParentLink13.__table__,
        # Stream 2
        models13_learning.LessonNote13.__table__,
        models13_learning.SqlExercise13.__table__,
        models13_learning.SqlAttempt13.__table__,
        models13_learning.DsExercise13.__table__,
        models13_learning.DsProgress13.__table__,
        models13_learning.CourseVersion13.__table__,
        models13_learning.EnrollmentVersion13.__table__,
        models13_learning.VideoPolicy13.__table__,
        # Stream 3
        models13_ai.AiDraft13.__table__,
        models13_ai.Rubric13.__table__,
        models13_ai.ProjectEvaluation13.__table__,
        models13_ai.AtRiskFlag13.__table__,
        models13_ai.StudentMemory13.__table__,
        # Stream 4
        models13_social.Conversation13.__table__,
        models13_social.DirectMessage13.__table__,
        models13_social.PrivacyPrefs13.__table__,
        # Stream 5
        models13_money.InstallmentPlan13.__table__,
        models13_money.StudentInstallment13.__table__,
        models13_money.FxRate13.__table__,
        models13_money.LocalePrefs13.__table__,
        # Stream 6
        models13_parked.LeadCaptureLog13.__table__,
    ]


def upgrade():
    bind = op.get_bind()
    for table in _tables():
        table.create(bind=bind)


def downgrade():
    bind = op.get_bind()
    for table in reversed(_tables()):
        table.drop(bind=bind)
