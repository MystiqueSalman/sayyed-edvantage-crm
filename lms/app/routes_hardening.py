"""Phase 10 — hardening admin pages + notification center (§24, §25, §12.4, §12.5).

hardening_bp (/admin): API keys, webhooks, backups, message templates,
monitoring. notify_bp: per-user /notifications.
"""
import os
import secrets
from datetime import datetime

from flask import (Blueprint, flash, redirect, render_template, request,
                   send_file, url_for)
from flask_login import current_user, login_required

from . import db
from .decorators import admin_required
from .models import (ApiKey, Backup, MessageTemplate, Notification, Webhook,
                     WebhookDelivery)
from . import hardening as H
from . import operations as OPS

hardening_bp = Blueprint("hardening", __name__, url_prefix="/admin")
notify_bp = Blueprint("notify", __name__)


def _ip():
    return (request.headers.get("X-Forwarded-For", "") or
            request.remote_addr or "")[:64]


# ------------------------------------------------------------- API keys (§25)

@hardening_bp.route("/api-keys", methods=["GET", "POST"])
@admin_required
def api_keys():
    new_raw_key = None
    if request.method == "POST":
        from .api_v1 import issue_key
        name = request.form.get("name", "").strip()[:120]
        scopes = [s for s in request.form.getlist("scopes")
                  if s in ApiKey.SCOPES]
        try:
            rate = max(1, min(10000,
                              int(request.form.get("rate_limit", 300) or 300)))
        except ValueError:
            rate = 300
        if not name:
            flash("Give the key a name.", "danger")
        elif not scopes:
            flash("Select at least one scope.", "danger")
        else:
            key, raw = issue_key(name, scopes, rate,
                                 created_by_id=current_user.id)
            OPS.audit(current_user, "apikey.create", target_type="apikey",
                      target_id=key.id,
                      detail=f"Created API key '{name}' "
                             f"({key.key_prefix}…, scopes: "
                             f"{', '.join(scopes)})", ip=_ip())
            new_raw_key = raw
            flash("API key created — copy it now, it won't be shown again.",
                  "success")
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return render_template("admin_api_keys.html", keys=keys,
                           scopes=ApiKey.SCOPES, new_raw_key=new_raw_key)


@hardening_bp.route("/api-keys/<int:key_id>/revoke", methods=["POST"])
@admin_required
def api_key_revoke(key_id):
    key = db.session.get(ApiKey, key_id)
    if key:
        key.is_active = False
        db.session.commit()
        OPS.audit(current_user, "apikey.revoke", target_type="apikey",
                  target_id=key.id,
                  detail=f"Revoked API key '{key.name}' "
                         f"({key.key_prefix}…)", ip=_ip())
        flash("API key revoked.", "info")
    return redirect(url_for("hardening.api_keys"))


@hardening_bp.route("/api-keys/<int:key_id>/delete", methods=["POST"])
@admin_required
def api_key_delete(key_id):
    key = db.session.get(ApiKey, key_id)
    if key:
        OPS.audit(current_user, "apikey.delete", target_type="apikey",
                  target_id=key.id,
                  detail=f"Deleted API key '{key.name}' "
                         f"({key.key_prefix}…)", ip=_ip())
        db.session.delete(key)
        db.session.commit()
        flash("API key deleted.", "info")
    return redirect(url_for("hardening.api_keys"))


# ------------------------------------------------------------- webhooks (§25)

@hardening_bp.route("/webhooks", methods=["GET", "POST"])
@admin_required
def webhooks():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        url = request.form.get("url", "").strip()[:500]
        events = [e for e in request.form.getlist("events")
                  if e in Webhook.EVENTS]
        if not name or not url:
            flash("Name and URL are required.", "danger")
        elif not (url.startswith("https://") or url.startswith("http://")):
            flash("URL must start with http:// or https://.", "danger")
        elif not events:
            flash("Select at least one event.", "danger")
        else:
            wh = Webhook(name=name, url=url,
                         secret=secrets.token_urlsafe(32))
            wh.events = events
            db.session.add(wh)
            db.session.commit()
            OPS.audit(current_user, "webhook.create", target_type="webhook",
                      target_id=wh.id,
                      detail=f"Registered webhook '{name}' → {url} "
                             f"({', '.join(events)})", ip=_ip())
            flash("Webhook registered.", "success")
            return redirect(url_for("hardening.webhooks"))
    hooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    return render_template("admin_webhooks.html", hooks=hooks,
                           events=Webhook.EVENTS)


@hardening_bp.route("/webhooks/<int:wh_id>/toggle", methods=["POST"])
@admin_required
def webhook_toggle(wh_id):
    wh = db.session.get(Webhook, wh_id)
    if wh:
        wh.is_active = not wh.is_active
        db.session.commit()
        OPS.audit(current_user, "webhook.toggle", target_type="webhook",
                  target_id=wh.id,
                  detail=f"{'Enabled' if wh.is_active else 'Disabled'} "
                         f"webhook '{wh.name}'", ip=_ip())
    return redirect(url_for("hardening.webhooks"))


@hardening_bp.route("/webhooks/<int:wh_id>/regenerate", methods=["POST"])
@admin_required
def webhook_regenerate(wh_id):
    wh = db.session.get(Webhook, wh_id)
    if wh:
        wh.secret = secrets.token_urlsafe(32)
        db.session.commit()
        flash("Webhook secret regenerated — update the receiver.", "warning")
    return redirect(url_for("hardening.webhooks"))


@hardening_bp.route("/webhooks/<int:wh_id>/delete", methods=["POST"])
@admin_required
def webhook_delete(wh_id):
    wh = db.session.get(Webhook, wh_id)
    if wh:
        OPS.audit(current_user, "webhook.delete", target_type="webhook",
                  target_id=wh.id,
                  detail=f"Deleted webhook '{wh.name}' → {wh.url}",
                  ip=_ip())
        db.session.delete(wh)
        db.session.commit()
        flash("Webhook deleted.", "info")
    return redirect(url_for("hardening.webhooks"))


@hardening_bp.route("/webhooks/<int:wh_id>/deliveries")
@admin_required
def webhook_deliveries(wh_id):
    wh = db.session.get(Webhook, wh_id)
    if not wh:
        flash("Webhook not found.", "danger")
        return redirect(url_for("hardening.webhooks"))
    deliveries = (WebhookDelivery.query
                  .filter_by(webhook_id=wh.id)
                  .order_by(WebhookDelivery.created_at.desc())
                  .limit(100).all())
    return render_template("admin_webhook_deliveries.html", wh=wh,
                           deliveries=deliveries)


# -------------------------------------------------------------- backups (§24)

@hardening_bp.route("/backups", methods=["GET", "POST"])
@admin_required
def backups():
    if request.method == "POST":
        if "retention" in request.form:
            try:
                days = max(1, min(90, int(request.form.get(
                    "retention_days", 7) or 7)))
            except ValueError:
                days = 7
            H.get_setting("backup.retention_days", "7")  # ensure table read
            from .models import AppSetting
            AppSetting.set("backup.retention_days", str(days))
            AppSetting.set("backup.enabled",
                           "1" if request.form.get("backup_enabled") else "0")
            flash("Backup settings saved.", "success")
            return redirect(url_for("hardening.backups"))
    rows = H.list_backups()
    retention = H.retention_days()
    enabled = H.get_setting("backup.enabled", "1") == "1"
    return render_template("admin_backups.html", rows=rows,
                           retention=retention, enabled=enabled,
                           sqlite_mode=H.is_sqlite_mode())


@hardening_bp.route("/backups/create", methods=["POST"])
@admin_required
def backup_create():
    try:
        row = H.create_backup(note="manual")
    except Exception as exc:  # noqa: BLE001
        flash(f"Backup failed: {exc}", "danger")
        return redirect(url_for("hardening.backups"))
    OPS.audit(current_user, "backup.create", target_type="backup",
              target_id=row.id,
              detail=f"Created backup {row.filename} "
                     f"({row.size_bytes} bytes)", ip=_ip())
    flash(f"Backup created: {row.filename}", "success")
    return redirect(url_for("hardening.backups"))


@hardening_bp.route("/backups/<int:backup_id>/download")
@admin_required
def backup_download(backup_id):
    row = db.session.get(Backup, backup_id)
    if not row:
        flash("Backup not found.", "danger")
        return redirect(url_for("hardening.backups"))
    path = os.path.join(H.backup_dir(), row.filename)
    if not os.path.exists(path):
        flash("Backup file missing from disk.", "danger")
        return redirect(url_for("hardening.backups"))
    return send_file(path, as_attachment=True,
                     download_name=row.filename)


@hardening_bp.route("/backups/<int:backup_id>/delete", methods=["POST"])
@admin_required
def backup_delete(backup_id):
    row = db.session.get(Backup, backup_id)
    if row:
        try:
            p = os.path.join(H.backup_dir(), row.filename)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        OPS.audit(current_user, "backup.delete", target_type="backup",
                  target_id=row.id,
                  detail=f"Deleted backup {row.filename}", ip=_ip())
        db.session.delete(row)
        db.session.commit()
        flash("Backup deleted.", "info")
    return redirect(url_for("hardening.backups"))


@hardening_bp.route("/backups/<int:backup_id>/restore", methods=["POST"])
@admin_required
def backup_restore(backup_id):
    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != "RESTORE":
        flash("Restore cancelled — type RESTORE exactly to confirm.",
              "warning")
        return redirect(url_for("hardening.backups"))
    try:
        H.restore_backup(backup_id, actor=current_user)
    except Exception as exc:  # noqa: BLE001
        flash(f"Restore failed: {exc}", "danger")
        return redirect(url_for("hardening.backups"))
    flash("Database restored from backup. Review the data before "
          "continuing.", "success")
    return redirect(url_for("hardening.backups"))


# ----------------------------------------------------- templates (§12.5)

@hardening_bp.route("/templates", methods=["GET", "POST"])
@admin_required
def templates():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        event_key = request.form.get("event_key", "").strip()[:60]
        channel = request.form.get("channel", "notification")
        subject = request.form.get("subject", "").strip()[:200]
        body = request.form.get("body", "")
        if channel not in MessageTemplate.CHANNELS:
            channel = "notification"
        if not name:
            flash("Template name is required.", "danger")
        elif MessageTemplate.query.filter_by(name=name).first():
            flash("A template with that name already exists.", "danger")
        else:
            tpl = MessageTemplate(name=name, event_key=event_key,
                                  channel=channel, subject=subject,
                                  body=body, is_active=True)
            db.session.add(tpl)
            db.session.commit()
            OPS.audit(current_user, "template.create",
                      target_type="template", target_id=tpl.id,
                      detail=f"Created template '{name}' "
                             f"({channel}/{event_key or 'manual'})",
                      ip=_ip())
            flash("Template created.", "success")
            return redirect(url_for("hardening.templates"))
    rows = MessageTemplate.query.order_by(
        MessageTemplate.event_key, MessageTemplate.channel,
        MessageTemplate.name).all()
    return render_template("admin_templates.html", rows=rows,
                           channels=MessageTemplate.CHANNELS,
                           events=list(Webhook.EVENTS) + ["quiz.graded",
                                                          "assignment.graded",
                                                          "badge.earned",
                                                          "challenge.won",
                                                          "application.status",
                                                          "live.reminder"])


@hardening_bp.route("/templates/<int:tpl_id>/edit",
                    methods=["GET", "POST"])
@admin_required
def template_edit(tpl_id):
    tpl = db.session.get(MessageTemplate, tpl_id)
    if not tpl:
        flash("Template not found.", "danger")
        return redirect(url_for("hardening.templates"))
    if request.method == "POST":
        tpl.subject = request.form.get("subject", "").strip()[:200]
        tpl.body = request.form.get("body", "")
        tpl.event_key = request.form.get("event_key", "").strip()[:60]
        channel = request.form.get("channel", "notification")
        if channel in MessageTemplate.CHANNELS:
            tpl.channel = channel
        db.session.commit()
        flash("Template updated.", "success")
        return redirect(url_for("hardening.templates"))
    return render_template("admin_template_edit.html", tpl=tpl,
                           channels=MessageTemplate.CHANNELS,
                           sample=H.SAMPLE_CONTEXT,
                           rendered_subject=H.render_template_string(
                               tpl.subject, H.SAMPLE_CONTEXT),
                           rendered_body=H.render_template_string(
                               tpl.body, H.SAMPLE_CONTEXT))


@hardening_bp.route("/templates/<int:tpl_id>/preview")
@admin_required
def template_preview(tpl_id):
    tpl = db.session.get(MessageTemplate, tpl_id)
    if not tpl:
        flash("Template not found.", "danger")
        return redirect(url_for("hardening.templates"))
    return render_template("admin_template_edit.html", tpl=tpl,
                           channels=MessageTemplate.CHANNELS,
                           sample=H.SAMPLE_CONTEXT,
                           rendered_subject=H.render_template_string(
                               tpl.subject, H.SAMPLE_CONTEXT),
                           rendered_body=H.render_template_string(
                               tpl.body, H.SAMPLE_CONTEXT),
                           preview=True)


@hardening_bp.route("/templates/<int:tpl_id>/toggle", methods=["POST"])
@admin_required
def template_toggle(tpl_id):
    tpl = db.session.get(MessageTemplate, tpl_id)
    if tpl:
        tpl.is_active = not tpl.is_active
        db.session.commit()
        OPS.audit(current_user, "template.toggle", target_type="template",
                  target_id=tpl.id,
                  detail=f"{'Activated' if tpl.is_active else 'Deactivated'} "
                         f"template '{tpl.name}'", ip=_ip())
    return redirect(url_for("hardening.templates"))


@hardening_bp.route("/templates/<int:tpl_id>/delete", methods=["POST"])
@admin_required
def template_delete(tpl_id):
    tpl = db.session.get(MessageTemplate, tpl_id)
    if tpl:
        if (tpl.use_count or 0) > 0:
            # No hard delete of in-use templates — deactivate instead.
            tpl.is_active = False
            db.session.commit()
            flash(f"Template '{tpl.name}' has been used "
                  f"{tpl.use_count}× — deactivated instead of deleted.",
                  "warning")
        else:
            OPS.audit(current_user, "template.delete",
                      target_type="template", target_id=tpl.id,
                      detail=f"Deleted template '{tpl.name}'", ip=_ip())
            db.session.delete(tpl)
            db.session.commit()
            flash("Template deleted.", "info")
    return redirect(url_for("hardening.templates"))


# ----------------------------------------------------------- monitoring (§24)

@hardening_bp.route("/monitoring")
@admin_required
def monitoring():
    stats = H.request_stats()
    log_lines = H.tail_app_log(120)
    ok, checks = H.health_checks()
    return render_template("admin_monitoring.html", stats=stats,
                           log_lines=log_lines, health_ok=ok,
                           checks=checks)


# --------------------------------------------------- notification center (§12.4)

@notify_bp.route("/notifications")
@login_required
def notifications():
    rows = (Notification.query.filter_by(user_id=current_user.id)
            .order_by(Notification.created_at.desc()).limit(100).all())
    unread = sum(1 for r in rows if not r.is_read)
    return render_template("notifications.html", rows=rows, unread=unread)


@notify_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def notification_read(notif_id):
    n = db.session.get(Notification, notif_id)
    if n and n.user_id == current_user.id and not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for("notify.notifications"))


@notify_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def notifications_read_all():
    (Notification.query.filter_by(user_id=current_user.id, is_read=False)
     .update({"is_read": True, "read_at": datetime.utcnow()}))
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notify.notifications"))
