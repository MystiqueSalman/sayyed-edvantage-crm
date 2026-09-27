"""Phase 9 — Faculty & operations routes (§4.3, §4.6, §18.4, §18.6, §11.4–11.5).

Registered as ops_bp. New routes enforce the granular permission matrix
(§18.3) via permission_required; faculty course scoping still goes through
User.can_manage_course.
"""
import csv
import io
import os
import tempfile
from datetime import date, datetime

from flask import (Blueprint, Response, abort, after_this_request, flash,
                   jsonify, redirect, render_template, request, send_file,
                   url_for)
from flask_login import current_user, login_required

from . import db
from .decorators import permission_required, role_required
from .models import (Announcement, Assignment, AuditLog, Batch, BatchMember,
                     Course, Enrollment, Invoice, InvoiceSetting, LiveSession,
                     Refund, RolePermission, SessionAttendance, User)
from . import operations as OPS

ops_bp = Blueprint("ops", __name__)

student_only = role_required("student")
manage_perm = permission_required  # alias for brevity


# ================================================================ live join + auto attendance (student)

@ops_bp.route("/live/join/<int:session_id>")
@login_required
def live_join(session_id):
    """Join a live class: auto-marks attendance (§4.3), then redirects out."""
    session = LiveSession.query.get_or_404(session_id)
    enr = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=session.course_id).first()
    if current_user.role not in ("admin", "manager", "faculty") and not enr:
        abort(403)
    if not session.is_joinable():
        flash("This session is not joinable right now.", "warning")
        return redirect(url_for("main.course_detail",
                                slug=session.course.slug))
    OPS.auto_mark_attendance(session, current_user)
    return redirect(session.join_url)


# ================================================================ calendar (§4.6)

@ops_bp.route("/calendar")
@login_required
def calendar():
    if current_user.role not in ("student", "faculty", "admin", "manager"):
        abort(403)
    return render_template("ops_calendar.html")


@ops_bp.route("/calendar/events")
@login_required
def calendar_events():
    return jsonify(OPS.calendar_events(current_user))


# ================================================================ attendance (§4.3)

def _session_course_or_403(session):
    course = session.course
    if not current_user.can_manage_course(course):
        abort(403)
    return course


@ops_bp.route("/manage/live/<int:session_id>/attendance", methods=["GET", "POST"])
@manage_perm("attendance", "view")
def session_attendance(session_id):
    session = LiveSession.query.get_or_404(session_id)
    _session_course_or_403(session)
    if request.method == "POST":
        if not OPS.has_permission(current_user, "attendance", "edit"):
            abort(403)
        enrolls = Enrollment.query.filter_by(
            course_id=session.course_id).all()
        for e in enrolls:
            status = request.form.get(f"status_{e.user_id}", "")
            dur = request.form.get(f"dur_{e.user_id}", "")
            if status in SessionAttendance.STATUSES:
                try:
                    dur_min = int(dur) if dur.strip() else None
                except ValueError:
                    dur_min = None
                OPS.manual_mark_attendance(session, e.user_id, status,
                                           current_user, dur_min)
        OPS.audit(current_user, "attendance.mark", "live_session",
                  session.id, f"Marked attendance for '{session.title}'",
                  request.remote_addr)
        flash("Attendance saved.", "success")
        return redirect(url_for("ops.session_attendance",
                                session_id=session.id))
    report = OPS.attendance_report(session.course_id)
    rec_by_user = {}
    for r in SessionAttendance.query.filter_by(
            session_id=session.id).all():
        rec_by_user[r.user_id] = r
    return render_template("ops_attendance_mark.html", session=session,
                           report=report, rec_by_user=rec_by_user)


@ops_bp.route("/manage/course/<int:course_id>/attendance")
@manage_perm("attendance", "view")
def course_attendance(course_id):
    course = Course.query.get_or_404(course_id)
    if not current_user.can_manage_course(course):
        abort(403)
    report = OPS.attendance_report(course_id)
    if request.args.get("format") == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        header = ["Student", "Email"] + [s.title for s in report["sessions"]] \
            + ["Present", "Total", "Percent"]
        w.writerow(header)
        for st in report["students"]:
            row = [st["user"].name, st["user"].email]
            for s in report["sessions"]:
                row.append(st["records"].get(s.id, "—"))
            row += [st["present"], st["total"], st["percent"]]
            w.writerow(row)
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition":
                                 f"attachment; filename=attendance-course-{course_id}.csv"})
    return render_template("ops_attendance_report.html", course=course,
                           report=report)


# ================================================================ batches (§18.4)

@ops_bp.route("/manage/batches", methods=["GET", "POST"])
@manage_perm("batches", "view")
def batch_list():
    if request.method == "POST":
        if not OPS.has_permission(current_user, "batches", "create"):
            abort(403)
        name = request.form.get("name", "").strip()
        course_id = request.form.get("course_id", type=int)
        faculty_id = request.form.get("faculty_id", type=int) or None
        start = _parse_date(request.form.get("start_date", ""))
        end = _parse_date(request.form.get("end_date", ""))
        try:
            capacity = int(request.form.get("capacity", 50) or 50)
        except ValueError:
            capacity = 50
        course = Course.query.get(course_id)
        if not name or not course:
            flash("Name and course are required.", "danger")
        else:
            b = Batch(name=name, course_id=course.id, faculty_id=faculty_id,
                      schedule_text=request.form.get("schedule_text", ""),
                      start_date=start, end_date=end,
                      capacity=max(1, capacity))
            db.session.add(b)
            db.session.commit()
            OPS.audit(current_user, "batch.create", "batch", b.id,
                      f"Created batch '{name}' for {course.title}",
                      request.remote_addr)
            flash(f"Batch '{name}' created.", "success")
        return redirect(url_for("ops.batch_list"))
    batches = Batch.query.order_by(Batch.created_at.desc()).all()
    courses = Course.query.order_by(Course.title).all()
    faculty = User.query.filter_by(role="faculty", is_active=True).all()
    return render_template("ops_batch_list.html", batches=batches,
                           courses=courses, faculty=faculty)


@ops_bp.route("/manage/batches/<int:batch_id>", methods=["GET", "POST"])
@manage_perm("batches", "view")
def batch_detail(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if request.method == "POST":
        if not OPS.has_permission(current_user, "batches", "edit"):
            abort(403)
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or user.role != "student":
            flash("Enter the email of a registered student.", "danger")
        else:
            ok, msg = OPS.enroll_in_batch(batch, user)
            flash(msg, "success" if ok else "danger")
            if ok:
                OPS.audit(current_user, "batch.enroll", "batch", batch.id,
                          f"Added {user.email} to '{batch.name}'",
                          request.remote_addr)
        return redirect(url_for("ops.batch_detail", batch_id=batch.id))
    summary = OPS.batch_summary(batch)
    batch_announcements = (Announcement.query
                           .filter_by(batch_id=batch.id, active=True)
                           .order_by(Announcement.created_at.desc()).all())
    return render_template("ops_batch_detail.html", summary=summary,
                           batch_announcements=batch_announcements)


@ops_bp.route("/manage/batches/<int:batch_id>/remove/<int:user_id>",
              methods=["POST"])
@manage_perm("batches", "edit")
def batch_remove(batch_id, user_id):
    batch = Batch.query.get_or_404(batch_id)
    m = BatchMember.query.filter_by(
        batch_id=batch.id, user_id=user_id).first_or_404()
    email = m.user.email
    db.session.delete(m)
    db.session.commit()
    OPS.audit(current_user, "batch.remove", "batch", batch.id,
              f"Removed {email} from '{batch.name}'", request.remote_addr)
    flash("Student removed from batch.", "info")
    return redirect(url_for("ops.batch_detail", batch_id=batch.id))


def _parse_date(value):
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


# ================================================================ audit logs (§18.6)

@ops_bp.route("/admin/audit-logs")
@manage_perm("audit_logs", "view")
def audit_logs():
    q = AuditLog.query
    action = request.args.get("action", "").strip()
    actor = request.args.get("actor", "").strip()
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if actor:
        q = q.filter(AuditLog.actor_email.ilike(f"%{actor}%"))
    logs = q.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("ops_audit_logs.html", logs=logs,
                           action=action, actor=actor)


# ================================================================ permissions (§18.3)

@ops_bp.route("/admin/permissions", methods=["GET", "POST"])
@manage_perm("permissions", "view")
def permissions():
    if request.method == "POST":
        if not OPS.has_permission(current_user, "permissions", "edit"):
            abort(403)
        OPS.ensure_permission_defaults()
        # Reset all non-admin rows, then apply the checked boxes
        # (unchecked boxes are absent from the form).
        for row in RolePermission.query.filter(
                RolePermission.role != "admin").all():
            row.can_view = row.can_create = row.can_edit = row.can_delete = False
        for key in request.form:
            if not key.startswith("p|"):
                continue
            # key: p|<role>|<module>|<action>
            parts = key.split("|")
            if len(parts) != 4:
                continue
            _, role, module, action = parts
            if role == "admin":
                continue
            row = RolePermission.query.filter_by(
                role=role, module=module).first()
            if row and action in ("view", "create", "edit", "delete"):
                setattr(row, f"can_{action}", True)
        db.session.commit()
        OPS.audit(current_user, "permissions.update", "role_permission",
                  None, "Permission matrix updated", request.remote_addr)
        flash("Permission matrix saved.", "success")
        return redirect(url_for("ops.permissions"))
    OPS.ensure_permission_defaults()
    rows = RolePermission.query.all()
    matrix = {}
    for r in rows:
        matrix.setdefault(r.role, {})[r.module] = r
    roles = ["admin", "manager", "faculty", "student", "counsellor",
             "employer"]
    return render_template("ops_permissions.html", matrix=matrix,
                           roles=roles, modules=OPS.PERMISSION_MODULES)


# ================================================================ invoices & finance (§11.4–11.5)

@ops_bp.route("/admin/invoice-settings", methods=["GET", "POST"])
@manage_perm("invoices", "edit")
def invoice_settings():
    settings = InvoiceSetting.get()
    if request.method == "POST":
        settings.business_name = request.form.get("business_name",
                                                  settings.business_name)
        settings.address = request.form.get("address", "")
        settings.email = request.form.get("email", "")
        settings.phone = request.form.get("phone", "")
        settings.gstin = request.form.get("gstin", "").strip().upper()
        settings.sac_code = request.form.get("sac_code", "999293").strip()
        try:
            settings.gst_rate = float(request.form.get("gst_rate", 18) or 18)
        except ValueError:
            pass
        settings.invoice_prefix = request.form.get("invoice_prefix",
                                                   "SE").strip() or "SE"
        settings.notes = request.form.get("notes", "")
        db.session.commit()
        OPS.audit(current_user, "invoice.settings", "invoice_setting", 1,
                  "Invoice business/tax details updated",
                  request.remote_addr)
        flash("Invoice settings saved.", "success")
        return redirect(url_for("ops.invoice_settings"))
    return render_template("ops_invoice_settings.html", settings=settings)


@ops_bp.route("/admin/invoices")
@manage_perm("invoices", "view")
def invoices():
    items = Invoice.query.order_by(Invoice.issued_at.desc()).all()
    unpaid = (Enrollment.query.filter_by(paid=True)
              .outerjoin(Invoice, Invoice.enrollment_id == Enrollment.id)
              .filter(Invoice.id.is_(None))
              .order_by(Enrollment.enrolled_at.desc()).all())
    return render_template("ops_invoices.html", invoices=items,
                           uninvoiced=unpaid)


@ops_bp.route("/admin/invoices/issue/<int:enrollment_id>", methods=["POST"])
@manage_perm("invoices", "create")
def invoice_issue(enrollment_id):
    enr = Enrollment.query.get_or_404(enrollment_id)
    inv = OPS.issue_invoice(enr, current_user)
    OPS.audit(current_user, "invoice.issue", "invoice", inv.id,
              f"Issued {inv.number} for {enr.user.email} / {enr.course.title}",
              request.remote_addr)
    flash(f"Invoice {inv.number} issued.", "success")
    return redirect(url_for("ops.invoice_view", invoice_id=inv.id))


@ops_bp.route("/admin/invoices/<int:invoice_id>")
@manage_perm("invoices", "view")
def invoice_view(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    settings = InvoiceSetting.get()
    return render_template("ops_invoice_view.html", inv=inv,
                           settings=settings)


@ops_bp.route("/admin/invoices/<int:invoice_id>/pdf")
@manage_perm("invoices", "view")
def invoice_pdf(invoice_id):
    from .pdfinvoice import generate_invoice_pdf
    inv = Invoice.query.get_or_404(invoice_id)
    settings = InvoiceSetting.get()
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    @after_this_request
    def _cleanup(response):
        try:
            os.unlink(path)
        except OSError:
            pass
        return response

    generate_invoice_pdf(inv, settings, path)
    return send_file(path, mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"{inv.number}.pdf")


@ops_bp.route("/admin/finance")
@manage_perm("finance", "view")
def finance():
    summary = OPS.finance_summary()
    return render_template("ops_finance.html", s=summary)


@ops_bp.route("/admin/finance.csv")
@manage_perm("finance", "view")
def finance_csv():
    summary = OPS.finance_summary()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Student", "Email", "Course", "Amount Paid (INR)",
                "Coupon", "Payment ID"])
    for e in summary["history"]:
        w.writerow([(e.enrolled_at or "").strftime("%Y-%m-%d")
                    if e.enrolled_at else "", e.user.name, e.user.email,
                    e.course.title if e.course else "",
                    e.amount_paid or 0, e.coupon_code or "",
                    e.razorpay_payment_id or ""])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=payment-history.csv"})


@ops_bp.route("/admin/refunds", methods=["GET", "POST"])
@manage_perm("refunds", "view")
def refunds():
    if request.method == "POST":
        if not OPS.has_permission(current_user, "refunds", "create"):
            abort(403)
        enr_id = request.form.get("enrollment_id", type=int)
        enr = Enrollment.query.get_or_404(enr_id)
        try:
            amount = int(request.form.get("amount", 0) or 0)
        except ValueError:
            amount = 0
        if not enr.paid or amount <= 0:
            flash("Refund needs a paid enrollment and a positive amount.",
                  "danger")
        else:
            r = Refund(enrollment_id=enr.id, user_id=enr.user_id,
                       course_id=enr.course_id, amount=amount,
                       reason=request.form.get("reason", ""),
                       requested_by=current_user.id)
            db.session.add(r)
            db.session.commit()
            OPS.audit(current_user, "refund.request", "refund", r.id,
                      f"Refund of Rs.{amount} requested for {enr.user.email}",
                      request.remote_addr)
            flash("Refund request recorded.", "success")
        return redirect(url_for("ops.refunds"))
    items = Refund.query.order_by(Refund.created_at.desc()).all()
    paid_enrollments = (Enrollment.query.filter_by(paid=True)
                        .order_by(Enrollment.enrolled_at.desc())
                        .limit(100).all())
    return render_template("ops_refunds.html", refunds=items,
                           enrollments=paid_enrollments)


@ops_bp.route("/admin/refunds/<int:refund_id>/<decision>", methods=["POST"])
@manage_perm("refunds", "edit")
def refund_decide(refund_id, decision):
    r = Refund.query.get_or_404(refund_id)
    if decision == "approve":
        r.status = Refund.STATUS_APPROVED
    elif decision == "reject":
        r.status = Refund.STATUS_REJECTED
    else:
        abort(404)
    r.decided_by = current_user.id
    r.decided_at = datetime.utcnow()
    db.session.commit()
    OPS.audit(current_user, f"refund.{decision}", "refund", r.id,
              f"Refund of Rs.{r.amount} {decision}d for {r.user.email}",
              request.remote_addr)
    flash(f"Refund {decision}d.", "success" if decision == "approve"
          else "info")
    return redirect(url_for("ops.refunds"))
