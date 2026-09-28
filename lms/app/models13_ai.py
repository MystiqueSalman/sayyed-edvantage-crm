"""Phase 13 Stream 3 — AI extras data models (additive only).

Tables: ai_drafts13, rubrics13, project_evaluations13, atrisk_flags13,
student_memory13. All AI-produced content is stored as *draft* /
*pending_review* and requires human approval before any student sees it.
"""
from datetime import datetime

from . import db

DRAFT_KINDS = ("lesson-outline", "quiz-draft", "assignment-draft")
DRAFT_STATUS_DRAFT = "draft"

EVAL_STATUSES = ("pending_review", "approved", "rejected")


class AiDraft13(db.Model):
    """Faculty content-assistant draft (§13.3.1). ALWAYS status='draft' —
    drafts are never auto-published."""
    __tablename__ = "ai_drafts13"

    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                           nullable=True, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                          nullable=True, index=True)
    kind = db.Column(db.String(20), nullable=False,
                     default="lesson-outline")  # lesson-outline|quiz-draft|assignment-draft
    topic = db.Column(db.String(200), nullable=False, default="")
    content = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False,
                       default=DRAFT_STATUS_DRAFT)  # always 'draft'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    faculty = db.relationship("User", foreign_keys=[faculty_id])
    course = db.relationship("Course", foreign_keys=[course_id])


class Rubric13(db.Model):
    """Faculty-created evaluation rubric (§13.3.2).

    criteria: [{name, weight}, ...]. Optionally scoped to a course and/or
    attached to a specific project (project_id)."""
    __tablename__ = "rubrics13"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                          nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"),
                           nullable=True, index=True)
    criteria = db.Column(db.JSON, default=list)  # [{name, weight}]
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"),
                           nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", foreign_keys=[course_id])
    project = db.relationship("Project", foreign_keys=[project_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    @property
    def total_weight(self):
        try:
            return sum(float(c.get("weight", 0)) for c in (self.criteria or []))
        except (TypeError, ValueError):
            return 0.0


class ProjectEvaluation13(db.Model):
    """AI evaluation of a project submission (§13.3.2).

    Flow: created with status='pending_review' -> faculty reviews in
    /faculty/evaluations -> approved/rejected. ONLY approved evaluations
    are ever shown to the student."""
    __tablename__ = "project_evaluations13"

    id = db.Column(db.Integer, primary_key=True)
    project_submission_id = db.Column(
        db.Integer, db.ForeignKey("project_submissions.id"),
        nullable=False, index=True)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubrics13.id"),
                          nullable=False, index=True)
    scores = db.Column(db.JSON, default=dict)  # {criterion_name: 0-10 score}
    feedback_text = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False,
                       default="pending_review")  # pending_review|approved|rejected
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"),
                            nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    submission = db.relationship("ProjectSubmission", foreign_keys=[
        project_submission_id],
        backref=db.backref("ai_evaluations",
                           order_by="ProjectEvaluation13.evaluated_at.desc()"))
    rubric = db.relationship("Rubric13", foreign_keys=[rubric_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    def marks_for(self, max_marks):
        """Convert 0-10 per-criterion scores to marks out of max_marks."""
        if not self.rubric or not self.rubric.criteria:
            return 0.0
        total_w = self.rubric.total_weight or 1.0
        weighted = 0.0
        for c in self.rubric.criteria:
            name, weight = c.get("name", ""), float(c.get("weight", 0) or 0)
            try:
                score = float((self.scores or {}).get(name, 0) or 0)
            except (TypeError, ValueError):
                score = 0.0
            score = max(0.0, min(10.0, score))
            weighted += (score / 10.0) * weight
        return round(100.0 * weighted / total_w / 100.0 * (max_marks or 0), 2)


class AtRiskFlag13(db.Model):
    """Rules-based at-risk flag (§13.3.3).

    Staff-only. Students are NEVER notified automatically; see the
    guarantee banner on /counsellor/at-risk."""
    __tablename__ = "atrisk_flags13"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, index=True)
    reasons = db.Column(db.JSON, default=list)  # ["low_attendance:42%", ...]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])


class StudentMemory13(db.Model):
    """Cross-course student memory profile (§13.3.4)."""
    __tablename__ = "student_memory13"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False, unique=True, index=True)
    completed_topics = db.Column(db.JSON, default=list)  # ["Course — Lesson", ...]
    weak_topics = db.Column(db.JSON, default=list)  # [{course, lesson, misses}]
    strengths = db.Column(db.JSON, default=list)  # ["Course — Module", ...]
    preferences = db.Column(db.JSON, default=dict)  # {pace, language}
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
