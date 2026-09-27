"""End-to-end verification of the Sayyed EdVantage LMS — Phase 4.

Covers: CRM leads (pipeline, timeline, follow-ups, filters, analytics,
scoring), admissions (application form, approve/reject, batches),
AI sales-agent chat (intents, fees, lead capture, hot-flagging, guardrails),
counsellor role boundaries, onboarding checklist, referral→lead hook.

Run against a dev server on http://localhost:5000 backed by a FRESH test DB
(migrated via `flask db upgrade` + seeded), with the same SQLITE_PATH for
both server and this script:

    SQLITE_PATH=/tmp/lms_test4/lms.db LMS_SCHEDULER=off venv/bin/python test_phase4.py
"""
import sys
from datetime import date, timedelta

sys.path.insert(0, "/home/hatch/workspace/lms")
import requests
from app import create_app, db
from app.models import (Application, Batch, BatchMember, ChatConversation,
                        Course, Lead, LeadActivity, OnboardingTask, User)

BASE = "http://localhost:5000"
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


def login(sess, email, pw):
    r = sess.post(f"{BASE}/login", data={"email": email, "password": pw},
                  allow_redirects=True)
    return "Logout" in r.text or "dashboard" in r.url.lower()


app = create_app()
with app.app_context():
    py = Course.query.filter_by(slug="python-programming").first()
    assert py is not None, "seed courses missing"
    py_id = py.id
    # counsellor seed user (added to seed.py in Phase 4)
    if not User.query.filter_by(email="counsellor@sayyed.in").first():
        u = User(name="Counsellor User", email="counsellor@sayyed.in",
                 role="counsellor")
        u.set_password("counsellor123")
        db.session.add(u)
        db.session.commit()

s_admin = requests.Session()
s_mgr = requests.Session()
s_coun = requests.Session()
s_fac = requests.Session()
s_stu = requests.Session()
assert login(s_admin, "admin@sayyed.in", "admin123")
assert login(s_mgr, "manager@sayyed.in", "manager123")
assert login(s_coun, "counsellor@sayyed.in", "counsellor123")
assert login(s_fac, "faculty@sayyed.in", "faculty123")
assert login(s_stu, "student@sayyed.in", "student123")
check("all 5 logins ok (incl. counsellor)", True)
check("counsellor lands on CRM",
      s_coun.get(f"{BASE}/login", allow_redirects=True).url.endswith("/crm/leads"))

# ================================================================ PUBLIC PAGES
for url, name in [("/enquiry", "enquiry"), ("/apply", "application form"),
                  ("/api/chat/status", "chat status")]:
    r = requests.get(f"{BASE}{url}")
    check(f"public {name} 200", r.status_code == 200, f"{r.status_code}")
check("chat widget on homepage", 'id="chat-panel"' in requests.get(f"{BASE}/").text)
check("enquire nav link", "/enquiry" in requests.get(f"{BASE}/").text)

# ================================================================ AI CHAT
s = requests.Session()
r = s.post(f"{BASE}/api/chat", json={"message": "What are the fees?"})
d = r.json()
check("chat fee list 200", r.status_code == 200)
check("chat lists all 7 fees",
      all(x in d["reply"] for x in ["50,000", "70,000", "35,000", "40,000",
                                    "25,000", "45,000", "60,000"]), d["reply"][:50])
cid = d["conversation_id"]
check("conversation id issued", bool(cid))

r = s.post(f"{BASE}/api/chat", json={"conversation_id": cid,
                                     "message": "Tell me about data science"})
check("chat course match -> Data Science",
      "Data Science" in r.json()["reply"], r.json()["reply"][:60])

r = s.post(f"{BASE}/api/chat", json={"conversation_id": cid,
                                     "message": "my name is Ravi Kumar, my number is 9876501234"})
d2 = r.json()
check("chat phone capture reply", "9876501234" in d2["reply"], d2["reply"][:70])

with app.app_context():
    lead = Lead.query.filter_by(phone="9876501234").first()
    lead_hot = lead.score == "hot" and lead.follow_up_date == date.today()
    lead_timeline = any("HIGH-INTENT" in a.text for a in lead.activities)
check("chat created CRM lead", lead is not None)
if lead:
    check("chat lead hot + follow-up today", lead_hot, f"{lead.score}/{lead.follow_up_date}")
    check("chat lead timeline has high-intent note", lead_timeline)

# guardrail: fees quoted are only approved ones
import re
amounts = set()
with app.app_context():
    conv = ChatConversation.query.get(cid)
    for m in conv.messages:
        if m.role == "assistant":
            for raw in re.findall(r"₹\s?([\d,]+)", m.text):
                amounts.add(int(raw.replace(",", "")))
    approved = {c.fee for c in Course.query.filter_by(is_bonus=False).all()}
check("chat never invents fees", amounts <= approved, str(sorted(amounts)))

# graceful degradation: no key configured here -> rules engine still answers
r = s.post(f"{BASE}/api/chat", json={"message": "hello"})
check("chat works without OPENAI_API_KEY", r.status_code == 200 and len(r.json()["reply"]) > 10)

# ================================================================ ENQUIRY -> LEAD
r = requests.post(f"{BASE}/enquiry",
                  data={"name": "Enquiry Eva", "phone": "9811111111",
                        "email": "eva@example.com", "course_id": str(py_id),
                        "message": "Want details"},
                  allow_redirects=True)
check("enquiry POST ok", r.status_code == 200)
with app.app_context():
    ev = Lead.query.filter_by(phone="9811111111").first()
check("enquiry created lead", ev is not None and ev.source == "website"
      and ev.course_id == py_id and ev.status == "new", getattr(ev, "source", None))

# ================================================================ CRM: LEADS
r = s_coun.get(f"{BASE}/crm/leads")
check("counsellor leads 200", r.status_code == 200 and "Enquiry Eva" in r.text)
r = s_admin.get(f"{BASE}/crm/leads?status=new")
check("admin leads filter 200", r.status_code == 200)
r = s_mgr.get(f"{BASE}/crm/leads?followup=due")
check("manager leads 200", r.status_code == 200)
for sess, role in [(s_fac, "faculty"), (s_stu, "student")]:
    r = sess.get(f"{BASE}/crm/leads")
    check(f"{role} blocked from leads (403)", r.status_code == 403, r.status_code)

# manual lead + status pipeline + timeline
r = s_coun.post(f"{BASE}/crm/leads/new",
                data={"name": "Manual Max", "phone": "9822222222",
                      "email": "max@example.com", "course_id": str(py_id)},
                allow_redirects=True)
check("manual lead create", r.status_code == 200)
with app.app_context():
    mx = Lead.query.filter_by(phone="9822222222").first()
    mx_id = mx.id
r = s_coun.post(f"{BASE}/crm/leads/{mx_id}/status",
                data={"status": "contacted", "note": "Called, no answer"},
                allow_redirects=True)
check("status transition ok", r.status_code == 200)
with app.app_context():
    mx = Lead.query.get(mx_id)
    kinds = [a.kind for a in mx.activities]
check("timeline logged status change",
      mx.status == "contacted" and "status" in kinds and "system" in kinds,
      f"{mx.status}/{kinds}")

# note + follow-up
tomorrow = (date.today() + timedelta(days=1)).isoformat()
r = s_coun.post(f"{BASE}/crm/leads/{mx_id}/note",
                data={"text": "Call again tomorrow", "follow_up_date": tomorrow},
                allow_redirects=True)
check("note + follow-up saved", r.status_code == 200)
with app.app_context():
    mx = Lead.query.get(mx_id)
check("follow-up date set", mx.follow_up_date.isoformat() == tomorrow)
check("score warmed by engagement", mx.score in ("warm", "hot"), mx.score)

# assign + score override
with app.app_context():
    coun = User.query.filter_by(email="counsellor@sayyed.in").first()
    coun_id = coun.id
r = s_coun.post(f"{BASE}/crm/leads/{mx_id}/assign", data={"user_id": str(coun_id)},
                allow_redirects=True)
check("lead assign ok", r.status_code == 200)
r = s_coun.post(f"{BASE}/crm/leads/{mx_id}/score", data={"score": "hot"},
                allow_redirects=True)
check("score override ok", r.status_code == 200)
with app.app_context():
    check("score persisted hot", Lead.query.get(mx_id).score == "hot")

# follow-ups page + analytics
r = s_coun.get(f"{BASE}/crm/followups")
check("followups page 200", r.status_code == 200)
r = s_coun.get(f"{BASE}/crm/followups?mine=1")
check("my followups 200", r.status_code == 200)
r = s_coun.get(f"{BASE}/crm/analytics")
check("counsellor analytics 200 + funnel",
      r.status_code == 200 and "New" in r.text and "Enrolled" in r.text)
r = s_stu.get(f"{BASE}/crm/analytics")
check("student blocked from analytics (403)", r.status_code == 403)

# invalid status rejected
r = s_coun.post(f"{BASE}/crm/leads/{mx_id}/status", data={"status": "bogus"},
                allow_redirects=True)
with app.app_context():
    check("invalid status rejected", Lead.query.get(mx_id).status == "contacted")

# ================================================================ APPLICATIONS
r = requests.post(f"{BASE}/apply",
                  data={"name": "Applicant Ana", "phone": "9833333333",
                        "email": "ana@example.com", "course_id": str(py_id),
                        "education": "B.Sc", "batch_timing": "Evenings"},
                  allow_redirects=True)
check("application POST ok", r.status_code == 200)
with app.app_context():
    ap = Application.query.filter_by(email="ana@example.com").first()
    ap_id = ap.id if ap else None
check("application created pending", ap is not None and ap.status == "pending")
r = s_coun.get(f"{BASE}/crm/applications")
check("counsellor applications 200", r.status_code == 200 and "Applicant Ana" in r.text)
r = s_coun.get(f"{BASE}/crm/applications/{ap_id}")
check("application detail 200", r.status_code == 200)
r = s_stu.get(f"{BASE}/crm/applications")
check("student blocked from applications (403)", r.status_code == 403)

# approve -> user + enrollment + lead linked
r = s_admin.post(f"{BASE}/crm/applications/{ap_id}/approve",
                 data={"mode": "enrolled"}, allow_redirects=True)
check("approve ok", r.status_code == 200 and "Temporary password" in r.text)
with app.app_context():
    from app.models import Enrollment
    ap = Application.query.get(ap_id)
    u = User.query.filter_by(email="ana@example.com").first()
    enr = Enrollment.query.filter_by(user_id=u.id, course_id=py_id).first()
    lead = Lead.query.filter_by(phone="9833333333").first()
check("approve created user+active enrollment",
      ap.status == "approved" and u is not None and enr is not None
      and enr.status == "active", f"{ap.status}/{enr.status if enr else None}")
check("approve linked CRM lead as enrolled",
      lead is not None and lead.status == "enrolled"
      and lead.converted_user_id == u.id)

# reject path
requests.post(f"{BASE}/apply",
              data={"name": "Reject Raj", "phone": "9844444444",
                    "email": "raj@example.com", "course_id": str(py_id)},
              allow_redirects=True)
with app.app_context():
    rj = Application.query.filter_by(email="raj@example.com").first()
    rj_id = rj.id
r = s_coun.post(f"{BASE}/crm/applications/{rj_id}/reject",
                data={"reason": "Incomplete documents"}, allow_redirects=True)
check("reject ok", r.status_code == 200)
with app.app_context():
    rj = Application.query.get(rj_id)
check("reject persisted with reason",
      rj.status == "rejected" and "Incomplete" in rj.reject_reason)
# reject without reason refused
requests.post(f"{BASE}/apply",
              data={"name": "No Reason", "phone": "9855555555",
                    "email": "noreason@example.com", "course_id": str(py_id)},
              allow_redirects=True)
with app.app_context():
    nr = Application.query.filter_by(email="noreason@example.com").first()
    nr_id = nr.id
r = s_coun.post(f"{BASE}/crm/applications/{nr_id}/reject", data={"reason": ""},
                allow_redirects=True)
with app.app_context():
    check("reject needs reason", Application.query.get(nr_id).status == "pending")

# double-approve guarded
r = s_admin.post(f"{BASE}/crm/applications/{ap_id}/approve",
                 data={"mode": "enrolled"}, allow_redirects=True)
check("double approve guarded", "already reviewed" in r.text.lower())

# ================================================================ BATCHES
r = s_admin.post(f"{BASE}/crm/batches/new",
                 data={"name": "PY-Oct-Weekday", "course_id": str(py_id),
                       "schedule_text": "Mon/Wed/Fri 7-9 PM",
                       "start_date": date.today().isoformat(), "capacity": "30"},
                 allow_redirects=True)
check("batch create (admin)", r.status_code == 200)
with app.app_context():
    b = Batch.query.filter_by(name="PY-Oct-Weekday").first()
    b_id = b.id
check("batch persisted", b is not None and b.capacity == 30)
r = s_coun.get(f"{BASE}/crm/batches")
check("counsellor batches view 200", r.status_code == 200 and "PY-Oct-Weekday" in r.text)
r = s_coun.post(f"{BASE}/crm/batches/new", data={"name": "X", "course_id": str(py_id)},
                allow_redirects=False)
check("counsellor cannot create batch (403)", r.status_code == 403, r.status_code)
r = s_mgr.post(f"{BASE}/crm/batches/new",
               data={"name": "PY-Oct-Weekend", "course_id": str(py_id)},
               allow_redirects=True)
check("manager can create batch", r.status_code == 200)

# add member + remove member
r = s_admin.post(f"{BASE}/crm/batches/{b_id}/members",
                 data={"email": "student@sayyed.in"}, allow_redirects=True)
check("batch add member", r.status_code == 200)
with app.app_context():
    mem = BatchMember.query.filter_by(batch_id=b_id).first()
    mem_id = mem.id if mem else None
check("member persisted", mem is not None)
r = s_coun.post(f"{BASE}/crm/batches/{b_id}/members",
                data={"email": "student@sayyed.in"}, allow_redirects=False)
check("counsellor cannot add member (403)", r.status_code == 403, r.status_code)
r = s_admin.post(f"{BASE}/crm/batches/{b_id}/members/{mem_id}/remove",
                 allow_redirects=True)
check("batch remove member", r.status_code == 200)
with app.app_context():
    check("member removed", BatchMember.query.get(mem_id) is None)

# ================================================================ ONBOARDING
r = s_stu.get(f"{BASE}/dashboard")
check("dashboard shows onboarding checklist",
      r.status_code == 200 and "Getting Started" in r.text)
r = s_stu.post(f"{BASE}/onboarding/toggle/first_lesson")
check("onboarding toggle ok", r.json().get("ok") is True and r.json()["done"] is True)
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    t = OnboardingTask.query.filter_by(user_id=stu.id, key="first_lesson").first()
check("onboarding task persisted", t is not None and t.done is True)
r = s_stu.post(f"{BASE}/onboarding/toggle/bogus_key")
check("bad onboarding key 400", r.status_code == 400)
r = s_coun.post(f"{BASE}/onboarding/toggle/first_lesson")
check("non-student blocked from toggle (403)", r.status_code == 403)

# ================================================================ COUNSELLOR BOUNDARIES
blocked = [
    ("/admin/users", "users admin"),
    ("/admin/coupons", "coupons"),
    ("/admin/email-settings", "email settings"),
    ("/admin/whatsapp-settings", "whatsapp settings"),
    ("/admin/analytics", "admin analytics"),
    ("/admin/jobs", "job board admin"),
    ("/admin/announcements", "announcements"),
]
for url, name in blocked:
    r = s_coun.get(f"{BASE}{url}", allow_redirects=False)
    check(f"counsellor 403 on {name}", r.status_code == 403, r.status_code)
# counsellor CAN do CRM things
for url, name in [("/crm/leads", "leads"), ("/crm/applications", "applications"),
                  ("/crm/batches", "batches view"), ("/crm/analytics", "crm analytics"),
                  ("/crm/followups", "followups")]:
    r = s_coun.get(f"{BASE}{url}")
    check(f"counsellor can access {name}", r.status_code == 200, r.status_code)

# ================================================================ REFERRAL -> LEAD HOOK
with app.app_context():
    from app.growth import get_or_create_referral_code
    stu = User.query.filter_by(email="student@sayyed.in").first()
    rcode = get_or_create_referral_code(stu)
s2 = requests.Session()
s2.get(f"{BASE}/r/{rcode}", allow_redirects=True)  # sets referral cookie
r = s2.post(f"{BASE}/register",
            data={"name": "Referred Rita", "email": "rita@example.com",
                  "password": "rita12345", "phone": "9866666666"},
            allow_redirects=True)
check("referral signup ok", r.status_code == 200)
with app.app_context():
    rl = Lead.query.filter_by(email="rita@example.com").first()
check("referral signup created CRM lead",
      rl is not None and rl.source == "referral" and rl.score == "warm",
      f"{getattr(rl, 'source', None)}/{getattr(rl, 'score', None)}")

# ================================================================ SUMMARY
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\n==== PHASE 4: {passed}/{total} checks passed ====")
failed = [n for n, ok, e in results if not ok]
if failed:
    print("FAILED:", failed)
    sys.exit(1)
