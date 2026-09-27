"""Faculty dashboard. Content management lives in manage_bp (shared)."""
from flask import Blueprint, render_template
from flask_login import current_user

from . import db
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
