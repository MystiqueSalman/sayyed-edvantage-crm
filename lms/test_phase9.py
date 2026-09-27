"""Phase 9 — Faculty & operations (end-to-end).

Runs against a dev server on http://localhost:5000 with a FRESH DB
(migrated via `flask db upgrade` + seeded), same SQLITE_PATH for server and
this script. Mixes HTTP flows with in-process checks.

Every app-context block re-fetches its rows (never reuse ORM instances
across blocks — the session closes between them).

Coverage: auto-attendance on join + late flag + manual override,
attendance % math, calendar aggregation, batch capacity enforcement,
audit-log writes, permission matrix allow/deny (incl. new modules),
invoice GST math + PDF, finance totals reconcile, refund flow.
"""
import os
import sys
from datetime import date, datetime, timedelta

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app import operations as OPS  # noqa: E402
from app.models import (Announcement, Assignment, AuditLog, Batch,
                        BatchMember, Challenge, Coupon, Course, Enrollment,
                        Invoice, LiveSession, Project, Refund, RolePermission,
                        SessionAttendance, User)  # noqa: E402

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


def ctx():
    return app.app_context()


s_stu = requests.Session()
s_adm = requests.Session()
s_fac = requests.Session()
s_emp = requests.Session()

print("== Phase 9: Faculty & Operations ==")

with ctx():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    adm = User.query.filter_by(email="admin@sayyed.in").first()
    fac = User.query.filter_by(email="faculty@sayyed.in").first()
    mgr = User.query.filter_by(email="manager@sayyed.in").first()
    check("seed users present", stu and adm and fac and mgr)
    STU_ID, ADM_ID, FAC_ID, MGR_ID = stu.id, adm.id, fac.id, mgr.id

    course = Course.query.first()
    course.instructor_id = fac.id
    db.session.commit()
    COURSE_ID = course.id
    check("seed course present", course is not None)

    enr = Enrollment.query.filter_by(
        user_id=STU_ID, course_id=COURSE_ID).first()
    if not enr:
        db.session.add(Enrollment(user_id=STU_ID, course_id=COURSE_ID,
                                  status="active"))
        db.session.commit()

    emp = User.query.filter_by(email="emp9@test.in").first()
    if not emp:
        emp = User(name="Emp Nine", email="emp9@test.in", role="employer",
                   company="TestCo", is_active=True)
        emp.set_password("emp123")
        db.session.add(emp)
        db.session.commit()
    EMP_ID = emp.id

    stu2 = User.query.filter_by(email="student2@sayyed.in").first()
    if not stu2:
        stu2 = User(name="Student Two", email="student2@sayyed.in",
                    role="student")
        stu2.set_password("student123")
        db.session.add(stu2)
        db.session.commit()

check("admin login", login(s_adm, "admin@sayyed.in", "admin123"))
check("student login", login(s_stu, "student@sayyed.in", "student123"))
check("faculty login", login(s_fac, "faculty@sayyed.in", "faculty123"))
check("employer login", login(s_emp, "emp9@test.in", "emp123"))

# ---------------------------------------------------------------- 1. attendance
with ctx():
    att_course = Course(title="P9 Attendance Course", slug="p9-attendance",
                        fee=1000, instructor_id=FAC_ID)
    db.session.add(att_course)
    db.session.commit()
    ATT_COURSE = att_course.id
    db.session.add(Enrollment(user_id=STU_ID, course_id=ATT_COURSE,
                              status="active"))
    s1 = LiveSession(course_id=ATT_COURSE, title="P9 Live One",
                     starts_at=datetime.utcnow() - timedelta(minutes=5),
                     duration_min=60, room_name="p9room1")
    s2 = LiveSession(course_id=ATT_COURSE, title="P9 Live Two",
                     starts_at=datetime.utcnow() - timedelta(minutes=20),
                     duration_min=60, room_name="p9room2")
    db.session.add_all([s1, s2])
    db.session.commit()
    S1, S2 = s1.id, s2.id

r = s_stu.get(f"{BASE}/live/join/{S1}", allow_redirects=False)
check("join redirects to jitsi",
      r.status_code == 302 and "meet.jit.si" in r.headers.get("Location", ""),
      f"got {r.status_code}")
with ctx():
    rec = SessionAttendance.query.filter_by(session_id=S1,
                                            user_id=STU_ID).first()
    check("auto-attendance present",
          rec and rec.status == "present" and rec.auto is True,
          f"{rec.status if rec else None}/{rec.auto if rec else None}")
    check("join time recorded", rec and rec.joined_at is not None)

r = s_stu.get(f"{BASE}/live/join/{S2}", allow_redirects=False)
check("late join redirects", r.status_code == 302)
with ctx():
    rec2 = SessionAttendance.query.filter_by(session_id=S2,
                                             user_id=STU_ID).first()
    check("late flag set", rec2 and rec2.status == "late",
          rec2.status if rec2 else None)

r = s_fac.post(f"{BASE}/manage/live/{S1}/attendance",
               data={f"status_{STU_ID}": "absent", f"dur_{STU_ID}": "30"})
check("faculty attendance posts", r.status_code in (200, 302), r.status_code)
with ctx():
    fac = db.session.get(User, FAC_ID)
    rec = SessionAttendance.query.filter_by(session_id=S1,
                                            user_id=STU_ID).first()
    check("manual override wins",
          rec and rec.status == "absent" and rec.auto is False,
          f"{rec.status if rec else None}")
    check("marked_by recorded", rec and rec.marked_by == fac.id)
    check("duration recorded", rec and rec.duration_min == 30)
    pct = SessionAttendance.percent(STU_ID, ATT_COURSE)
    check("attendance % math", pct == 50.0, pct)  # S1 absent, S2 late

r = s_fac.get(f"{BASE}/manage/course/{ATT_COURSE}/attendance")
check("attendance report 200",
      r.status_code == 200 and "Attendance" in r.text, r.status_code)
r = s_fac.get(f"{BASE}/manage/course/{ATT_COURSE}/attendance?format=csv")
check("attendance CSV",
      r.status_code == 200 and "text/csv" in r.headers.get("Content-Type", ""),
      r.status_code)
r = s_stu.get(f"{BASE}/manage/course/{COURSE_ID}/attendance")
check("student denied attendance report", r.status_code == 403, r.status_code)

# ---------------------------------------------------------------- 2. calendar
with ctx():
    from app.models import Module as _Module, Quiz as _Quiz
    mod = _Module.query.filter_by(course_id=COURSE_ID).first()
    db.session.add(Assignment(course_id=COURSE_ID, title="P9 HW",
                              due_date=date.today() + timedelta(days=3)))
    db.session.add(Project(course_id=COURSE_ID, title="P9 Capstone",
                           deadline=date.today() + timedelta(days=10),
                           is_active=True))
    db.session.add(_Quiz(module_id=mod.id, title="P9 Final Exam",
                         deadline=date.today() + timedelta(days=5)))
    db.session.add(Challenge(title="P9 Sprint", criterion="lessons",
                             target_json='{"count": 3}', is_active=True,
                             starts_at=datetime.utcnow(),
                             ends_at=datetime.utcnow() + timedelta(days=7)))
    db.session.commit()

r = s_stu.get(f"{BASE}/calendar")
check("calendar page 200", r.status_code == 200, r.status_code)
r = s_stu.get(f"{BASE}/calendar/events")
evs = r.json()
kinds = {e["kind"] for e in evs}
check("calendar aggregates sources",
      {"live", "assignment", "exam", "project", "challenge"} <= kinds, kinds)
check("exam deadline on calendar",
      any(e["kind"] == "exam" and "P9 Final Exam" in e["title"] for e in evs))
check("calendar events have urls", all("url" in e for e in evs))

# faculty sets quiz deadline via the quiz form (Phase 6 regression)
with ctx():
    qz = _Quiz.query.filter_by(title="P9 Final Exam").first()
    QZ = qz.id
r = s_fac.post(f"{BASE}/manage/quiz/{QZ}/edit",
               data={"title": "P9 Final Exam", "pass_percent": "60",
                     "time_limit_min": "90",
                     "deadline": (date.today() + timedelta(days=6)).isoformat()})
with ctx():
    qz = db.session.get(_Quiz, QZ)
    check("quiz deadline editable via form",
          qz.deadline == date.today() + timedelta(days=6), qz.deadline)

# ---------------------------------------------------------------- 3. batches
r = s_adm.post(f"{BASE}/manage/batches",
               data={"name": "P9 Batch", "course_id": COURSE_ID,
                     "capacity": "1", "schedule_text": "Mon-Wed",
                     "start_date": date.today().isoformat()})
check("batch created", r.status_code in (200, 302), r.status_code)
with ctx():
    b = Batch.query.filter_by(name="P9 Batch").first()
    BID = b.id if b else None
    check("batch persisted", b is not None and b.capacity == 1)

r = s_adm.get(f"{BASE}/manage/batches/{BID}")
check("batch detail 200 + roster",
      r.status_code == 200 and "Add student" in r.text, r.status_code)

r = s_adm.post(f"{BASE}/manage/batches/{BID}",
               data={"email": "student@sayyed.in"})
with ctx():
    check("first enroll ok",
          BatchMember.query.filter_by(batch_id=BID).count() == 1)
r = s_adm.post(f"{BASE}/manage/batches/{BID}",
               data={"email": "student2@sayyed.in"})
with ctx():
    check("capacity enforced",
          BatchMember.query.filter_by(batch_id=BID).count() == 1)

with ctx():
    acts = {a.action for a in AuditLog.query.filter(
        AuditLog.action.like("batch.%")).all()}
    check("batch audit written",
          "batch.create" in acts and "batch.enroll" in acts, acts)

with ctx():
    m = BatchMember.query.filter_by(batch_id=BID).first()
    UID = m.user_id
r = s_adm.post(f"{BASE}/manage/batches/{BID}/remove/{UID}")
with ctx():
    check("batch remove works",
          BatchMember.query.filter_by(batch_id=BID).count() == 0)

# ---------------------------------------------------------------- 4. audit logs
r = s_adm.post(f"{BASE}/admin/coupons",
               data={"code": "P9TEST", "percent_off": "10", "active": "1"})
with ctx():
    c9 = Coupon.query.filter_by(code="P9TEST").first()
    log = AuditLog.query.filter_by(action="coupon.create").order_by(
        AuditLog.id.desc()).first()
    check("coupon audit written",
          c9 is not None and log and log.actor_email == "admin@sayyed.in",
          log.action if log else None)

with ctx():
    emp = db.session.get(User, EMP_ID)
    emp.is_active = False
    db.session.commit()
r = s_adm.post(f"{BASE}/admin/employers/{EMP_ID}/approve")
with ctx():
    log = AuditLog.query.filter_by(action="employer.approve").order_by(
        AuditLog.id.desc()).first()
    check("employer approve audit", log is not None,
          log.action if log else None)

r = s_adm.get(f"{BASE}/admin/audit-logs")
check("audit log page 200",
      r.status_code == 200 and "coupon.create" in r.text, r.status_code)
r = s_adm.get(f"{BASE}/admin/audit-logs?action=coupon")
check("audit log filter",
      r.status_code == 200 and "employer.approve" not in r.text, r.status_code)

# toggle audits
with ctx():
    ann = Announcement.query.filter_by(active=True,
                                       batch_id=None).first()
    AID = ann.id if ann else None
    tgt = User.query.filter_by(email="student2@sayyed.in").first()
    TUID = tgt.id
if AID:
    r = s_adm.post(f"{BASE}/admin/announcements/{AID}/toggle")
    with ctx():
        check("announcement toggle audit",
              AuditLog.query.filter_by(
                  action="announcement.toggle").count() >= 1)
r = s_adm.post(f"{BASE}/admin/users/{TUID}/toggle")
with ctx():
    check("user toggle audit",
          AuditLog.query.filter_by(action="user.toggle").count() >= 1)

# ---------------------------------------------------------------- 5. permissions
r = s_emp.get(f"{BASE}/admin/finance")
check("employer denied finance", r.status_code == 403, r.status_code)
r = s_adm.get(f"{BASE}/admin/finance")
check("admin allowed finance", r.status_code == 200, r.status_code)
r = s_stu.get(f"{BASE}/manage/batches")
check("student denied batches", r.status_code == 403, r.status_code)
r = s_fac.get(f"{BASE}/manage/batches")
check("faculty allowed batches (default)", r.status_code == 200, r.status_code)
r = s_fac.get(f"{BASE}/admin/finance")
check("faculty denied finance (default)", r.status_code == 403, r.status_code)

with ctx():
    mgr = db.session.get(User, MGR_ID)
    fac = db.session.get(User, FAC_ID)
    check("matrix seeded",
          RolePermission.query.filter_by(role="manager",
                                         module="users").first() is not None)
    check("manager denied users module",
          OPS.has_permission(mgr, "users", "view") is False)
    check("manager keeps courses edit",
          OPS.has_permission(mgr, "courses", "edit") is True)
    check("faculty calendar view default",
          OPS.has_permission(fac, "calendar", "view") is True)

r = s_adm.post(f"{BASE}/admin/permissions", data={"p|faculty|batches|view": "on"})
check("matrix saved", r.status_code in (200, 302), r.status_code)
with ctx():
    db.session.expire_all()
    fac = db.session.get(User, FAC_ID)
    check("matrix edit took effect",
          OPS.has_permission(fac, "batches", "edit") is False)
r = s_fac.post(f"{BASE}/manage/batches",
               data={"name": "ShouldFail", "course_id": COURSE_ID})
check("revoked permission enforced", r.status_code == 403, r.status_code)
with ctx():
    row = RolePermission.query.filter_by(role="faculty",
                                         module="batches").first()
    row.can_create = row.can_edit = row.can_delete = True
    db.session.commit()

# ---------------------------------------------------------------- 6. invoices & finance
with ctx():
    enr = Enrollment.query.filter_by(user_id=STU_ID,
                                     course_id=COURSE_ID).first()
    enr.paid = True
    enr.amount_paid = 53100
    enr.coupon_code = "P9TEST"
    enr.razorpay_payment_id = "pay_p9test1"
    enr.status = "active"
    db.session.commit()
    ENR, FEE = enr.id, enr.course.fee

r = s_adm.post(f"{BASE}/admin/invoices/issue/{ENR}", allow_redirects=False)
check("invoice issued", r.status_code == 302, r.status_code)
with ctx():
    inv = Invoice.query.filter_by(enrollment_id=ENR).first()
    exp_disc = round(FEE * 10 / 100)
    exp_tax = FEE - exp_disc
    exp_gst = round(exp_tax * 18 / 100)
    check("invoice GST math",
          inv and inv.base_fee == FEE and inv.discount == exp_disc
          and inv.taxable == exp_tax and inv.gst_amount == exp_gst
          and inv.total == exp_tax + exp_gst,
          f"{inv.base_fee}/{inv.discount}/{inv.taxable}/{inv.gst_amount}/{inv.total}"
          if inv else None)
    check("invoice number sequential",
          inv and inv.number.startswith("SE-"), inv.number if inv else None)
    IID, INUM = inv.id, inv.number

r = s_adm.post(f"{BASE}/admin/invoices/issue/{ENR}", allow_redirects=False)
with ctx():
    check("invoice idempotent",
          Invoice.query.filter_by(enrollment_id=ENR).count() == 1)

r = s_adm.get(f"{BASE}/admin/invoices/{IID}/pdf")
check("invoice PDF",
      r.status_code == 200 and r.content[:5] == b"%PDF-",
      f"{r.status_code}/{r.content[:5]}")
r = s_adm.get(f"{BASE}/admin/invoices")
check("invoices page lists",
      r.status_code == 200 and INUM in r.text, r.status_code)

r = s_adm.get(f"{BASE}/admin/finance")
check("finance page 200",
      r.status_code == 200 and "Revenue collected" in r.text, r.status_code)
with ctx():
    s = OPS.finance_summary()
    check("finance revenue reconciles", s["revenue"] >= 53100, s["revenue"])
    check("finance discounts include coupon",
          s["discounts_total"] >= round(FEE * 10 / 100), s["discounts_total"])
r = s_adm.get(f"{BASE}/admin/finance.csv")
check("finance CSV", r.status_code == 200 and "pay_p9test1" in r.text,
      r.status_code)

r = s_adm.post(f"{BASE}/admin/invoice-settings",
               data={"business_name": "Sayyed EdVantage",
                     "gstin": "27ABCDE1234F1Z5", "sac_code": "999293",
                     "gst_rate": "18", "invoice_prefix": "SE",
                     "email": "sayyededvantage@gmail.com",
                     "phone": "+91 7977877884", "address": "", "notes": ""})
check("invoice settings saved", r.status_code in (200, 302), r.status_code)
with ctx():
    check("invoice settings audit",
          AuditLog.query.filter_by(action="invoice.settings").count() >= 1)

# ---------------------------------------------------------------- 7. refunds
r = s_adm.post(f"{BASE}/admin/refunds",
               data={"enrollment_id": ENR, "amount": "5000",
                     "reason": "p9 test refund"})
with ctx():
    rf = Refund.query.filter_by(enrollment_id=ENR).order_by(
        Refund.id.desc()).first()
    RID = rf.id if rf else None
    check("refund requested",
          rf and rf.status == "requested" and rf.amount == 5000)
r = s_adm.post(f"{BASE}/admin/refunds/{RID}/approve")
with ctx():
    rf = db.session.get(Refund, RID)
    check("refund approved", rf.status == "approved")
    s = OPS.finance_summary()
    check("finance refunds total", s["refunds_total"] >= 5000,
          s["refunds_total"])

# ---------------------------------------------------------------- 8. regression guards
r = s_stu.get(f"{BASE}/live/join/999999")
check("join 404 for missing session", r.status_code == 404, r.status_code)
with ctx():
    b = Batch(name="P9 Ann Batch", course_id=COURSE_ID)
    db.session.add(b)
    db.session.commit()
    db.session.add(Announcement(title="P9 batch note", body="hi",
                                active=True, batch_id=b.id))
    db.session.add(Announcement(title="P9 site-wide note", body="hello all",
                                active=True, batch_id=None))
    db.session.commit()
    check("batch-targeted announcement",
          Announcement.query.filter_by(batch_id=b.id).count() == 1)
r = s_stu.get(f"{BASE}/")
check("global banner shows site-wide announcement",
      "P9 site-wide note" in r.text, r.status_code)
check("batch announcement not a global banner",
      "P9 batch note" not in r.text)

print(f"\n== Phase 9: {passed} passed, {failed} failed ==")
if notes:
    print("FAILURES:", notes)
sys.exit(1 if failed else 0)
