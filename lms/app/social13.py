"""Phase 13, Stream 4 — Direct messaging (controlled student<->faculty)
+ public leaderboard (built on the Phase 8 points ledger).

Blueprint: social13_bp. All routes use full explicit paths; no url_prefix.

Registration (applied by the coordinator in app/__init__.py):
    from .social13 import social13_bp  # noqa: E402  (Phase 13: messaging + leaderboard)
    app.register_blueprint(social13_bp)
"""
from datetime import datetime

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from sqlalchemy import desc, func

from . import db
from .models import (Batch, BatchMember, Course, Enrollment, PointTransaction,
                     User, UserBadge)
from .models13_social import (Conversation13, DirectMessage13, PrivacyPrefs13)

social13_bp = Blueprint("social13", __name__)

# Roles allowed to INITIATE a conversation, and only with a student.
INITIATOR_ROLES = ("faculty", "admin", "counsellor")
STUDENT_ROLE = "student"
ADMIN_ROLE = "admin"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def mask_name(name):
    """Mask a display name for anonymous viewers: 'Aarav' -> 'A***v'."""
    n = (name or "").strip() or "?"
    if len(n) > 1:
        return "%s***%s" % (n[0], n[-1])
    return "%s***" % n[0]


def unread_dm_count(user_id):
    """Unread direct-message count for user_id (nav badge).

    Counts messages in non-archived conversations the user participates in,
    sent by someone else, and not yet opened (read_at is NULL).
    """
    conv_ids = db.session.query(Conversation13.id).filter(
        Conversation13.archived.is_(False),
        ((Conversation13.student_id == user_id)
         | (Conversation13.faculty_id == user_id)))
    return db.session.query(func.count(DirectMessage13.id)).filter(
        DirectMessage13.conversation_id.in_(conv_ids),
        DirectMessage13.sender_id != user_id,
        DirectMessage13.read_at.is_(None)).scalar() or 0


def _conv_for_user(conv_id):
    """Fetch a conversation with server-side access control.

    Participants (student or faculty side) may access their own threads;
    admins may view/moderate all. Anyone else gets 403.
    """
    conv = Conversation13.query.get(conv_id)
    if conv is None:
        abort(404)
    if (current_user.role != ADMIN_ROLE
            and conv.student_id != current_user.id
            and conv.faculty_id != current_user.id):
        abort(403)
    return conv


def _conv_unread(conv, user_id):
    return DirectMessage13.query.filter_by(conversation_id=conv.id).filter(
        DirectMessage13.sender_id != user_id,
        DirectMessage13.read_at.is_(None)).count()


def _last_message(conv_id):
    return (DirectMessage13.query
            .filter_by(conversation_id=conv_id)
            .order_by(DirectMessage13.created_at.desc(),
                      DirectMessage13.id.desc()).first())


# ---------------------------------------------------------------------------
# Direct messaging
# ---------------------------------------------------------------------------
@social13_bp.route("/messages")
@login_required
def inbox():
    """Inbox grouped by conversation, newest activity first, with per-thread
    unread counts. Admins see every conversation (moderation)."""
    q = Conversation13.query
    if current_user.role != ADMIN_ROLE:
        q = q.filter(((Conversation13.student_id == current_user.id)
                      | (Conversation13.faculty_id == current_user.id)))
    convs = q.order_by(Conversation13.last_message_at.desc().nullslast(),
                       Conversation13.created_at.desc()).all()
    open_convs, archived_convs = [], []
    for c in convs:
        entry = {"conv": c, "last": _last_message(c.id),
                 "unread": _conv_unread(c, current_user.id)}
        (archived_convs if c.archived else open_convs).append(entry)
    return render_template("p13_inbox.html", open_convs=open_convs,
                           archived_convs=archived_convs,
                           is_admin=current_user.role == ADMIN_ROLE,
                           can_initiate=current_user.role in INITIATOR_ROLES)


@social13_bp.route("/messages/new", methods=["GET", "POST"])
@login_required
def new_conversation():
    """Start a conversation. Only faculty/admin/counsellor may initiate,
    and only with a student. Reuses the open thread if one already exists."""
    if current_user.role not in INITIATOR_ROLES:
        abort(403)
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        subject = (request.form.get("subject") or "").strip()[:160]
        body = (request.form.get("body") or "").strip()
        target = User.query.get(student_id) if student_id else None
        if (not target or not target.is_active
                or target.role != STUDENT_ROLE or target.id == current_user.id):
            flash("Pick a valid active student to message.", "danger")
            return redirect(url_for("social13.new_conversation"))
        if not body:
            flash("Write a message to start the conversation.", "danger")
            return redirect(url_for("social13.new_conversation"))
        existing = Conversation13.query.filter_by(
            student_id=target.id, faculty_id=current_user.id,
            archived=False).first()
        if existing:
            flash("You already have an open conversation with this student.",
                  "info")
            return redirect(url_for("social13.thread", conv_id=existing.id))
        conv = Conversation13(student_id=target.id, faculty_id=current_user.id,
                              subject=subject or "(no subject)")
        db.session.add(conv)
        db.session.flush()
        db.session.add(DirectMessage13(conversation_id=conv.id,
                                       sender_id=current_user.id, body=body))
        conv.last_message_at = datetime.utcnow()
        db.session.commit()
        flash("Conversation started.", "success")
        return redirect(url_for("social13.thread", conv_id=conv.id))
    students = (User.query.filter_by(role=STUDENT_ROLE, is_active=True)
                .order_by(User.name).all())
    return render_template("p13_new.html", students=students)


@social13_bp.route("/messages/<int:conv_id>")
@login_required
def thread(conv_id):
    """Thread view. Opening the thread marks the other party's messages as
    read — but only for participants (admin moderation views never touch
    read state)."""
    conv = _conv_for_user(conv_id)
    if (conv.student_id == current_user.id
            or conv.faculty_id == current_user.id):
        now = datetime.utcnow()
        (DirectMessage13.query
         .filter_by(conversation_id=conv.id)
         .filter(DirectMessage13.sender_id != current_user.id,
                 DirectMessage13.read_at.is_(None))
         .update({"read_at": now}, synchronize_session=False))
        db.session.commit()
    msgs = (DirectMessage13.query
            .filter_by(conversation_id=conv.id)
            .order_by(DirectMessage13.created_at, DirectMessage13.id).all())
    can_reply = (conv.student_id == current_user.id
                 or conv.faculty_id == current_user.id)
    return render_template("p13_thread.html", conv=conv, msgs=msgs,
                           can_reply=can_reply,
                           is_admin=current_user.role == ADMIN_ROLE)


@social13_bp.route("/messages/<int:conv_id>/reply", methods=["POST"])
@login_required
def reply(conv_id):
    """Post a reply. Only conversation participants may post — a student
    can never send a message into someone else's thread."""
    conv = _conv_for_user(conv_id)
    if (conv.student_id != current_user.id
            and conv.faculty_id != current_user.id):
        abort(403)  # admins can view/moderate, not post
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Message cannot be empty.", "danger")
        return redirect(url_for("social13.thread", conv_id=conv.id))
    db.session.add(DirectMessage13(conversation_id=conv.id,
                                   sender_id=current_user.id, body=body))
    conv.last_message_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("social13.thread", conv_id=conv.id))


@social13_bp.route("/messages/<int:conv_id>/archive", methods=["POST"])
@login_required
def archive(conv_id):
    """Archive a conversation (participant or admin moderation)."""
    conv = _conv_for_user(conv_id)
    conv.archived = True
    db.session.commit()
    flash("Conversation archived.", "info")
    return redirect(url_for("social13.inbox"))


# ---------------------------------------------------------------------------
# Leaderboard (Phase 8 points ledger, read-only)
# ---------------------------------------------------------------------------
def _leaderboard_rows(course_id=None, batch_id=None):
    """Ranked leaderboard rows from the Phase 8 points ledger.

    Read-only SUM over point_transactions; opted-out users (PrivacyPrefs13)
    never appear; only users with > 0 points are listed.
    """
    allowed = None
    if course_id:
        allowed = {r[0] for r in db.session.query(Enrollment.user_id)
                   .filter(Enrollment.course_id == course_id).distinct()}
    elif batch_id:
        allowed = {r[0] for r in db.session.query(BatchMember.user_id)
                   .filter(BatchMember.batch_id == batch_id).distinct()}
    totals = (db.session.query(PointTransaction.user_id,
                               func.sum(PointTransaction.points).label("total"))
              .group_by(PointTransaction.user_id)
              .order_by(desc("total")).all())
    if not totals:
        return []
    opted_out = {p.user_id for p in PrivacyPrefs13.query
                 .filter_by(leaderboard_opt_out=True).all()}
    users = {u.id: u for u in User.query.filter(
        User.id.in_([t[0] for t in totals])).all()}
    badge_counts = dict(db.session.query(
        UserBadge.user_id, func.count(UserBadge.id))
        .group_by(UserBadge.user_id).all())
    rows = []
    rank = 0
    for uid, total in totals:
        if total is None or int(total) <= 0:
            continue
        if uid in opted_out:
            continue
        if allowed is not None and uid not in allowed:
            continue
        u = users.get(uid)
        if not u or not u.is_active:
            continue
        rank += 1
        rows.append({"rank": rank, "user": u, "points": int(total),
                     "badges": badge_counts.get(uid, 0)})
    return rows


def _get_privacy(user_id):
    prefs = PrivacyPrefs13.query.filter_by(user_id=user_id).first()
    if not prefs:
        prefs = PrivacyPrefs13(user_id=user_id)
        db.session.add(prefs)
        db.session.commit()  # commit (not just flush): GET requests must not
        # leave an uncommitted row behind in a request-scoped session
    return prefs


@social13_bp.route("/leaderboard")
def leaderboard():
    """Public leaderboard with Platform / Course / Batch tabs.

    ?tab=platform|course|batch  ?course_id=  ?batch_id=
    Anonymous viewers see masked names ("A***v" style); opted-out users
    never appear.
    """
    tab = (request.args.get("tab") or "platform").strip().lower()
    if tab not in ("platform", "course", "batch"):
        tab = "platform"
    course = (Course.query.get(request.args.get("course_id", type=int))
              if tab == "course" else None)
    batch = (Batch.query.get(request.args.get("batch_id", type=int))
             if tab == "batch" else None)
    rows = []
    if tab == "platform" or (tab == "course" and course) or (tab == "batch" and batch):
        rows = _leaderboard_rows(
            course_id=course.id if course else None,
            batch_id=batch.id if batch else None)
    anon = not current_user.is_authenticated
    for r in rows:
        r["display_name"] = mask_name(r["user"].name) if anon else r["user"].name
    prefs = _get_privacy(current_user.id) if current_user.is_authenticated else None
    return render_template("p13_leaderboard.html", tab=tab, rows=rows,
                           course=course, batch=batch,
                           courses=Course.query.order_by(Course.title).all(),
                           batches=Batch.query.order_by(Batch.name).all(),
                           prefs=prefs)


@social13_bp.route("/leaderboard/privacy", methods=["POST"])
@login_required
def leaderboard_privacy():
    """Toggle the current user's leaderboard opt-out."""
    prefs = _get_privacy(current_user.id)
    prefs.leaderboard_opt_out = bool(request.form.get("opt_out"))
    prefs.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Leaderboard privacy updated.", "success")
    return redirect(url_for("social13.leaderboard"))
