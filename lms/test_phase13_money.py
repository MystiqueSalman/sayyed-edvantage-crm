"""Phase 13 Stream 5 — Money + International (end-to-end).

Runs IN-PROCESS via Flask's test_client against a FRESH SQLite DB
(migrated via `flask db upgrade` + seeded by run_suite.sh, same SQLITE_PATH).
In-process testing lets us mock the Stripe SDK (unittest.mock.patch) — the
live Stripe API is never touched.

Phase-13 tables are created via db.create_all() (additive only — the
coordinator's combined Alembic revision will cover them in prod).

Coverage: Stripe session creation (mocked), webhook signature verification
(good + bad), payment recorded + enrollment activated via mocked webhook,
Stripe hidden when unconfigured; installment plan CRUD, schedule generation
on enrollment, overdue flagging, manual mark-paid; currency conversion math,
INR fallback, secondary display on catalog/detail pages; timezone conversion
correctness for 2 zones, invalid zone rejected.

Every app-context block re-fetches its rows (never reuse ORM instances
across blocks — the session closes between them).
"""
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app.models import AppSetting, Course, Enrollment, User  # noqa: E402
from app.models13_money import (FxRate13, InstallmentPlan13,  # noqa: E402
                                LocalePrefs13, StudentInstallment13)

app = create_app()
with app.app_context():
    db.create_all()  # Phase-13 tables only (existing tables untouched)

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


def login(client, email, password):
    r = client.post("/login", data={"email": email, "password": password},
                    follow_redirects=True)
    return r.status_code == 200 and b"logout" in r.data.lower()


def text(resp):
    return resp.get_data(as_text=True)


c_adm, c_stu, c_anon = (app.test_client() for _ in range(3))
assert login(c_adm, "admin@sayyed.in", "admin123"), "admin login failed"
assert login(c_stu, "student@sayyed.in", "student123"), "student login failed"

with app.app_context():
    course = Course.query.order_by(Course.id).first()
    student = User.query.filter_by(email="student@sayyed.in").first()
    CID, STU_ID = course.id, student.id
    # clean slate for this suite
    Enrollment.query.filter_by(user_id=STU_ID).delete()
    StudentInstallment13.query.filter_by(user_id=STU_ID).delete()
    InstallmentPlan13.query.delete()
    LocalePrefs13.query.filter_by(user_id=STU_ID).delete()
    db.session.commit()

FAKE_KEYS = {"STRIPE_PUBLISHABLE_KEY": "pk_test_fake",
             "STRIPE_SECRET_KEY": "sk_test_fake",
             "STRIPE_WEBHOOK_SECRET": "whsec_fake"}


def set_stripe_keys(on=True):
    with app.app_context():
        for k, v in FAKE_KEYS.items():
            AppSetting.set(k, v if on else "")
        AppSetting.set("STRIPE_TEST_MODE", "1")


class FakeSession:
    url = "https://checkout.stripe.com/pay/cs_test_fake"


FAKE_ENR_ID = [None]  # filled in after the enrollment is created


def fake_construct_event_ok(payload, sig, secret):
    return {"type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_123",
                "payment_intent": "pi_test_123",
                "amount_total": 50000 * 100,
                "metadata": {"enrollment_id": str(FAKE_ENR_ID[0]),
                             "user_id": str(STU_ID),
                             "test_mode": "1"}}}}


# ---------------------------------------------------------------- 1. Stripe

set_stripe_keys(True)

with app.app_context():
    enr = Enrollment(user_id=STU_ID, course_id=CID,
                     status=Enrollment.STATUS_PENDING, paid=False,
                     amount_paid=50000, coupon_code="")
    db.session.add(enr)
    db.session.commit()
    ENR_ID = enr.id
FAKE_ENR_ID[0] = ENR_ID  # read by the fake webhook payload builder

# 1a. checkout page renders with test-mode banner
r = c_stu.get(f"/pay/stripe/enrollment/{ENR_ID}")
check("stripe checkout page renders",
      r.status_code == 200 and "TEST MODE" in text(r), r.status_code)

# 1b. session creation mocked -> 303 redirect to Stripe
with patch("stripe.checkout.Session.create",
           return_value=FakeSession()) as mk:
    r = c_stu.post(f"/pay/stripe/enrollment/{ENR_ID}",
                    data={"plan_choice": "full"})
    check("stripe session created + redirect",
          r.status_code == 303 and "checkout.stripe.com" in r.headers.get(
              "Location", ""), r.status_code)
    kwargs = mk.call_args.kwargs
    check("stripe session charges INR in paise",
          kwargs["line_items"][0]["price_data"]["currency"] == "inr"
          and kwargs["line_items"][0]["price_data"]["unit_amount"]
          == 50000 * 100, str(kwargs.get("line_items")))

# 1c. webhook with good signature -> payment recorded + enrollment active
with patch("stripe.Webhook.construct_event",
           side_effect=fake_construct_event_ok):
    r = c_anon.post("/webhooks/stripe", data=b"{}",
                    headers={"Stripe-Signature": "t=1,v1=abc"})
    check("webhook good signature accepted", r.status_code == 200,
          r.status_code)
with app.app_context():
    e = Enrollment.query.get(ENR_ID)
    check("webhook recorded payment + activated enrollment",
          e.paid and e.status == Enrollment.STATUS_ACTIVE
          and e.amount_paid == 50000
          and (e.razorpay_payment_id or "").startswith("stripe_"),
          f"paid={e.paid} status={e.status} amt={e.amount_paid}")

# 1d. webhook with bad signature -> 400, nothing changes
with patch("stripe.Webhook.construct_event",
           side_effect=Exception("bad sig")):
    r = c_anon.post("/webhooks/stripe", data=b"{}",
                    headers={"Stripe-Signature": "bogus"})
    check("webhook bad signature rejected", r.status_code == 400,
          r.status_code)

# 1e. idempotent re-delivery
with patch("stripe.Webhook.construct_event",
           side_effect=fake_construct_event_ok):
    r = c_anon.post("/webhooks/stripe", data=b"{}",
                    headers={"Stripe-Signature": "t=1,v1=abc"})
    check("webhook re-delivery idempotent", r.status_code == 200,
          r.status_code)
with app.app_context():
    e = Enrollment.query.get(ENR_ID)
    check("no double-charge on re-delivery", e.amount_paid == 50000,
          e.amount_paid)

# 1f. hidden when unconfigured (fresh pending enrollment)
set_stripe_keys(False)
with app.app_context():
    Enrollment.query.filter_by(user_id=STU_ID).delete()
    enr3 = Enrollment(user_id=STU_ID, course_id=CID,
                      status=Enrollment.STATUS_PENDING, paid=False,
                      amount_paid=40000, coupon_code="")
    db.session.add(enr3)
    db.session.commit()
    ENR3_ID = enr3.id
r = c_stu.get(f"/pay/stripe/enrollment/{ENR3_ID}")
check("stripe pay hidden when unconfigured",
      r.status_code in (301, 302)
      and "/checkout/" in r.headers.get("Location", ""), r.status_code)
r = c_adm.get("/admin/payments/stripe")
check("admin sees 'Stripe not configured' notice",
      r.status_code == 200 and "Stripe not configured" in text(r),
      r.status_code)
r = c_anon.post("/webhooks/stripe", data=b"{}")
check("webhook 400 when unconfigured", r.status_code == 400, r.status_code)
set_stripe_keys(True)

# 1g. role gate on settings
r = c_stu.get("/admin/payments/stripe")
check("student blocked from stripe settings", r.status_code == 403,
      r.status_code)

# ---------------------------------------------------------------- 2. installments

# 2a. admin creates a plan
r = c_adm.post("/admin/installment-plans/new", data={
    "course_id": CID, "name": "3-part test plan", "num_installments": "3",
    "amounts": "20000, 15000, 15000", "due_days": "0, 30, 60",
    "active": "1"})
check("admin creates installment plan", r.status_code in (301, 302),
      r.status_code)
with app.app_context():
    plan = InstallmentPlan13.query.filter_by(
        name="3-part test plan").first()
    check("plan stored with amounts/due_days",
          plan is not None and plan.amounts == [20000, 15000, 15000]
          and plan.due_days == [0, 30, 60] and plan.total_amount == 50000,
          getattr(plan, "amounts", None))
    PLAN_ID = plan.id

# 2b. plan validation: mismatched counts rejected
r = c_adm.post("/admin/installment-plans/new", data={
    "course_id": CID, "name": "bad plan", "num_installments": "3",
    "amounts": "20000, 30000", "due_days": "0, 30, 60",
    "active": "1"})
with app.app_context():
    bad = InstallmentPlan13.query.filter_by(name="bad plan").first()
    check("mismatched amounts rejected", bad is None)

# 2c. enroll with plan -> schedule generated
with app.app_context():
    Enrollment.query.filter_by(user_id=STU_ID).delete()
    db.session.commit()
r = c_stu.post(f"/billing/enroll-with-plan/{PLAN_ID}")
check("enroll-with-plan redirects to stripe checkout",
      r.status_code in (301, 302) and "/pay/stripe/enrollment/" in r.headers.get(
          "Location", ""), r.status_code)
with app.app_context():
    rows = (StudentInstallment13.query
            .filter_by(user_id=STU_ID, plan_id=PLAN_ID)
            .order_by(StudentInstallment13.installment_no).all())
    check("schedule generated (3 rows)",
          len(rows) == 3 and [x.amount_inr for x in rows]
          == [20000, 15000, 15000], len(rows))
    today = datetime.utcnow().date()
    check("due dates = today + due_days",
          rows[0].due_date == today and rows[1].due_date == today
          + timedelta(days=30) and rows[2].due_date == today
          + timedelta(days=60),
          [str(x.due_date) for x in rows])
    enr2 = Enrollment.query.filter_by(
        user_id=STU_ID, course_id=CID).first()
    ENR2_ID = enr2.id
    check("plan enrollment starts pending/unpaid",
          not enr2.paid and enr2.status == Enrollment.STATUS_PENDING
          and enr2.amount_paid == 0)

# 2d. billing page shows schedule
r = c_stu.get("/billing/installments")
check("billing page lists installments",
      r.status_code == 200 and "3-part test plan" in text(r)
      and "Pay ₹20,000" in text(r), r.status_code)

# 2e. overdue flagging
with app.app_context():
    from app.money13 import refresh_overdue
    r1 = StudentInstallment13.query.filter_by(
        user_id=STU_ID, plan_id=PLAN_ID, installment_no=2).first()
    r1.due_date = datetime.utcnow().date() - timedelta(days=1)
    db.session.commit()
    n = refresh_overdue()
    db.session.refresh(r1)
    check("refresh_overdue flags past-due as overdue",
          n >= 1 and r1.status == StudentInstallment13.STATUS_OVERDUE,
          f"n={n} status={r1.status}")

# 2f. finance dashboard widget
r = c_adm.get("/admin/finance")
check("finance dashboard shows overdue widget",
      r.status_code == 200 and "Overdue installments" in text(r)
      and "student@sayyed.in" in text(r), r.status_code)

# 2g. admin manual mark-paid
with app.app_context():
    r1 = StudentInstallment13.query.filter_by(
        user_id=STU_ID, plan_id=PLAN_ID, installment_no=2).first()
    INST2_ID = r1.id
r = c_adm.post(f"/admin/installments/{INST2_ID}/mark-paid",
               data={"payment_ref": "UPI-REF-1"})
check("admin mark-paid redirects", r.status_code in (301, 302),
      r.status_code)
with app.app_context():
    r1 = StudentInstallment13.query.get(INST2_ID)
    check("installment marked paid with ref",
          r1.status == StudentInstallment13.STATUS_PAID
          and r1.paid_at is not None
          and r1.payment_ref == "manual:UPI-REF-1",
          f"{r1.status} {r1.payment_ref}")

# 2h. first-installment Stripe payment activates enrollment via webhook
def fake_event_installment(payload, sig, secret):
    return {"type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_456", "payment_intent": "pi_test_456",
                "amount_total": 20000 * 100,
                "metadata": {"enrollment_id": str(ENR2_ID),
                             "installment_id": str(INST1_ID),
                             "user_id": str(STU_ID)}}}}


with app.app_context():
    i1 = StudentInstallment13.query.filter_by(
        user_id=STU_ID, plan_id=PLAN_ID, installment_no=1).first()
    INST1_ID = i1.id
with patch("stripe.Webhook.construct_event",
           side_effect=fake_event_installment):
    r = c_anon.post("/webhooks/stripe", data=b"{}",
                    headers={"Stripe-Signature": "t=1,v1=ok"})
    check("installment webhook accepted", r.status_code == 200,
          r.status_code)
with app.app_context():
    i1 = StudentInstallment13.query.get(INST1_ID)
    e2 = Enrollment.query.get(ENR2_ID)
    # amount_paid = 15000 (manual mark-paid of #2 in 2g) + 20000 (webhook #1)
    check("first installment activates enrollment",
          i1.status == StudentInstallment13.STATUS_PAID
          and e2.paid and e2.status == Enrollment.STATUS_ACTIVE
          and e2.amount_paid == 35000,
          f"inst={i1.status} paid={e2.paid} amt={e2.amount_paid}")

# 2i. student blocked from plan admin
r = c_stu.get("/admin/installment-plans")
check("student blocked from plan admin", r.status_code == 403,
      r.status_code)

# ---------------------------------------------------------------- 3. currency

with app.app_context():
    from app.money13 import display_price, seed_fx_rates
    seed_fx_rates()
    AppSetting.set("CURRENCY_DISPLAY", "USD")
    dp = display_price(50000)
    check("USD conversion math (50000/83.5≈599)",
          dp["primary"] == "₹50,000" and dp["secondary"] == "≈ $599",
          str(dp))
    AppSetting.set("CURRENCY_DISPLAY", "EUR")
    dp = display_price(90000)
    check("EUR conversion uses € symbol",
          dp["secondary"].startswith("≈ €"), str(dp))
    AppSetting.set("CURRENCY_DISPLAY", "AED")
    dp = display_price(22700)
    check("AED conversion format",
          dp["secondary"] == "≈ AED 1,000", str(dp))
    AppSetting.set("CURRENCY_DISPLAY", "INR")
    dp = display_price(50000)
    check("INR fallback: no secondary",
          dp == {"primary": "₹50,000", "secondary": ""}, str(dp))
    AppSetting.set("CURRENCY_DISPLAY", "XYZ")
    dp = display_price(50000)
    check("unknown currency falls back to INR",
          dp == {"primary": "₹50,000", "secondary": ""}, str(dp))
    AppSetting.set("CURRENCY_DISPLAY", "INR")

# 3b. secondary display on catalog + detail pages
with app.app_context():
    AppSetting.set("CURRENCY_DISPLAY", "USD")
r = c_anon.get("/courses")
check("catalog shows converted secondary price",
      r.status_code == 200 and "est." in text(r) and "≈ $" in text(r),
      r.status_code)
with app.app_context():
    slug = Course.query.get(CID).slug
r = c_anon.get(f"/course/{slug}")
check("course detail shows converted secondary price",
      r.status_code == 200 and "≈ $" in text(r), r.status_code)
with app.app_context():
    AppSetting.set("CURRENCY_DISPLAY", "INR")
r = c_anon.get("/courses")
check("catalog hides secondary when INR",
      r.status_code == 200 and "≈ $" not in text(r), r.status_code)

# 3c. student blocked from fx admin
r = c_stu.get("/admin/fx-rates")
check("student blocked from fx admin", r.status_code == 403, r.status_code)

# ---------------------------------------------------------------- 4. timezone

with app.app_context():
    from app.money13 import to_user_tz, user_timezone, valid_timezone
    # naive 13:30 IST wall time
    naive = datetime(2026, 9, 28, 13, 30)
    ny = to_user_tz(naive, "America/New_York")
    check("IST -> New York conversion",
          ny.strftime("%H:%M") == "04:00" and ny.strftime("%Z") == "EDT",
          ny.strftime("%H:%M %Z"))
    dxb = to_user_tz(naive, "Asia/Dubai")
    check("IST -> Dubai conversion",
          dxb.strftime("%H:%M") == "12:00"
          and dxb.utcoffset() == timedelta(hours=4),
          dxb.strftime("%H:%M %Z"))
    kol = to_user_tz(naive, "Asia/Kolkata")
    check("default zone unchanged",
          kol.strftime("%H:%M %Z") == "13:30 IST", kol.strftime("%H:%M %Z"))
    check("invalid zone rejected", not valid_timezone("Mars/Olympus")
          and not valid_timezone("") and not valid_timezone(None)
          and valid_timezone("UTC"))
    check("none passthrough", to_user_tz(None, "UTC") is None)
    check("anonymous defaults to Kolkata",
          user_timezone(None) == "Asia/Kolkata")

# 4b. timezone settings page: save + reject invalid
r = c_stu.post("/settings/timezone",
               data={"timezone": "America/New_York"})
check("timezone saved", r.status_code in (301, 302), r.status_code)
with app.app_context():
    prefs = LocalePrefs13.query.filter_by(user_id=STU_ID).first()
    check("prefs row stored", prefs is not None
          and prefs.timezone == "America/New_York",
          getattr(prefs, "timezone", None))
r = c_stu.post("/settings/timezone",
               data={"timezone": "Mars/Olympus"})
with app.app_context():
    prefs = LocalePrefs13.query.filter_by(user_id=STU_ID).first()
    check("invalid timezone rejected (unchanged)",
          r.status_code == 200 and "not a valid timezone" in text(r)
          and prefs.timezone == "America/New_York",
          r.status_code)

# 4c. dashboard renders live-class time in the viewer's zone
with app.app_context():
    from app.models import LiveSession
    start = (datetime.utcnow() + timedelta(hours=1)).replace(
        second=0, microsecond=0)
    ls = LiveSession(course_id=CID, title="TZ test class",
                     starts_at=start,
                     duration_min=60, room_name="se-tz-test-13")
    db.session.add(ls)
    db.session.commit()
    LS_ID = ls.id
exp_ny = (start - timedelta(hours=9, minutes=30)).strftime("%I:%M %p EDT")
exp_ist = start.strftime("%I:%M %p IST")
r = c_stu.get("/dashboard")
check("dashboard shows viewer timezone (EDT)",
      r.status_code == 200 and exp_ny in text(r),
      f"expected {exp_ny}")
# admin has no enrollments so the student dashboard widget is empty for them;
# verify IST rendering on the (edited) course-detail live-class list instead
with app.app_context():
    slug = Course.query.get(CID).slug
r = c_adm.get(f"/course/{slug}")
check("course page (Kolkata admin) still shows IST",
      r.status_code == 200 and exp_ist in text(r),
      f"expected {exp_ist}")
with app.app_context():
    db.session.delete(LiveSession.query.get(LS_ID))
    db.session.commit()

print(f"\n==== Phase 13 Stream 5: {passed} passed, {failed} failed ====")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
