"""Phase 11 — Marketing suite (end-to-end).

Runs against a dev server on http://localhost:5000 with a FRESH DB
(migrated via `flask db upgrade` + seeded), same SQLITE_PATH for server and
this script. Mixes HTTP flows with in-process checks.

Every app-context block re-fetches its rows (never reuse ORM instances
across blocks — the session closes between them).

Coverage: landing page CRUD + publish toggle, lead capture with source,
campaign metrics math (views->leads->enrollments, CPL), CSV export,
email-campaign SMTP gate, affiliate click->lead->enrollment chain with
flat + percent commission, payout marking + audit log, analytics IDs on
public pages only, attribution lead.source -> enrollment, migration head.
"""
import os
import re
import secrets
import sys
from datetime import date

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app.models import (Affiliate, AffiliateEarning, AffiliatePayout,  # noqa: E402
                        AppSetting, AuditLog, Campaign, Course,
                        EmailCampaign, EmailSettings, Enrollment,
                        LandingPage, Lead, MessageTemplate, PageView, User)
from app import marketing as M  # noqa: E402

app = create_app()
passed, failed, notes = 0, 0, []


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        notes.append(name)
        print(f"  FAIL {name} {detail}")


def login(session, email, password):
    r = session.post(f"{BASE}/login",
                     data={"email": email, "password": password})
    return "Logout" in r.text


# ---------------------------------------------------------------- setup

s_adm = requests.Session()
assert login(s_adm, "admin@sayyed.in", "admin123"), "admin login failed"

with app.app_context():
    course = Course.query.first()
    COURSE_ID = course.id
    tpl = MessageTemplate(name="P11 Test Promo", channel="email",
                          subject="Hi {{name}}", body="Deal: {{campaign}}")
    db.session.add(tpl)
    db.session.commit()
    TPL_ID = tpl.id
    es = EmailSettings.get()
    es.enabled = False
    db.session.commit()

# ---------------------------------------------------------------- 1. landing page CRUD + publish toggle

r = s_adm.post(f"{BASE}/admin/landing-pages/new",
               data={"title": "Free Demo Week", "slug": "free-demo-week",
                     "status": "draft"})
check("landing page create redirects to edit",
      r.status_code == 200 and "Blocks" in r.text)

with app.app_context():
    page = LandingPage.query.filter_by(slug="free-demo-week").first()
    check("landing page created as draft", page and page.status == "draft")
    check("starter blocks seeded", page and len(page.blocks or []) >= 5)
    PAGE_ID = page.id

# draft page must 404 for the public
r = requests.get(f"{BASE}/p/free-demo-week")
check("draft landing page 404s", r.status_code == 404)

# publish it
r = s_adm.post(f"{BASE}/admin/landing-pages/{PAGE_ID}/edit",
               data={"title": "Free Demo Week", "slug": "free-demo-week",
                     "status": "published"})
check("publish toggle saves", r.status_code == 200)

r = requests.get(f"{BASE}/p/free-demo-week")
check("published page renders", r.status_code == 200
      and "Learn Job-Ready IT Skills" in r.text)

# add a block
r = s_adm.post(f"{BASE}/admin/landing-pages/{PAGE_ID}/blocks",
               data={"type": "hero", "heading": "Extra Hero",
                     "text": "hello"})
with app.app_context():
    n = len(LandingPage.query.get(PAGE_ID).blocks)
check("block add works", n >= 6, f"blocks={n}")

# delete the block again
r = s_adm.post(f"{BASE}/admin/landing-pages/{PAGE_ID}/blocks/0/delete")
with app.app_context():
    n2 = len(LandingPage.query.get(PAGE_ID).blocks)
check("block delete works", n2 == n - 1, f"{n} -> {n2}")

# ---------------------------------------------------------------- 2. campaign + metrics math

with app.app_context():
    camp = Campaign(name="P11 Insta Push", channel="instagram",
                    landing_page_id=PAGE_ID, budget=10000, active=True)
    db.session.add(camp)
    db.session.commit()
    CAMP_ID = camp.id

# two page views via the tracking link
s_pub = requests.Session()
r = s_pub.get(f"{BASE}/p/free-demo-week?c={CAMP_ID}")
check("tracked page view 200", r.status_code == 200)
s_pub.get(f"{BASE}/p/free-demo-week?c={CAMP_ID}")
check("campaign cookie set", s_pub.cookies.get("se_camp") == str(CAMP_ID))

# lead capture from the landing form (with campaign cookie + hidden field)
r = s_pub.post(f"{BASE}/p/free-demo-week/lead",
               data={"name": "Camp Lead", "phone": "9111100011",
                     "email": "camplead@example.com",
                     "course_id": str(COURSE_ID),
                     "campaign_id": str(CAMP_ID)})
check("landing lead thanks page", r.status_code == 200
      and "Thanks, Camp Lead" in r.text)

with app.app_context():
    lead = Lead.query.filter_by(phone="9111100011").first()
    check("landing lead captured", lead is not None)
    check("landing lead source=campaign",
          lead and lead.source == Lead.SOURCE_CAMPAIGN, lead.source if lead else "")
    check("landing lead campaign_id set",
          lead and lead.campaign_id == CAMP_ID)
    views = PageView.query.filter_by(campaign_id=CAMP_ID).count()
    check("page views recorded", views == 2, f"views={views}")

# paid enrollment attributed to the campaign
with app.app_context():
    u = User(name="Camp Student", email="campstudent@example.com",
             phone="9111100012", role="student")
    u.set_password("x")
    db.session.add(u)
    db.session.flush()
    enr = Enrollment(user_id=u.id, course_id=COURSE_ID,
                     status=Enrollment.STATUS_ACTIVE, paid=True,
                     amount_paid=40000, campaign_id=CAMP_ID,
                     source=Lead.SOURCE_CAMPAIGN)
    db.session.add(enr)
    db.session.commit()
    ENR_ID = enr.id

with app.app_context():
    stats = Campaign.query.get(CAMP_ID).stats()
check("campaign stats views", stats["views"] == 2, stats)
check("campaign stats leads", stats["leads"] == 1, stats)
check("campaign stats enrollments", stats["enrollments"] == 1, stats)
check("campaign CPL math", stats["cost_per_lead"] == 10000.0, stats)

# campaign dashboard renders + CSV export
r = s_adm.get(f"{BASE}/admin/campaigns/{CAMP_ID}")
check("campaign dashboard renders",
      r.status_code == 200 and "P11 Insta Push" in r.text
      and "10,000.00" in r.text)
r = s_adm.get(f"{BASE}/admin/campaigns/{CAMP_ID}/export.csv")
check("campaign CSV export",
      r.status_code == 200 and "cost_per_lead" in r.text
      and "Camp Lead" in r.text)

# ---------------------------------------------------------------- 3. email campaign SMTP gate

with app.app_context():
    ec = EmailCampaign(name="P11 Blast", template_id=TPL_ID,
                       segment={"audience": "leads"})
    db.session.add(ec)
    db.session.commit()
    EC_ID = ec.id

r = s_adm.post(f"{BASE}/admin/email-campaigns/{EC_ID}/send")
check("email send blocked without SMTP",
      "not configured" in r.text or "SMTP" in r.text)
with app.app_context():
    ec2 = EmailCampaign.query.get(EC_ID)
check("email campaign still draft after gate refusal",
      ec2.status == "draft" and ec2.sent_count == 0)

# recipients resolve from the segment (leads with email)
with app.app_context():
    recips = M.campaign_recipients(EmailCampaign.query.get(EC_ID))
check("email recipients resolve from leads segment",
      any(e == "camplead@example.com" for _n, e in recips), f"{recips}")

# ---------------------------------------------------------------- 4. affiliates: click -> lead -> enrollment -> commission

with app.app_context():
    aff = Affiliate(name="P11 Partner", contact="partner@example.com",
                    code="P11PART", commission_type="flat",
                    commission_value=500, token=secrets.token_urlsafe(16))
    db.session.add(aff)
    db.session.commit()
    AFF_ID = aff.id

s_aff = requests.Session()
r = s_aff.get(f"{BASE}/a/p11part", allow_redirects=False)
check("affiliate link redirects", r.status_code in (301, 302))
check("affiliate cookie set", s_aff.cookies.get("se_aff") == "P11PART")
with app.app_context():
    clicks = Affiliate.query.get(AFF_ID)
check("affiliate click recorded", True)  # click row asserted below
with app.app_context():
    from app.models import AffiliateClick
    nc = AffiliateClick.query.filter_by(affiliate_id=AFF_ID).count()
check("click row in DB", nc == 1, f"clicks={nc}")

# lead via affiliate cookie (chat-style create_lead picks up attribution)
with app.test_request_context("/", headers={"Cookie": "se_aff=P11PART"}):
    from app.crm import create_lead
    al = create_lead(name="Aff Lead", phone="9111100021",
                     email="afflead@example.com", source=Lead.SOURCE_CHAT,
                     course_id=COURSE_ID)
    db.session.commit()
    check("chat lead picks up affiliate from cookie",
          al.source == Lead.SOURCE_AFFILIATE and al.affiliate_id == AFF_ID,
          f"{al.source}/{al.affiliate_id}")
    AFF_LEAD_ID = al.id

# paid enrollment -> attribution -> flat commission earning
with app.test_request_context("/", headers={"Cookie": "se_aff=P11PART"}):
    u2 = User(name="Aff Student", email="affstudent@example.com",
              phone="9111100022", role="student")
    u2.set_password("x")
    db.session.add(u2)
    db.session.flush()
    enr2 = Enrollment(user_id=u2.id, course_id=COURSE_ID,
                      status=Enrollment.STATUS_ACTIVE, paid=True,
                      amount_paid=40000)
    db.session.add(enr2)
    db.session.flush()
    M.attribute_enrollment(enr2)
    db.session.commit()
    check("enrollment attributed to affiliate",
          enr2.affiliate_id == AFF_ID
          and enr2.source == Lead.SOURCE_AFFILIATE,
          f"{enr2.source}/{enr2.affiliate_id}")
    earning = M.record_affiliate_earning(enr2)
    check("flat commission earning created",
          earning and earning.amount == 500, getattr(earning, "amount", None))
    check("earning idempotent (no double)",
          M.record_affiliate_earning(enr2) is None)

# percent commission affiliate
with app.app_context():
    aff2 = Affiliate(name="P11 Percent", contact="p2@example.com",
                     code="P11PCT", commission_type="percent",
                     commission_value=10, token=secrets.token_urlsafe(16))
    db.session.add(aff2)
    db.session.commit()
    AFF2_ID = aff2.id
with app.test_request_context("/", headers={"Cookie": "se_aff=P11PCT"}):
    u3 = User(name="Pct Student", email="pct@example.com",
              phone="9111100023", role="student")
    u3.set_password("x")
    db.session.add(u3)
    db.session.flush()
    enr3 = Enrollment(user_id=u3.id, course_id=COURSE_ID,
                      status=Enrollment.STATUS_ACTIVE, paid=True,
                      amount_paid=40000)
    db.session.add(enr3)
    db.session.flush()
    M.attribute_enrollment(enr3)
    db.session.commit()
    e3 = M.record_affiliate_earning(enr3)
    check("percent commission = 10% of 40000",
          e3 and e3.amount == 4000.0, getattr(e3, "amount", None))

# affiliate dashboard token page + admin payout flow
with app.app_context():
    tok = Affiliate.query.get(AFF_ID).token
r = requests.get(f"{BASE}/aff/{tok}")
check("affiliate token dashboard renders",
      r.status_code == 200 and "P11 Partner" in r.text)

with app.app_context():
    stats = Affiliate.query.get(AFF_ID).stats()
check("affiliate stats earned", stats["earned"] == 500.0, stats)
check("affiliate stats pending", stats["pending"] == 500.0, stats)

r = s_adm.post(f"{BASE}/admin/affiliates/{AFF_ID}/payout",
               data={"note": "test payout"})
check("payout created", r.status_code == 200)
with app.app_context():
    po = AffiliatePayout.query.filter_by(affiliate_id=AFF_ID).first()
    check("payout row pending", po and po.status == "pending"
          and po.amount == 500.0, getattr(po, "amount", None))
    PO_ID = po.id

r = s_adm.post(f"{BASE}/admin/affiliates/payouts/{PO_ID}/mark-paid")
with app.app_context():
    po2 = AffiliatePayout.query.get(PO_ID)
    check("payout marked paid", po2.status == "paid" and po2.paid_at)
    e_paid = AffiliateEarning.query.filter_by(
        affiliate_id=AFF_ID).first()
    check("earning flipped to paid", e_paid.status == "paid")
    log = AuditLog.query.filter_by(action="affiliate.payout.paid").first()
    check("payout paid writes audit log", log is not None)

# ---------------------------------------------------------------- 5. analytics IDs: public only

with app.app_context():
    AppSetting.set("analytics.ga4_id", "G-TEST123")
    AppSetting.set("analytics.meta_pixel_id", "999888777")
r = requests.get(f"{BASE}/")
check("GA4 on public homepage",
      "G-TEST123" in r.text and "googletagmanager" in r.text)
check("Meta Pixel on public homepage", "999888777" in r.text)
r = s_adm.get(f"{BASE}/admin/dashboard")
check("no analytics on admin pages",
      "G-TEST123" not in r.text and "999888777" not in r.text)
r = requests.get(f"{BASE}/p/free-demo-week")
check("analytics on public landing page", "G-TEST123" in r.text)
with app.app_context():
    AppSetting.set("analytics.ga4_id", "")
    AppSetting.set("analytics.meta_pixel_id", "")

# ---------------------------------------------------------------- 6. lead.source -> enrollment attribution fallback

with app.app_context():
    u4 = User(name="Conv Student", email="conv@example.com",
              phone="9111100031", role="student")
    u4.set_password("x")
    db.session.add(u4)
    db.session.flush()
    l4 = Lead(name="Conv Lead", phone="9111100031", source=Lead.SOURCE_CHAT,
              course_id=COURSE_ID, campaign_id=CAMP_ID,
              converted_user_id=u4.id)
    db.session.add(l4)
    db.session.flush()
    enr4 = Enrollment(user_id=u4.id, course_id=COURSE_ID,
                      status=Enrollment.STATUS_ACTIVE, paid=True,
                      amount_paid=35000)
    db.session.add(enr4)
    db.session.flush()
    with app.test_request_context("/"):
        M.attribute_enrollment(enr4)
    db.session.commit()
    check("attribution falls back to converted lead",
          enr4.source == Lead.SOURCE_CHAT and enr4.campaign_id == CAMP_ID,
          f"{enr4.source}/{enr4.campaign_id}")

# ---------------------------------------------------------------- 7. permission matrix + migration head

with app.app_context():
    from app.models import RolePermission
    mp = RolePermission.query.filter_by(role="admin",
                                        module="marketing").first()
    check("marketing permission module seeded for admin",
          mp and mp.can_view and mp.can_delete)
    fac = RolePermission.query.filter_by(role="faculty",
                                         module="marketing").first()
    check("faculty denied marketing by default",
          fac and not fac.can_view)

with app.app_context():
    head = db.session.execute(
        db.text("SELECT version_num FROM alembic_version")).fetchone()[0]
    check("migration head is recorded-sessions revision", head == "f29d3e4a5b6c", head)

print(f"\n==== Phase 11: {passed} passed, {failed} failed ====")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
