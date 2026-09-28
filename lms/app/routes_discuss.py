"""Course discussions: threads + replies per course.

Students (enrolled) and faculty/admin/manager can post. Faculty and admin can
pin and delete threads.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import db
from .models import Course, Discussion, DiscussionReply, Enrollment

discuss_bp = Blueprint("discuss", __name__)

STAFF = ("admin", "manager", "faculty")


def _course_for_discussion(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    if current_user.role in STAFF:
        return course
    enr = Enrollment.query.filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course.id,
        Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                               Enrollment.STATUS_COMPLETED])).first()
    if not enr:
        abort(403)
    return course


@discuss_bp.route("/course/<slug>/discussions", methods=["GET", "POST"])
@login_required
def thread_list(slug):
    course = _course_for_discussion(slug)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title:
            flash("A title is required.", "danger")
        else:
            disc = Discussion(course_id=course.id, user_id=current_user.id,
                              title=title, body=body)
            db.session.add(disc)
            db.session.commit()
            # Phase 8: discussion points (students only earn these)
            if current_user.role == "student":
                from . import gamification as G
                G.award_points(current_user.id, "discussion_post",
                               "discussion", disc.id)
            flash("Discussion started.", "success")
            return redirect(url_for("discuss.thread_list", slug=slug))
    threads = (Discussion.query.filter_by(course_id=course.id)
               .order_by(Discussion.pinned.desc(),
                         Discussion.created_at.desc()).all())
    return render_template("discussions.html", course=course, threads=threads)


@discuss_bp.route("/discussion/<int:discussion_id>", methods=["GET", "POST"])
@login_required
def thread_view(discussion_id):
    disc = Discussion.query.get_or_404(discussion_id)
    course = _course_for_discussion(disc.course.slug)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            flash("Reply can't be empty.", "danger")
        else:
            reply = DiscussionReply(discussion_id=disc.id,
                                    user_id=current_user.id, body=body)
            db.session.add(reply)
            db.session.commit()
            # Phase 8: discussion points (students only earn these)
            if current_user.role == "student":
                from . import gamification as G
                G.award_points(current_user.id, "discussion_post",
                               "reply", reply.id)
            flash("Reply posted.", "success")
            return redirect(url_for("discuss.thread_view",
                                    discussion_id=disc.id))
    return render_template("discussion_thread.html", course=course, disc=disc)


@discuss_bp.route("/discussion/<int:discussion_id>/pin", methods=["POST"])
@login_required
def thread_pin(discussion_id):
    if current_user.role not in ("admin", "faculty"):
        abort(403)
    disc = Discussion.query.get_or_404(discussion_id)
    disc.pinned = not disc.pinned
    db.session.commit()
    flash("Thread " + ("pinned 📌" if disc.pinned else "unpinned."), "info")
    return redirect(url_for("discuss.thread_view", discussion_id=disc.id))


@discuss_bp.route("/discussion/<int:discussion_id>/delete", methods=["POST"])
@login_required
def thread_delete(discussion_id):
    if current_user.role not in ("admin", "faculty"):
        abort(403)
    disc = Discussion.query.get_or_404(discussion_id)
    slug = disc.course.slug
    db.session.delete(disc)
    db.session.commit()
    flash("Discussion deleted.", "info")
    return redirect(url_for("discuss.thread_list", slug=slug))


@discuss_bp.route("/community")
@login_required
def community():
    """UI14: cross-course community index — recent threads everywhere."""
    threads = (Discussion.query.order_by(Discussion.created_at.desc())
               .limit(20).all())
    return render_template("community.html", threads=threads)
