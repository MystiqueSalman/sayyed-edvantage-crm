"""Phase 11 routes: marketing suite (§20).

Public: /p/<slug> (landing pages), /a/<code> (affiliate links),
/aff/<token> (affiliate dashboard).
Admin: /admin/marketing hub, landing pages, campaigns, email campaigns,
affiliates, analytics integrations.
"""
import csv
import io
import re
import secrets
from datetime import date, datetime

from flask import (Blueprint, flash, make_response, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from . import db
from .decorators import admin_required, manager_or_admin
from .marketing import (AFF_COOKIE, BLOCK_TYPES, CAMP_COOKIE,
                        campaign_recipients, create_lead_from_landing,
                        email_gate_ok, new_affiliate_code,
                        record_affiliate_earning, record_page_view,
                        resolve_affiliate, send_email_campaign,
                        starter_blocks)
from .models import (Affiliate, AffiliateClick, AffiliateEarning,
                     AffiliatePayout, AppSetting, Campaign, Course, Coupon,
                     EmailCampaign, LandingPage, Lead, MessageTemplate,
                     PageView)
from .operations import audit

marketing_bp = Blueprint("marketing", __name__)


def _slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "page"


# ============================================================ public: landing pages

@marketing_bp.route("/p/<slug>")
def landing_page(slug):
    page = LandingPage.query.filter_by(slug=slug).first_or_404()
    if not page.is_published:
        return render_template("marketing_404.html", page=page), 404
    camp_id = request.args.get("c")
    try:
        camp_id = int(camp_id) if camp_id else None
    except (TypeError, ValueError):
        camp_id = None
    if camp_id and not db.session.get(Campaign, camp_id):
        camp_id = None
    record_page_view(page, camp_id)
    courses = {c.id: c for c in Course.query.all()}
    countdown = None
    for b in (page.blocks or []):
        if b.get("type") == "countdown" and b.get("ends_at"):
            countdown = b.get("ends_at")
            break
    resp = make_response(render_template("marketing_landing.html", page=page,
                                          courses=courses,
                                          camp_id=camp_id,
                                          countdown=countdown))
    if camp_id:
        resp.set_cookie(CAMP_COOKIE, str(camp_id), max_age=30 * 24 * 3600,
                        httponly=True, samesite="Lax")
    aff_code = request.args.get("aff")
    if aff_code and resolve_affiliate(aff_code):
        resp.set_cookie(AFF_COOKIE, aff_code.upper(), max_age=30 * 24 * 3600,
                        httponly=True, samesite="Lax")
    return resp


@marketing_bp.route("/p/<slug>/lead", methods=["POST"])
def landing_lead(slug):
    page = LandingPage.query.filter_by(slug=slug).first_or_404()
    if not page.is_published:
        return render_template("marketing_404.html", page=page), 404
    camp_id = request.form.get("campaign_id")
    try:
        camp_id = int(camp_id) if camp_id else None
    except (TypeError, ValueError):
        camp_id = None
    aff = resolve_affiliate(request.cookies.get(AFF_COOKIE))
    lead, err = create_lead_from_landing(request.form, page, camp_id, aff)
    if err:
        flash(err, "warning")
        return redirect(url_for("marketing.landing_page", slug=slug))
    return render_template("marketing_thanks.html", page=page, lead=lead)


# ============================================================ public: affiliates

@marketing_bp.route("/a/<code>")
def affiliate_redirect(code):
    aff = Affiliate.query.filter_by(code=code.upper()).first_or_404()
    if aff.active:
        db.session.add(AffiliateClick(affiliate_id=aff.id))
        db.session.commit()
    resp = make_response(redirect(url_for("main.catalog")))
    if aff.active:
        resp.set_cookie(AFF_COOKIE, aff.code, max_age=30 * 24 * 3600,
                        httponly=True, samesite="Lax")
    return resp


@marketing_bp.route("/aff/<token>")
def affiliate_dash(token):
    aff = Affiliate.query.filter_by(token=token).first_or_404()
    stats = aff.stats()
    payouts = (AffiliatePayout.query
               .filter_by(affiliate_id=aff.id)
               .order_by(AffiliatePayout.created_at.desc()).all())
    earnings = (AffiliateEarning.query
                .filter_by(affiliate_id=aff.id)
                .order_by(AffiliateEarning.created_at.desc())
                .limit(50).all())
    link = url_for("marketing.affiliate_redirect", code=aff.code,
                   _external=True)
    return render_template("marketing_affiliate_dash.html", aff=aff,
                           stats=stats, payouts=payouts,
                           earnings=earnings, link=link)


# ============================================================ admin hub

@marketing_bp.route("/admin/marketing")
@manager_or_admin
def hub():
    pages = LandingPage.query.count()
    campaigns = Campaign.query.count()
    affiliates = Affiliate.query.filter_by(active=True).count()
    emailc = EmailCampaign.query.count()
    return render_template("marketing_hub.html", pages=pages,
                           campaigns=campaigns, affiliates=affiliates,
                           emailc=emailc)


# ============================================================ landing pages (admin)

@marketing_bp.route("/admin/landing-pages")
@manager_or_admin
def page_list():
    pages = LandingPage.query.order_by(
        LandingPage.updated_at.desc()).all()
    return render_template("marketing_pages.html", pages=pages)


@marketing_bp.route("/admin/landing-pages/new", methods=["GET", "POST"])
@manager_or_admin
def page_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        slug = _slugify(request.form.get("slug") or title)
        if LandingPage.query.filter_by(slug=slug).first():
            flash("That URL slug is already taken.", "warning")
            return render_template("marketing_page_form.html",
                                   title=title, slug=slug)
        page = LandingPage(title=title or "Untitled page", slug=slug,
                           status=request.form.get("status") or "draft",
                           blocks=starter_blocks())
        db.session.add(page)
        db.session.commit()
        audit(current_user, "landing_page.create",
              "landing_pages", page.id, page.title)
        flash("Landing page created — now edit the blocks.", "success")
        return redirect(url_for("marketing.page_edit", page_id=page.id))
    return render_template("marketing_page_form.html", title="", slug="")


@marketing_bp.route("/admin/landing-pages/<int:page_id>/edit",
                    methods=["GET", "POST"])
@manager_or_admin
def page_edit(page_id):
    page = LandingPage.query.get_or_404(page_id)
    if request.method == "POST":
        page.title = (request.form.get("title") or page.title).strip()
        slug = _slugify(request.form.get("slug") or page.slug)
        clash = LandingPage.query.filter(
            LandingPage.slug == slug, LandingPage.id != page.id).first()
        if clash:
            flash("That URL slug is already taken.", "warning")
        else:
            page.slug = slug
        page.status = request.form.get("status") or "draft"
        db.session.commit()
        audit(current_user, "landing_page.edit",
              "landing_pages", page.id, page.title)
        flash("Saved.", "success")
        return redirect(url_for("marketing.page_edit", page_id=page.id))
    courses = Course.query.order_by(Course.title).all()
    return render_template("marketing_page_edit.html", page=page,
                           courses=courses, block_types=BLOCK_TYPES)


@marketing_bp.route("/admin/landing-pages/<int:page_id>/blocks",
                    methods=["POST"])
@manager_or_admin
def block_add(page_id):
    page = LandingPage.query.get_or_404(page_id)
    btype = request.form.get("type")
    if btype not in BLOCK_TYPES:
        flash("Unknown block type.", "warning")
        return redirect(url_for("marketing.page_edit", page_id=page.id))
    block = {"type": btype,
             "heading": (request.form.get("heading") or "").strip(),
             "text": (request.form.get("text") or "").strip(),
             "button_text": (request.form.get("button_text") or "").strip(),
             "button_link": (request.form.get("button_link") or "").strip(),
             "ends_at": (request.form.get("ends_at") or "").strip()}
    if btype == "course_cards":
        ids = request.form.getlist("course_ids")
        block["course_ids"] = [int(i) for i in ids if i.isdigit()]
    if btype in ("testimonials", "faq"):
        block["items"] = [{"name": (request.form.get("item_name") or "").strip(),
                           "text": (request.form.get("item_text") or "").strip(),
                           "q": (request.form.get("item_q") or "").strip(),
                           "a": (request.form.get("item_a") or "").strip()}]
    blocks = list(page.blocks or [])
    blocks.append(block)
    page.blocks = blocks
    db.session.commit()
    flash("Block added.", "success")
    return redirect(url_for("marketing.page_edit", page_id=page.id))


@marketing_bp.route("/admin/landing-pages/<int:page_id>/blocks/<int:idx>"
                    "/delete", methods=["POST"])
@manager_or_admin
def block_delete(page_id, idx):
    page = LandingPage.query.get_or_404(page_id)
    blocks = list(page.blocks or [])
    if 0 <= idx < len(blocks):
        blocks.pop(idx)
        page.blocks = blocks
        db.session.commit()
        flash("Block removed.", "success")
    return redirect(url_for("marketing.page_edit", page_id=page.id))


# ============================================================ campaigns (admin)

@marketing_bp.route("/admin/campaigns")
@manager_or_admin
def campaign_list():
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    return render_template("marketing_campaigns.html", campaigns=campaigns)


@marketing_bp.route("/admin/campaigns/new", methods=["GET", "POST"])
@manager_or_admin
def campaign_new():
    pages = LandingPage.query.filter_by(status="published").all()
    coupons = Coupon.query.filter_by(active=True).all()
    if request.method == "POST":
        camp = Campaign(
            name=(request.form.get("name") or "").strip() or "Untitled",
            channel=request.form.get("channel") or "other",
            landing_page_id=int(request.form["landing_page_id"])
            if request.form.get("landing_page_id") else None,
            coupon_id=int(request.form["coupon_id"])
            if request.form.get("coupon_id") else None,
            budget=int(request.form["budget"])
            if request.form.get("budget", "").isdigit() else None,
            active=bool(request.form.get("active")),
        )
        for f in ("start_date", "end_date"):
            val = (request.form.get(f) or "").strip()
            if val:
                setattr(camp, f, date.fromisoformat(val))
        db.session.add(camp)
        db.session.commit()
        audit(current_user, "campaign.create",
              "campaigns", camp.id, camp.name)
        flash("Campaign created.", "success")
        return redirect(url_for("marketing.campaign_detail",
                                campaign_id=camp.id))
    return render_template("marketing_campaign_form.html", camp=None,
                           pages=pages, coupons=coupons,
                           channels=Campaign.CHANNELS)


@marketing_bp.route("/admin/campaigns/<int:campaign_id>/edit",
                    methods=["GET", "POST"])
@manager_or_admin
def campaign_edit(campaign_id):
    camp = Campaign.query.get_or_404(campaign_id)
    pages = LandingPage.query.filter_by(status="published").all()
    coupons = Coupon.query.filter_by(active=True).all()
    if request.method == "POST":
        camp.name = (request.form.get("name") or camp.name).strip()
        camp.channel = request.form.get("channel") or "other"
        camp.landing_page_id = int(request.form["landing_page_id"]) \
            if request.form.get("landing_page_id") else None
        camp.coupon_id = int(request.form["coupon_id"]) \
            if request.form.get("coupon_id") else None
        camp.budget = int(request.form["budget"]) \
            if request.form.get("budget", "").isdigit() else None
        camp.active = bool(request.form.get("active"))
        for f in ("start_date", "end_date"):
            val = (request.form.get(f) or "").strip()
            setattr(camp, f, date.fromisoformat(val) if val else None)
        db.session.commit()
        flash("Campaign saved.", "success")
        return redirect(url_for("marketing.campaign_detail",
                                campaign_id=camp.id))
    return render_template("marketing_campaign_form.html", camp=camp,
                           pages=pages, coupons=coupons,
                           channels=Campaign.CHANNELS)


@marketing_bp.route("/admin/campaigns/<int:campaign_id>")
@manager_or_admin
def campaign_detail(campaign_id):
    camp = Campaign.query.get_or_404(campaign_id)
    stats = camp.stats()
    leads = (Lead.query.filter_by(campaign_id=camp.id)
             .order_by(Lead.created_at.desc()).limit(50).all())
    track_url = ""
    if camp.landing_page and camp.landing_page.is_published:
        track_url = url_for("marketing.landing_page",
                            slug=camp.landing_page.slug,
                            c=camp.id, _external=True)
    return render_template("marketing_campaign_detail.html", camp=camp,
                           stats=stats, leads=leads, track_url=track_url)


@marketing_bp.route("/admin/campaigns/<int:campaign_id>/export.csv")
@manager_or_admin
def campaign_export(campaign_id):
    camp = Campaign.query.get_or_404(campaign_id)
    stats = camp.stats()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric", "value"])
    w.writerow(["campaign", camp.name])
    w.writerow(["channel", camp.channel])
    w.writerow(["views", stats["views"]])
    w.writerow(["leads", stats["leads"]])
    w.writerow(["enrollments", stats["enrollments"]])
    w.writerow(["cost_per_lead", stats["cost_per_lead"] or ""])
    w.writerow([])
    w.writerow(["lead_name", "phone", "email", "status", "created_at"])
    for l in Lead.query.filter_by(campaign_id=camp.id).all():
        w.writerow([l.name, l.phone, l.email, l.status, l.created_at])
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=campaign-{camp.id}.csv")
    return resp


# ============================================================ email campaigns (admin)

@marketing_bp.route("/admin/email-campaigns")
@manager_or_admin
def email_campaign_list():
    items = EmailCampaign.query.order_by(
        EmailCampaign.created_at.desc()).all()
    return render_template("marketing_email_campaigns.html", items=items,
                           gate_ok=email_gate_ok())


@marketing_bp.route("/admin/email-campaigns/new", methods=["GET", "POST"])
@manager_or_admin
def email_campaign_new():
    templates = MessageTemplate.query.filter_by(
        channel="email", is_active=True).all()
    courses = Course.query.order_by(Course.title).all()
    if request.method == "POST":
        seg = {"audience": request.form.get("audience") or "leads"}
        if request.form.get("course_id"):
            seg["course_id"] = int(request.form["course_id"])
        if request.form.get("status"):
            seg["status"] = request.form["status"]
        camp = EmailCampaign(
            name=(request.form.get("name") or "").strip() or "Untitled",
            template_id=int(request.form["template_id"])
            if request.form.get("template_id") else None,
            segment=seg)
        db.session.add(camp)
        db.session.commit()
        flash("Email campaign drafted.", "success")
        return redirect(url_for("marketing.email_campaign_list"))
    return render_template("marketing_email_campaign_form.html",
                           templates=templates, courses=courses,
                           statuses=Lead.PIPELINE)


@marketing_bp.route("/admin/email-campaigns/<int:campaign_id>/send",
                    methods=["POST"])
@manager_or_admin
def email_campaign_send(campaign_id):
    camp = EmailCampaign.query.get_or_404(campaign_id)
    ok, msg = send_email_campaign(camp)
    audit(current_user, "email_campaign.send",
          "email_campaigns", camp.id, f"{camp.name}: {msg}")
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("marketing.email_campaign_list"))


# ============================================================ affiliates (admin)

@marketing_bp.route("/admin/affiliates")
@manager_or_admin
def affiliate_list():
    affs = Affiliate.query.order_by(Affiliate.created_at.desc()).all()
    return render_template("marketing_affiliates.html", affs=affs)


@marketing_bp.route("/admin/affiliates/new", methods=["GET", "POST"])
@manager_or_admin
def affiliate_new():
    if request.method == "POST":
        aff = Affiliate(
            name=(request.form.get("name") or "").strip() or "Affiliate",
            contact=(request.form.get("contact") or "").strip(),
            code=(request.form.get("code") or "").strip().upper()
            or new_affiliate_code(),
            commission_type=request.form.get("commission_type")
            or Affiliate.COMM_FLAT,
            commission_value=float(request.form.get("commission_value") or 0),
            token=secrets.token_urlsafe(32),
            active=bool(request.form.get("active")),
        )
        if Affiliate.query.filter_by(code=aff.code).first():
            flash("That referral code is taken.", "warning")
            return render_template("marketing_affiliate_form.html", aff=None)
        db.session.add(aff)
        db.session.commit()
        audit(current_user, "affiliate.create",
              "affiliates", aff.id, aff.name)
        flash("Affiliate created.", "success")
        return redirect(url_for("marketing.affiliate_detail", aff_id=aff.id))
    return render_template("marketing_affiliate_form.html", aff=None)


@marketing_bp.route("/admin/affiliates/<int:aff_id>/edit",
                    methods=["GET", "POST"])
@manager_or_admin
def affiliate_edit(aff_id):
    aff = Affiliate.query.get_or_404(aff_id)
    if request.method == "POST":
        aff.name = (request.form.get("name") or aff.name).strip()
        aff.contact = (request.form.get("contact") or "").strip()
        aff.commission_type = request.form.get("commission_type") \
            or Affiliate.COMM_FLAT
        aff.commission_value = float(request.form.get("commission_value") or 0)
        aff.active = bool(request.form.get("active"))
        db.session.commit()
        flash("Affiliate saved.", "success")
        return redirect(url_for("marketing.affiliate_detail", aff_id=aff.id))
    return render_template("marketing_affiliate_form.html", aff=aff)


@marketing_bp.route("/admin/affiliates/<int:aff_id>")
@manager_or_admin
def affiliate_detail(aff_id):
    aff = Affiliate.query.get_or_404(aff_id)
    stats = aff.stats()
    payouts = (AffiliatePayout.query
               .filter_by(affiliate_id=aff.id)
               .order_by(AffiliatePayout.created_at.desc()).all())
    pending_earnings = (AffiliateEarning.query
                        .filter_by(affiliate_id=aff.id, status="pending")
                        .all())
    pending_total = round(sum(e.amount for e in pending_earnings), 2)
    link = url_for("marketing.affiliate_redirect", code=aff.code,
                   _external=True)
    dash = url_for("marketing.affiliate_dash", token=aff.token,
                   _external=True)
    return render_template("marketing_affiliate_detail.html", aff=aff,
                           stats=stats, payouts=payouts,
                           pending_total=pending_total,
                           pending_count=len(pending_earnings),
                           link=link, dash=dash)


@marketing_bp.route("/admin/affiliates/<int:aff_id>/payout", methods=["POST"])
@manager_or_admin
def affiliate_payout_create(aff_id):
    aff = Affiliate.query.get_or_404(aff_id)
    pending = (AffiliateEarning.query
               .filter_by(affiliate_id=aff.id, status="pending").all())
    total = round(sum(e.amount for e in pending), 2)
    if not pending:
        flash("Nothing pending to pay out.", "warning")
        return redirect(url_for("marketing.affiliate_detail", aff_id=aff.id))
    payout = AffiliatePayout(affiliate_id=aff.id, amount=total,
                             note=(request.form.get("note") or "").strip())
    db.session.add(payout)
    db.session.flush()
    for e in pending:
        e.payout_id = payout.id
    db.session.commit()
    audit(current_user, "affiliate.payout.create",
          "affiliate_payouts", payout.id, f"{aff.name}: ₹{total}")
    flash(f"Payout of ₹{total} created (pending).", "success")
    return redirect(url_for("marketing.affiliate_detail", aff_id=aff.id))


@marketing_bp.route("/admin/affiliates/payouts/<int:payout_id>/mark-paid",
                    methods=["POST"])
@manager_or_admin
def affiliate_payout_paid(payout_id):
    payout = AffiliatePayout.query.get_or_404(payout_id)
    if payout.status != "paid":
        payout.status = "paid"
        payout.paid_at = datetime.utcnow()
        for e in payout.earnings:
            e.status = "paid"
        db.session.commit()
        audit(current_user, "affiliate.payout.paid",
              "affiliate_payouts", payout.id,
              f"{payout.affiliate.name}: ₹{payout.amount}")
        flash("Payout marked as paid.", "success")
    return redirect(url_for("marketing.affiliate_detail",
                            aff_id=payout.affiliate_id))


# ============================================================ analytics integrations

@marketing_bp.route("/admin/analytics", methods=["GET", "POST"])
@admin_required
def analytics_settings():
    keys = [("analytics.ga4_id", "Google Analytics 4 ID (e.g. G-XXXXXXX)"),
            ("analytics.gtm_id", "Google Tag Manager ID (e.g. GTM-XXXXXXX)"),
            ("analytics.meta_pixel_id", "Meta Pixel ID"),
            ("analytics.head_snippet", "Custom <head> snippet (advanced)")]
    if request.method == "POST":
        for key, _label in keys:
            AppSetting.set(key, (request.form.get(key) or "").strip())
        audit(current_user, "analytics.settings",
              "app_settings", None, "updated")
        flash("Analytics settings saved.", "success")
        return redirect(url_for("marketing.analytics_settings"))
    values = {k: AppSetting.get(k, "") for k, _ in keys}
    return render_template("marketing_analytics.html", keys=keys,
                           values=values)
