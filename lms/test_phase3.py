"""End-to-end verification of the Sayyed EdVantage LMS — Phase 3.

Covers: referral & earn (codes, clicks, attribution, rewards, fraud guards,
admin), job board (CRUD, public listing, applications, status pipeline,
role boundaries), WhatsApp notifications (settings, fail-safe sends,
auto-hooks, token never exposed).

Run against a dev server on http://localhost:5000 backed by a FRESH test DB
(migrated via `flask db upgrade` + seeded), with the same SQLITE_PATH for
both server and this script:

    SQLITE_PATH=/tmp/lms_test3/lms.db LMS_SCHEDULER=off venv/bin/python test_phase3.py
"""
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, "/home/hatch/workspace/lms")
import requests
from app import create_app, db
from app.models import (Coupon, Enrollment, Job, JobApplication, Referral,
                        ReferralClick, ReferralSettings, User, WhatsAppSettings)

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
    from app.models import Course
    py = Course.query.filter_by(slug="python-programming").first()
    assert py is not None, "seed courses missing"
    py_id = py.id
    # fresh-phase-3 defaults
    ws = WhatsAppSettings.get()
    rs = ReferralSettings.get()
    assert ws.enabled is False, "WhatsApp must ship DISABLED"
    assert rs.enabled is True and rs.reward_percent == 10
    # extra users for referral scenarios
    for name, email in [("Ref Friend", "friend@sayyed.in"),
                        ("Freebie Fran", "freebie@sayyed.in"),
                        ("Second Wave", "wave@sayyed.in")]:
        if not User.query.filter_by(email=email).first():
            u = User(name=name, email=email, role="student",
                     phone="9876543210")
            u.set_password("student123")
            db.session.add(u)
    db.session.commit()

s_admin, s_mgr, s_fac, s_stu, s_friend = (requests.Session() for _ in range(5))
assert login(s_admin, "admin@sayyed.in", "admin123")
assert login(s_mgr, "manager@sayyed.in", "manager123")
assert login(s_fac, "faculty@sayyed.in", "faculty123")
assert login(s_stu, "student@sayyed.in", "student123")
assert login(s_friend, "friend@sayyed.in", "student123")
check("all 5 logins ok", True)

# ================================================================ REFERRALS
# --- referrer dashboard generates a code ---
r = s_stu.get(f"{BASE}/referrals")
check("student refer dashboard 200", r.status_code == 200)
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    code = stu.referral_code
check("referral code generated, SE-prefix",
      bool(code) and code.startswith("SE") and len(code) == 8, code)
check("dashboard shows /r/ link", f"/r/{code}" in r.text)
check("dashboard shows reward %", "10%" in r.text or "10 %" in r.text)

# --- /r/<code>: click recorded, cookie set, redirect to register ---
anon = requests.Session()
r = anon.get(f"{BASE}/r/{code}", allow_redirects=False)
check("referral link redirects to register",
      r.status_code == 302 and r.headers.get("Location", "").endswith("/register"))
check("se_ref cookie set", anon.cookies.get("se_ref") == code)
with app.app_context():
    clicks = ReferralClick.query.filter_by(code=code).count()
check("click recorded once", clicks == 1, clicks)
r = anon.get(f"{BASE}/r/{code}", allow_redirects=False)  # same IP again
with app.app_context():
    clicks2 = ReferralClick.query.filter_by(code=code).count()
check("duplicate click deduped", clicks2 == 1, clicks2)

# --- invalid code: no crash, no attribution ---
anon2 = requests.Session()
r = anon2.get(f"{BASE}/r/NOPE99", allow_redirects=False)
check("invalid referral code still redirects",
      r.status_code == 302 and r.headers.get("Location", "").endswith("/register"))
r = anon2.post(f"{BASE}/register",
               data={"name": "No Ref", "email": "noref@sayyed.in",
                     "password": "student123"}, allow_redirects=True)
with app.app_context():
    noref = User.query.filter_by(email="noref@sayyed.in").first()
    no_attr = Referral.query.filter_by(referred_id=noref.id).first()
check("invalid code -> no attribution", noref is not None and no_attr is None)

# --- valid attribution on signup ---
r = anon.post(f"{BASE}/register",
              data={"name": "Referred Rita", "email": "rita@sayyed.in",
                    "password": "student123", "phone": "9811111111"},
              allow_redirects=True)
check("referred signup ok", "Logout" in r.text)
with app.app_context():
    rita = User.query.filter_by(email="rita@sayyed.in").first()
    ref = Referral.query.filter_by(referred_id=rita.id).first()
check("referral row created (signed_up)",
      ref is not None and ref.referrer_id == stu.id and
      ref.status == Referral.STATUS_SIGNED_UP,
      getattr(ref, "status", None))
check("phone saved at registration", rita.phone == "9811111111")
r = s_stu.get(f"{BASE}/referrals")
check("dashboard shows 1 signup", "Referred Rita" in r.text)

# --- self-referral blocked (unit-level: own code) ---
with app.app_context():
    from app.growth import attribute_signup, get_or_create_referral_code
    fr = User.query.filter_by(email="friend@sayyed.in").first()
    fr_code = get_or_create_referral_code(fr)
    self_ref = attribute_signup(fr, fr_code)
    dup_ref = attribute_signup(rita, code)  # rita already attributed
check("self-referral blocked", self_ref is None)
check("double attribution blocked", dup_ref is None)
check("codes unique across users", fr_code != code, f"{fr_code} vs {code}")

# --- first PAID enrollment -> referrer rewarded ---
r = anon.post(f"{BASE}/enroll/python-programming", data={"confirm": "1"},
              allow_redirects=False)
check("referred enroll -> checkout", r.status_code == 302 and "/checkout/" in r.headers.get("Location", ""))
enr_id = r.headers["Location"].rstrip("/").split("/")[-1]
r = anon.post(f"{BASE}/payment/confirm/{enr_id}", allow_redirects=False)
check("referred stub payment confirms", r.status_code == 302)
with app.app_context():
    ref = Referral.query.filter_by(referred_id=rita.id).first()
    coupon = Coupon.query.filter_by(code=ref.coupon_code).first() if ref and ref.coupon_code else None
check("referral rewarded after first paid enrollment",
      ref.status == Referral.STATUS_REWARDED, ref.status)
check("reward coupon issued: 10%, one-time",
      coupon is not None and coupon.percent_off == 10 and
      coupon.max_uses == 1 and coupon.active, getattr(coupon, "code", None))
r = s_stu.get(f"{BASE}/referrals")
check("referrer dashboard shows reward coupon",
      coupon.code in r.text if coupon else False)

# --- second paid enrollment -> NO second reward ---
r = anon.post(f"{BASE}/enroll/data-science", data={"confirm": "1"},
              allow_redirects=False)
enr_id2 = r.headers["Location"].rstrip("/").split("/")[-1]
anon.post(f"{BASE}/payment/confirm/{enr_id2}", allow_redirects=False)
with app.app_context():
    n_coupons = Coupon.query.filter(Coupon.code.like("REF-%")).count()
check("one reward per referred user (no double-issue)", n_coupons == 1, n_coupons)

# --- FREE enrollment does NOT trigger reward ---
anon3 = requests.Session()
anon3.get(f"{BASE}/r/{code}", allow_redirects=False)
anon3.post(f"{BASE}/register",
           data={"name": "Free Fran", "email": "fran2@sayyed.in",
                 "password": "student123"}, allow_redirects=True)
r = anon3.post(f"{BASE}/enroll/git-github-essentials", data={"confirm": "1"},
               allow_redirects=True)
check("free bonus enrollment works", "happy learning" in r.text.lower())
with app.app_context():
    fran = User.query.filter_by(email="fran2@sayyed.in").first()
    ref_f = Referral.query.filter_by(referred_id=fran.id).first()
check("free enrollment -> no reward",
      ref_f is not None and ref_f.status == Referral.STATUS_SIGNED_UP,
      getattr(ref_f, "status", None))

# --- reward % configurable; disabled program issues nothing ---
r = s_admin.post(f"{BASE}/admin/referrals",
                 data={"reward_percent": "15", "enabled": "1"},
                 allow_redirects=True)
with app.app_context():
    rs = ReferralSettings.get()
check("admin sets reward % to 15", rs.reward_percent == 15)
anon4 = requests.Session()
anon4.get(f"{BASE}/r/{code}", allow_redirects=False)
anon4.post(f"{BASE}/register",
           data={"name": "Wave Two", "email": "wave2@sayyed.in",
                 "password": "student123"}, allow_redirects=True)
r = anon4.post(f"{BASE}/enroll/python-programming", data={"confirm": "1"},
               allow_redirects=False)
enr_id3 = r.headers["Location"].rstrip("/").split("/")[-1]
anon4.post(f"{BASE}/payment/confirm/{enr_id3}", allow_redirects=False)
with app.app_context():
    wave = User.query.filter_by(email="wave2@sayyed.in").first()
    ref_w = Referral.query.filter_by(referred_id=wave.id).first()
    c15 = Coupon.query.filter_by(code=ref_w.coupon_code).first()
check("15% reward coupon issued", c15 is not None and c15.percent_off == 15,
      getattr(c15, "code", None))
# disable program -> no attribution, no reward
s_admin.post(f"{BASE}/admin/referrals",
             data={"reward_percent": "15"}, allow_redirects=True)  # enabled unchecked
anon5 = requests.Session()
anon5.get(f"{BASE}/r/{code}", allow_redirects=False)
anon5.post(f"{BASE}/register",
           data={"name": "No Attr", "email": "noattr@sayyed.in",
                 "password": "student123"}, allow_redirects=True)
with app.app_context():
    na = User.query.filter_by(email="noattr@sayyed.in").first()
    na_id = na.id
with app.app_context():
    no_attr_row = Referral.query.filter_by(referred_id=na_id).first()
check("disabled program -> no attribution", no_attr_row is None)
s_admin.post(f"{BASE}/admin/referrals",
             data={"reward_percent": "10", "enabled": "1"},
             allow_redirects=True)  # restore

# --- admin referrals page + validate/invalidate + role boundaries ---
r = s_admin.get(f"{BASE}/admin/referrals")
check("admin referrals page 200", r.status_code == 200 and "Referral Program" in r.text)
for sess, role in [(s_stu, "student"), (s_mgr, "manager"), (s_fac, "faculty")]:
    r = sess.get(f"{BASE}/admin/referrals", allow_redirects=False)
    check(f"{role} blocked from admin referrals (403)", r.status_code == 403)
with app.app_context():
    ref_any = Referral.query.filter_by(status=Referral.STATUS_SIGNED_UP).first()
    ref_any_id = ref_any.id
r = s_admin.post(f"{BASE}/admin/referrals/{ref_any_id}/invalidate",
                 allow_redirects=True)
with app.app_context():
    st = Referral.query.get(ref_any_id).status
check("admin invalidate", st == Referral.STATUS_INVALID, st)
r = s_admin.post(f"{BASE}/admin/referrals/{ref_any_id}/validate",
                 allow_redirects=True)
with app.app_context():
    st = Referral.query.get(ref_any_id).status
check("admin re-validate", st in (Referral.STATUS_SIGNED_UP,
                                  Referral.STATUS_ENROLLED), st)

# ================================================================ JOB BOARD
# --- admin posts an internal-apply job ---
future = (date.today() + timedelta(days=30)).isoformat()
r = s_admin.post(f"{BASE}/admin/jobs",
                 data={"title": "Junior Data Analyst", "company": "Acme Analytics",
                       "type": "job", "location": "Mumbai", "remote": "1",
                       "skills": "Python, SQL", "description": "Entry-level analyst role.",
                       "deadline": future, "apply_mode": "internal",
                       "active": "1"}, allow_redirects=True)
check("admin posts job", "Junior Data Analyst" in r.text)
with app.app_context():
    job = Job.query.filter_by(title="Junior Data Analyst").first()
    job_id = job.id
check("job stored (remote, internal)", job is not None and job.remote is True and
      job.apply_mode == Job.APPLY_INTERNAL)

# --- manager can post too; student/faculty blocked ---
r = s_mgr.post(f"{BASE}/admin/jobs",
               data={"title": "ML Intern", "company": "Beta AI",
                     "type": "internship", "description": "Internship.",
                     "apply_mode": "internal", "active": "1"},
               allow_redirects=True)
check("manager posts job", "ML Intern" in r.text)
r = s_stu.post(f"{BASE}/admin/jobs", data={"title": "X"}, allow_redirects=False)
check("student blocked from posting job (403)", r.status_code == 403)
r = s_fac.post(f"{BASE}/admin/jobs", data={"title": "X"}, allow_redirects=False)
check("faculty blocked from posting job (403)", r.status_code == 403)

# --- public listing ---
r = requests.get(f"{BASE}/jobs")
check("public /jobs 200", r.status_code == 200 and "Junior Data Analyst" in r.text)
r = s_admin.get(f"{BASE}/admin/jobs")
check("admin jobs page 200", r.status_code == 200)

# --- inactive + expired jobs hidden ---
past = (date.today() - timedelta(days=1)).isoformat()
s_admin.post(f"{BASE}/admin/jobs",
             data={"title": "Old Posting", "company": "Old Co", "type": "job",
                   "description": "Expired.", "deadline": past,
                   "apply_mode": "internal", "active": "1"},
             allow_redirects=True)
s_admin.post(f"{BASE}/admin/jobs",
             data={"title": "Hidden Posting", "company": "Hid Co", "type": "job",
                   "description": "Inactive.", "apply_mode": "internal"},
             allow_redirects=True)  # active unchecked
r = requests.get(f"{BASE}/jobs")
check("expired job hidden", "Old Posting" not in r.text)
check("inactive job hidden", "Hidden Posting" not in r.text)

# --- student applies ---
r = s_friend.get(f"{BASE}/jobs/{job_id}")
check("job detail 200", r.status_code == 200 and "Apply now" in r.text)
r = s_friend.post(f"{BASE}/jobs/{job_id}/apply",
                  data={"phone": "9822222222", "cover_note": "I love data!"},
                  allow_redirects=True)
check("student applies", "Application sent" in r.text)
with app.app_context():
    fr = User.query.filter_by(email="friend@sayyed.in").first()
    appn = JobApplication.query.filter_by(job_id=job_id, user_id=fr.id).first()
    appn_id = appn.id
check("application stored (applied)", appn is not None and
      appn.status == JobApplication.STATUS_APPLIED)
check("phone updated from apply form", fr.phone == "9822222222", fr.phone)
r = s_friend.post(f"{BASE}/jobs/{job_id}/apply", data={},
                  allow_redirects=True)
with app.app_context():
    n_apps = JobApplication.query.filter_by(job_id=job_id, user_id=fr.id).count()
check("duplicate apply blocked", n_apps == 1 and "already applied" in r.text.lower())
r = s_friend.get(f"{BASE}/applications")
check("my applications shows it", "Junior Data Analyst" in r.text and
      "applied" in r.text.lower())

# --- external-mode job: no in-app apply ---
s_admin.post(f"{BASE}/admin/jobs",
             data={"title": "External Role", "company": "Ext Co", "type": "job",
                   "description": "Apply outside.", "apply_mode": "external",
                   "external_url": "https://example.com/apply", "active": "1"},
             allow_redirects=True)
with app.app_context():
    ext = Job.query.filter_by(title="External Role").first()
    ext_id = ext.id
r = s_friend.get(f"{BASE}/jobs/{ext_id}")
check("external job shows company link, no apply form",
      "example.com/apply" in r.text and "Apply now" not in r.text)
r = s_friend.post(f"{BASE}/jobs/{ext_id}/apply", data={},
                  allow_redirects=False)
check("POST apply to external job blocked",
      r.status_code == 302)  # redirected with warning
with app.app_context():
    n_ext = JobApplication.query.filter_by(job_id=ext_id).count()
check("no application row for external job", n_ext == 0)

# --- status pipeline: admin + manager update; student sees it ---
r = s_admin.post(f"{BASE}/admin/jobs/{job_id}/applications",
                 data={"app_id": appn_id, "status": "shortlisted"},
                 allow_redirects=True)
with app.app_context():
    st = JobApplication.query.get(appn_id).status
check("admin sets shortlisted", st == "shortlisted", st)
r = s_mgr.post(f"{BASE}/admin/jobs/{job_id}/applications",
               data={"app_id": appn_id, "status": "interviewed"},
               allow_redirects=True)
with app.app_context():
    st = JobApplication.query.get(appn_id).status
check("manager sets interviewed", st == "interviewed", st)
r = s_friend.get(f"{BASE}/applications")
check("student sees updated status", "interviewed" in r.text.lower())
r = s_stu.get(f"{BASE}/admin/jobs/{job_id}/applications",
              allow_redirects=False)
check("student blocked from admin applications (403)", r.status_code == 403)

# --- anon apply -> login; delete perms ---
r = requests.post(f"{BASE}/jobs/{job_id}/apply", data={},
                  allow_redirects=False)
check("anon apply redirected to login",
      r.status_code == 302 and "/login" in r.headers.get("Location", ""))
r = s_mgr.post(f"{BASE}/admin/jobs/{job_id}/delete", allow_redirects=False)
check("manager blocked from job delete (403)", r.status_code == 403)
with app.app_context():
    hid = Job.query.filter_by(title="Hidden Posting").first().id
r = s_admin.post(f"{BASE}/admin/jobs/{hid}/delete", allow_redirects=True)
with app.app_context():
    gone = Job.query.get(hid) is None
check("admin deletes job", gone)

# ================================================================ WHATSAPP
# --- settings page: admin only, token never rendered ---
r = s_admin.get(f"{BASE}/admin/whatsapp-settings")
check("admin whatsapp settings 200", r.status_code == 200 and
      "Cloud API Settings" in r.text)
for sess, role in [(s_stu, "student"), (s_mgr, "manager"), (s_fac, "faculty")]:
    r = sess.get(f"{BASE}/admin/whatsapp-settings", allow_redirects=False)
    check(f"{role} blocked from whatsapp settings (403)", r.status_code == 403)
r = s_admin.post(f"{BASE}/admin/whatsapp-settings",
                 data={"phone_number_id": "999888777666555",
                       "access_token": "SECRET_TEST_TOKEN_ABC123",
                       "enabled": "1"}, allow_redirects=True)
check("whatsapp settings saved", "saved" in r.text.lower())
r = s_admin.get(f"{BASE}/admin/whatsapp-settings")
check("access token NEVER rendered back",
      "SECRET_TEST_TOKEN_ABC123" not in r.text)
with app.app_context():
    w = WhatsAppSettings.get()
check("whatsapp enabled after save", w.enabled is True and
      w.phone_number_id == "999888777666555")

# --- unit-level: disabled / no-phone / normalize / fail-safe ---
with app.app_context():
    from app.whatsapp import (normalize_phone, send_whatsapp_async,
                              send_whatsapp_sync)
    w = WhatsAppSettings.get()  # fresh attached instance in this context
    check("normalize bare 10-digit -> 91 prefix",
          normalize_phone("9876543210") == "919876543210")
    check("normalize formatted number",
          normalize_phone("+91 98765 43210") == "919876543210")
    w.enabled = False
    db.session.commit()
    check("disabled -> async send is silent no-op",
          send_whatsapp_async("9876543210", "hi") is False)
    check("no phone -> async send is silent no-op",
          send_whatsapp_async("", "hi") is False)
    w.enabled = True
    db.session.commit()
    check("enabled -> async queues (True), never raises",
          send_whatsapp_async("9876543210", "test") is True)
    ok, msg = send_whatsapp_sync("9876543210", "test")
    check("sync send with bad creds fails gracefully, no raise",
          ok is False and "Send failed" in msg, msg[:60])

# --- admin test-send button surfaces failure cleanly ---
r = s_admin.post(f"{BASE}/admin/whatsapp-settings",
                 data={"send_test": "1", "test_phone": "919876543210"},
                 allow_redirects=True)
check("test-send button handles gateway failure",
      "Send failed" in r.text)

# --- enrollment hook is fail-safe with WhatsApp enabled ---
s_w = requests.Session()
assert login(s_w, "wave@sayyed.in", "student123")
with app.app_context():
    wv = User.query.filter_by(email="wave@sayyed.in").first()
    wv.phone = "9833333333"
    db.session.commit()
r = s_w.post(f"{BASE}/enroll/devops", data={"confirm": "1"},
             allow_redirects=False)
check("enroll works with WA enabled (checkout redirect)",
      r.status_code == 302 and "/checkout/" in r.headers.get("Location", ""))
enr_idx = r.headers["Location"].rstrip("/").split("/")[-1]
r = s_w.post(f"{BASE}/payment/confirm/{enr_idx}", allow_redirects=False)
check("payment confirm works with WA enabled", r.status_code == 302)

# --- live reminder hook: fail-safe, returns session count ---
with app.app_context():
    from app.emailer import send_live_reminders
    from app.models import Course, LiveSession
    c = Course.query.filter_by(slug="devops").first()
    ls = LiveSession(course_id=c.id, title="WA Reminder Test",
                     starts_at=datetime.utcnow() + timedelta(minutes=60),
                     duration_min=60, room_name="se-test-wa-reminder")
    db.session.add(ls)
    db.session.commit()
    n = send_live_reminders()
    check("live reminders run with WA hook (1 session)", n == 1, n)
    check("reminder claimed (no double-send)",
          LiveSession.query.get(ls.id).sent_reminder is True)

# ================================================================ SUMMARY
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} Phase 3 checks passed.")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("ALL PHASE 3 CHECKS PASSED ✔")
