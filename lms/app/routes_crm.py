"""Phase 4 routes: CRM & leads, admissions, batches, AI sales-agent chat.

Public: /enquiry, /apply, /api/chat.
CRM (admin/manager/counsellor): /crm/leads..., /crm/followups, /crm/analytics,
    /crm/applications..., /crm/batches... (batches: counsellor view-only).
Student: /onboarding/toggle/<key>.
"""
import os
import secrets
import time
import uuid
from datetime import date, datetime

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user
from werkzeug.utils import secure_filename

from . import db
from .decorators import role_required
from .models import (AISettings, Application, ApplicationSettings, Batch,
                     BatchMember, ChatConversation, ChatMessage, Course,
                     Enrollment, Lead, OnboardingTask, User,
                     ROLE_COUNSELLOR)

crm_bp = Blueprint("crm", __name__)

crm_required = role_required("admin", "manager", ROLE_COUNSELLOR)
batch_manage = role_required("admin", "manager")
student_only = role_required("student")

ALLOWED_DOC_EXTS = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}

ONBOARDING_ITEMS = [
    ("complete_profile", "Complete your profile", "Add your mobile number so we can reach you."),
    ("orientation", "Attend the orientation class", "Join the welcome live class for your batch."),
    ("install_app", "Install the app", "Add Sayyed EdVantage to your phone home screen."),
    ("first_lesson", "Finish your first lesson", "Open any lesson from your course and mark it done."),
    ("community", "Say hello in discussions", "Introduce yourself in your course discussion board."),
]


def _onboarding_for(user):
    """Return list of (key, title, desc, done) for a student."""
    existing = {t.key: t for t in OnboardingTask.query.filter_by(user_id=user.id)}
    out = []
    for key, title, desc in ONBOARDING_ITEMS:
        task = existing.get(key)
        done = bool(task and task.done)
        if key == "complete_profile" and (user.phone or "").strip():
            done = True
        out.append({"key": key, "title": title, "desc": desc, "done": done})
    return out


# ================================================================ PUBLIC: enquiry
@crm_bp.route("/enquiry", methods=["GET", "POST"])
def enquiry():
    from .crm import create_lead
    courses = Course.query.filter_by(is_bonus=False).order_by(Course.title).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        course_id = request.form.get("course_id", "").strip()
        message = request.form.get("message", "").strip()
        if not name or not phone:
            flash("Please share your name and phone number.", "danger")
        else:
            try:
                lead = create_lead(
                    name=name, phone=phone, email=email,
                    source=Lead.SOURCE_WEBSITE,
                    course_id=int(course_id) if course_id.isdigit() else None,
                    note=f"Enquiry: {message}" if message else "")
                db.session.commit()
                flash("Thanks! Our counsellor will call you shortly. 🎉", "success")
                return redirect(url_for("main.index"))
            except Exception:
                db.session.rollback()
                flash("Something went wrong — please try again.", "danger")
    return render_template("enquiry.html", courses=courses)


# ================================================================ PUBLIC: application form
@crm_bp.route("/apply", methods=["GET", "POST"])
def apply():
    settings = ApplicationSettings.get()
    courses = Course.query.filter_by(is_bonus=False).order_by(Course.title).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        course_id = request.form.get("course_id", "").strip()
        education = request.form.get("education", "").strip() if settings.enable_education else ""
        batch_timing = request.form.get("batch_timing", "").strip() if settings.enable_batch_timing else ""
        if not name or not phone or not email:
            flash("Name, phone and email are required.", "danger")
            return render_template("apply.html", courses=courses, settings=settings)
        doc_path = ""
        if settings.enable_document and "document" in request.files:
            f = request.files["document"]
            if f and f.filename:
                ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
                if ext not in ALLOWED_DOC_EXTS:
                    flash("Document must be PDF/DOC/PNG/JPG.", "danger")
                    return render_template("apply.html", courses=courses, settings=settings)
                subdir = os.path.join(current_app.config["UPLOAD_DIR"], "applications")
                os.makedirs(subdir, exist_ok=True)
                fname = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
                f.save(os.path.join(subdir, fname))
                doc_path = f"applications/{fname}"
        app_obj = Application(
            name=name, phone=phone, email=email,
            course_id=int(course_id) if course_id.isdigit() else None,
            education=education, batch_timing=batch_timing,
            document_path=doc_path)
        db.session.add(app_obj)
        db.session.commit()
        # also drop a CRM lead so counsellors can follow up
        try:
            from .crm import create_lead
            lead = create_lead(name=name, phone=phone, email=email,
                               source=Lead.SOURCE_WEBSITE,
                               course_id=app_obj.course_id,
                               note="Submitted admission application.")
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash("Application submitted! Our counsellor will contact you soon. ✅", "success")
        return redirect(url_for("main.index"))
    return render_template("apply.html", courses=courses, settings=settings)


# ================================================================ AI SALES AGENT chat API
_chat_hits = {}  # ip -> [timestamps], light in-memory throttle


def _throttled(ip):
    now = time.time()
    hits = [t for t in _chat_hits.get(ip, []) if now - t < 3600]
    _chat_hits[ip] = hits
    if len(hits) >= 30:
        return True
    hits.append(now)
    return False


@crm_bp.route("/api/chat/status")
def chat_status():
    from .ai_agent import openai_available
    return jsonify({"available": True, "ai": openai_available()})


@crm_bp.route("/api/chat", methods=["POST"])
def chat():
    from .ai_agent import CHAT_UNAVAILABLE, agent_reply
    from .crm import create_lead, refresh_score, set_status
    ip = request.remote_addr or "?"
    if _throttled(ip):
        return jsonify({"reply": "You're sending messages too fast — please wait a bit. 🙂",
                        "conversation_id": request.json.get("conversation_id", "")}), 429
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()[:1000]
    conv_id = (data.get("conversation_id") or "").strip()
    if not message:
        return jsonify({"reply": "Please type a message. 🙂",
                        "conversation_id": conv_id})
    conv = ChatConversation.query.get(conv_id) if conv_id else None
    if conv is None:
        import hashlib
        conv = ChatConversation(
            id=uuid.uuid4().hex,
            ip_hash=hashlib.sha256(ip.encode()).hexdigest()[:32])
        db.session.add(conv)
        db.session.commit()
    db.session.add(ChatMessage(conversation_id=conv.id, role="user", text=message))
    db.session.commit()

    reply, flags = agent_reply(message, conv)
    db.session.add(ChatMessage(conversation_id=conv.id, role="assistant", text=reply))

    # --- lead capture & intent handling (fail-safe) ---
    try:
        lead = conv.lead or None
        if flags.get("phone"):
            lead = create_lead(name=flags.get("name") or "Chat visitor",
                               phone=flags["phone"], source=Lead.SOURCE_CHAT,
                               note="Shared number in AI chat.")
            if not conv.lead_id:
                conv.lead_id = lead.id
            if flags.get("name") and lead.name in ("Chat visitor", ""):
                lead.name = flags["name"]
            lead.follow_up_date = date.today()
            lead.log("system", "AI chat flagged HIGH-INTENT (phone shared).")
            lead.score = Lead.SCORE_HOT
        elif flags.get("name") and lead and lead.name in ("Chat visitor", ""):
            lead.name = flags["name"]
        if flags.get("fee_asked"):
            conv.fee_asks = (conv.fee_asks or 0) + 1
        if flags.get("high_intent") or (conv.fee_asks or 0) >= 2:
            if lead is None:
                lead = create_lead(name=flags.get("name") or "Chat visitor",
                                   source=Lead.SOURCE_CHAT,
                                   note="High-intent chat visitor (no phone yet).")
                if not conv.lead_id:
                    conv.lead_id = lead.id
            lead.log("system", "AI chat flagged HIGH-INTENT.")
            lead.score = Lead.SCORE_HOT
            if not lead.follow_up_date:
                lead.follow_up_date = date.today()
        if lead:
            refresh_score(lead)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({"reply": reply, "conversation_id": conv.id})


# ================================================================ CRM: leads
@crm_bp.route("/crm/leads")
@crm_required
def leads():
    q = Lead.query
    status = request.args.get("status", "")
    source = request.args.get("source", "")
    course_id = request.args.get("course_id", "")
    assignee = request.args.get("assignee", "")
    followup = request.args.get("followup", "")
    search = request.args.get("q", "").strip()
    if status in Lead.PIPELINE:
        q = q.filter(Lead.status == status)
    if source in Lead.SOURCES:
        q = q.filter(Lead.source == source)
    if course_id.isdigit():
        q = q.filter(Lead.course_id == int(course_id))
    if assignee.isdigit():
        q = q.filter(Lead.assigned_to == int(assignee))
    if followup == "due":
        q = q.filter(Lead.follow_up_date.isnot(None),
                     Lead.follow_up_date <= date.today(),
                     ~Lead.status.in_([Lead.STATUS_ENROLLED, Lead.STATUS_ADMITTED]))
    if search:
        like = f"%{search}%"
        q = q.filter((Lead.name.ilike(like)) | (Lead.phone.ilike(like))
                     | (Lead.email.ilike(like)))
    items = q.order_by(Lead.updated_at.desc()).limit(200).all()
    courses = Course.query.filter_by(is_bonus=False).order_by(Course.title).all()
    staff = User.query.filter(User.role.in_(["admin", "manager", "counsellor"]),
                              User.is_active.is_(True)).all()
    return render_template("crm_leads.html", leads=items, courses=courses,
                           staff=staff, f=request.args,
                           pipeline=Lead.PIPELINE, labels=Lead.LABELS,
                           sources=Lead.SOURCES, scores=Lead.SCORES)


@crm_bp.route("/crm/leads/new", methods=["POST"])
@crm_required
def lead_new():
    from .crm import create_lead
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    course_id = request.form.get("course_id", "")
    if not name or not phone:
        flash("Name and phone are required.", "danger")
        return redirect(url_for("crm.leads"))
    lead = create_lead(name=name, phone=phone, email=email,
                       source=Lead.SOURCE_MANUAL,
                       course_id=int(course_id) if course_id.isdigit() else None,
                       actor_id=current_user.id, note="Added manually.")
    db.session.commit()
    flash("Lead added.", "success")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.route("/crm/leads/<int:lead_id>")
@crm_required
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    staff = User.query.filter(User.role.in_(["admin", "manager", "counsellor"]),
                              User.is_active.is_(True)).all()
    return render_template("crm_lead_detail.html", lead=lead, staff=staff,
                           pipeline=Lead.PIPELINE, labels=Lead.LABELS,
                           scores=Lead.SCORES)


@crm_bp.route("/crm/leads/<int:lead_id>/status", methods=["POST"])
@crm_required
def lead_status(lead_id):
    from .crm import refresh_score, set_status
    lead = Lead.query.get_or_404(lead_id)
    try:
        changed = set_status(lead, request.form.get("status", ""),
                             actor_id=current_user.id,
                             note=request.form.get("note", "").strip())
        refresh_score(lead)
        db.session.commit()
        flash("Status updated." if changed else "Status unchanged.", "success")
    except ValueError:
        db.session.rollback()
        flash("Invalid status.", "danger")
    except Exception:
        db.session.rollback()
        flash("Could not update status.", "danger")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.route("/crm/leads/<int:lead_id>/note", methods=["POST"])
@crm_required
def lead_note(lead_id):
    from .crm import add_note, refresh_score
    lead = Lead.query.get_or_404(lead_id)
    text = request.form.get("text", "").strip()
    fu = request.form.get("follow_up_date", "").strip()
    follow_up = None
    if fu:
        try:
            follow_up = date.fromisoformat(fu)
        except ValueError:
            flash("Follow-up date must be YYYY-MM-DD.", "danger")
            return redirect(url_for("crm.lead_detail", lead_id=lead.id))
    if not text and not follow_up:
        flash("Write a note or set a follow-up date.", "warning")
        return redirect(url_for("crm.lead_detail", lead_id=lead.id))
    add_note(lead, text or "(follow-up scheduled)", actor_id=current_user.id,
             follow_up=follow_up)
    refresh_score(lead)
    db.session.commit()
    flash("Note saved.", "success")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.route("/crm/leads/<int:lead_id>/assign", methods=["POST"])
@crm_required
def lead_assign(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    uid = request.form.get("user_id", "")
    user = User.query.get(int(uid)) if uid.isdigit() else None
    if user and user.role in ("admin", "manager", "counsellor") and user.is_active:
        lead.assigned_to = user.id
        lead.log("system", f"Assigned to {user.name}.", actor_id=current_user.id)
        db.session.commit()
        flash(f"Assigned to {user.name}.", "success")
    else:
        flash("Pick an active admin/manager/counsellor.", "danger")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.route("/crm/leads/<int:lead_id>/score", methods=["POST"])
@crm_required
def lead_score(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    score = request.form.get("score", "")
    if score in Lead.SCORES:
        lead.score = score
        lead.log("system", f"Score manually set to {score}.",
                 actor_id=current_user.id)
        db.session.commit()
        flash(f"Score set to {score}.", "success")
    else:
        flash("Invalid score.", "danger")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.route("/crm/followups")
@crm_required
def followups():
    from .crm import todays_followups
    mine_only = request.args.get("mine", "")
    user = current_user if mine_only else None
    items = todays_followups(user)
    return render_template("crm_followups.html", items=items, mine=mine_only)


@crm_bp.route("/crm/analytics")
@crm_required
def analytics():
    from .crm import counsellor_stats, funnel_stats, source_stats
    counts, conversion = funnel_stats()
    return render_template("crm_analytics.html", counts=counts,
                           labels=Lead.LABELS, pipeline=Lead.PIPELINE,
                           conversion=conversion, sources=source_stats(),
                           staff=counsellor_stats())


# ================================================================ CRM: applications
@crm_bp.route("/crm/applications")
@crm_required
def applications():
    status = request.args.get("status", "")
    q = Application.query
    if status in (Application.STATUS_PENDING, Application.STATUS_APPROVED,
                  Application.STATUS_REJECTED):
        q = q.filter(Application.status == status)
    items = q.order_by(Application.created_at.desc()).limit(200).all()
    return render_template("crm_applications.html", items=items, f=status)


@crm_bp.route("/crm/applications/<int:app_id>")
@crm_required
def application_detail(app_id):
    app_obj = Application.query.get_or_404(app_id)
    return render_template("crm_application_detail.html", app_obj=app_obj)


@crm_bp.route("/crm/applications/<int:app_id>/approve", methods=["POST"])
@crm_required
def application_approve(app_id):
    from .crm import set_status as _set_status
    app_obj = Application.query.get_or_404(app_id)
    if app_obj.status != Application.STATUS_PENDING:
        flash("Application already reviewed.", "warning")
        return redirect(url_for("crm.application_detail", app_id=app_obj.id))
    mode = request.form.get("mode", "payment_pending")  # or "enrolled"
    # find or create the student account
    user = User.query.filter_by(email=app_obj.email).first()
    temp_pw = None
    if not user:
        user = User(name=app_obj.name, email=app_obj.email, role="student",
                    phone=app_obj.phone)
        temp_pw = secrets.token_urlsafe(9)
        user.set_password(temp_pw)
        db.session.add(user)
        db.session.flush()
    # enrollment per admin choice
    if app_obj.course_id:
        existing = Enrollment.query.filter_by(
            user_id=user.id, course_id=app_obj.course_id).first()
        if not existing:
            enr = Enrollment(user_id=user.id, course_id=app_obj.course_id,
                             status=(Enrollment.STATUS_ACTIVE
                                     if mode == "enrolled"
                                     else Enrollment.STATUS_PENDING),
                             paid=False, amount_paid=0)
            db.session.add(enr)
            db.session.flush()
    app_obj.status = Application.STATUS_APPROVED
    app_obj.created_user_id = user.id
    app_obj.reviewed_by = current_user.id
    app_obj.reviewed_at = datetime.utcnow()
    # link any matching CRM lead
    try:
        lead = Lead.query.filter_by(phone=app_obj.phone).first()
        if lead and lead.status != Lead.STATUS_ENROLLED:
            _set_status(lead, Lead.STATUS_ENROLLED, actor_id=current_user.id,
                        note=f"Application #{app_obj.id} approved.")
            lead.converted_user_id = user.id
    except Exception:
        pass
    db.session.commit()
    try:
        from .emailer import send_welcome_email
        send_welcome_email(user)
    except Exception:
        pass
    msg = f"Approved — account {'created' if temp_pw else 'found'} for {user.email}."
    if temp_pw:
        msg += f" Temporary password: {temp_pw} (share it securely, then ask the student to change it)."
    flash(msg, "success")
    return redirect(url_for("crm.application_detail", app_id=app_obj.id))


@crm_bp.route("/crm/applications/<int:app_id>/reject", methods=["POST"])
@crm_required
def application_reject(app_id):
    app_obj = Application.query.get_or_404(app_id)
    if app_obj.status != Application.STATUS_PENDING:
        flash("Application already reviewed.", "warning")
        return redirect(url_for("crm.application_detail", app_id=app_obj.id))
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("Please give a rejection reason.", "danger")
        return redirect(url_for("crm.application_detail", app_id=app_obj.id))
    app_obj.status = Application.STATUS_REJECTED
    app_obj.reject_reason = reason
    app_obj.reviewed_by = current_user.id
    app_obj.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash("Application rejected.", "info")
    return redirect(url_for("crm.application_detail", app_id=app_obj.id))


@crm_bp.route("/crm/application-settings", methods=["GET", "POST"])
@batch_manage
def application_settings():
    settings = ApplicationSettings.get()
    if request.method == "POST":
        settings.enable_education = bool(request.form.get("enable_education"))
        settings.enable_batch_timing = bool(request.form.get("enable_batch_timing"))
        settings.enable_document = bool(request.form.get("enable_document"))
        settings.intro_text = request.form.get("intro_text", "").strip()
        db.session.commit()
        flash("Application form settings saved.", "success")
        return redirect(url_for("crm.application_settings"))
    return render_template("crm_application_settings.html", settings=settings)


# ================================================================ CRM: batches
@crm_bp.route("/crm/batches")
@crm_required
def batches():
    items = Batch.query.order_by(Batch.created_at.desc()).all()
    courses = Course.query.filter_by(is_bonus=False).order_by(Course.title).all()
    faculty = User.query.filter_by(role="faculty", is_active=True).all()
    return render_template("crm_batches.html", items=items, courses=courses,
                           faculty=faculty)


@crm_bp.route("/crm/batches/new", methods=["POST"])
@batch_manage
def batch_new():
    name = request.form.get("name", "").strip()
    course_id = request.form.get("course_id", "")
    faculty_id = request.form.get("faculty_id", "")
    schedule_text = request.form.get("schedule_text", "").strip()
    start = request.form.get("start_date", "").strip()
    capacity = request.form.get("capacity", "50")
    if not name or not course_id.isdigit():
        flash("Batch name and course are required.", "danger")
        return redirect(url_for("crm.batches"))
    batch = Batch(name=name, course_id=int(course_id),
                  faculty_id=int(faculty_id) if faculty_id.isdigit() else None,
                  schedule_text=schedule_text,
                  start_date=date.fromisoformat(start) if start else None,
                  capacity=int(capacity) if capacity.isdigit() else 50)
    db.session.add(batch)
    db.session.commit()
    flash(f"Batch '{name}' created.", "success")
    return redirect(url_for("crm.batch_detail", batch_id=batch.id))


@crm_bp.route("/crm/batches/<int:batch_id>")
@crm_required
def batch_detail(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    return render_template("crm_batch_detail.html", batch=batch)


@crm_bp.route("/crm/batches/<int:batch_id>/members", methods=["POST"])
@batch_manage
def batch_add_member(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    email = request.form.get("email", "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or user.role != "student":
        flash("Enter the email of an enrolled student.", "danger")
        return redirect(url_for("crm.batch_detail", batch_id=batch.id))
    if len(batch.members) >= (batch.capacity or 50):
        flash("Batch is at full capacity.", "warning")
        return redirect(url_for("crm.batch_detail", batch_id=batch.id))
    if BatchMember.query.filter_by(batch_id=batch.id, user_id=user.id).first():
        flash("Student is already in this batch.", "warning")
    else:
        db.session.add(BatchMember(batch_id=batch.id, user_id=user.id))
        db.session.commit()
        flash(f"{user.name} added to {batch.name}.", "success")
    return redirect(url_for("crm.batch_detail", batch_id=batch.id))


@crm_bp.route("/crm/batches/<int:batch_id>/members/<int:member_id>/remove",
              methods=["POST"])
@batch_manage
def batch_remove_member(batch_id, member_id):
    member = BatchMember.query.filter_by(id=member_id,
                                         batch_id=batch_id).first_or_404()
    db.session.delete(member)
    db.session.commit()
    flash("Student removed from batch.", "info")
    return redirect(url_for("crm.batch_detail", batch_id=batch_id))


# ================================================================ STUDENT: onboarding
@crm_bp.route("/onboarding/toggle/<key>", methods=["POST"])
@student_only
def onboarding_toggle(key):
    valid = {k for k, _, _ in ONBOARDING_ITEMS}
    if key not in valid:
        return jsonify({"ok": False}), 400
    task = OnboardingTask.query.filter_by(user_id=current_user.id,
                                          key=key).first()
    if not task:
        task = OnboardingTask(user_id=current_user.id, key=key)
        db.session.add(task)
    task.done = not task.done
    task.done_at = datetime.utcnow() if task.done else None
    db.session.commit()
    return jsonify({"ok": True, "done": task.done})
