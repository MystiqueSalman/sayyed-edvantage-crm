"""Faculty dashboard. Content management lives in manage_bp (shared)."""
from flask import Blueprint, abort, render_template
from flask_login import current_user

from . import db
from .ai_tutor import weak_topics_for_course
from .decorators import role_required
from .models import Assignment, Course, Submission

faculty_bp = Blueprint("faculty", __name__)


@faculty_bp.route("/faculty")
@role_required("faculty")
def dashboard():
    courses = Course.query.filter_by(instructor_id=current_user.id).all()
    course_ids = [c.id for c in courses]
    pending = 0
    if course_ids:
        pending = (Submission.query.join(Assignment)
                   .filter(Assignment.course_id.in_(course_ids),
                           Submission.grade.is_(None)).count())
    return render_template("faculty_dashboard.html", courses=courses, pending=pending)


@faculty_bp.route("/faculty/weak-topics/<int:course_id>")
@role_required("faculty", "admin", "manager")
def weak_topics(course_id):
    """Phase 5: which topics students struggle with most (faculty view)."""
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    if (current_user.role == "faculty"
            and course.instructor_id != current_user.id):
        abort(403)
    topics = weak_topics_for_course(course_id)
    return render_template("faculty_weak_topics.html", course=course,
                           topics=topics)
