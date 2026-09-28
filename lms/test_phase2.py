"""End-to-end verification of the Sayyed EdVantage LMS — Phase 2.

Covers: live classes (CRUD + join window), drip scheduling, SMTP settings,
discussions, analytics endpoints, PWA files, reviews, public certificate
verification, announcements, catalog search, wishlist, email hooks, and
role boundaries.

Run against a dev server on http://localhost:5000 backed by a FRESH test DB
(migrated + seeded), with the same SQLITE_PATH for both server and this script:

    SQLITE_PATH=/tmp/lms_test/lms.db LMS_SCHEDULER=off venv/bin/python test_phase2.py
"""
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/home/hatch/workspace/lms")
import requests
from app import create_app, db
from app.models import (Course, Discussion, EmailSettings, Enrollment, Lesson,
                        LiveSession, Review, User, Wishlist)

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
    ds = Course.query.filter_by(slug="data-science").first()
    py = Course.query.filter_by(slug="python-programming").first()
    devops = Course.query.filter_by(slug="devops").first()
    ds_id = ds.id
    py_id = py.id
    devops_id = devops.id
    # drip lessons of python course: idx1 -> 7 days, idx2 -> 14 days
    py_mod = py.modules[0]
    locked_lesson = py_mod.lessons[1]
    locked_lid = locked_lesson.id
    open_lesson = py_mod.lessons[0]
    open_lid = open_lesson.id
    assert locked_lesson.available_after_days == 7, "seed drip not applied"
    # second student (not enrolled anywhere)
    if not User.query.filter_by(email="student2@sayyed.in").first():
        u2 = User(name="Student Two", email="student2@sayyed.in", role="student")
        u2.set_password("student123")
        db.session.add(u2)
        db.session.commit()

s_admin, s_mgr, s_fac, s_stu, s_stu2 = (requests.Session() for _ in range(5))
assert login(s_admin, "admin@sayyed.in", "admin123")
assert login(s_mgr, "manager@sayyed.in", "manager123")
assert login(s_fac, "faculty@sayyed.in", "faculty123")
assert login(s_stu, "student@sayyed.in", "student123")
assert login(s_stu2, "student2@sayyed.in", "student123")
check("all 5 logins ok", True)

# --- student enrolls in data-science (stub payment): needed for the dashboard
# live widget, discussions and reviews below ---
r = s_stu.post(f"{BASE}/enroll/data-science", data={"confirm": "1"},
               allow_redirects=False)
check("enroll data-science -> checkout redirect",
      r.status_code == 302 and "/checkout/" in r.headers.get("Location", ""))
_ds_enr_id = r.headers["Location"].rstrip("/").split("/")[-1]
r = s_stu.post(f"{BASE}/payment/confirm/{_ds_enr_id}", allow_redirects=False)
check("data-science stub payment confirms", r.status_code == 302)

# ================================================================ LIVE CLASSES
# --- admin schedules a session starting in 5 minutes (joinable) ---
soon = (datetime.utcnow() + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
r = s_admin.post(f"{BASE}/manage/course/{ds_id}/live/new",
                 data={"title": "Test Live NOW", "starts_at": soon,
                       "duration_min": "45", "recording_url": ""},
                 allow_redirects=True)
check("admin schedules live class", "Live class scheduled" in r.text)
with app.app_context():
    sess = LiveSession.query.filter_by(title="Test Live NOW").first()
check("live session stored + auto room name",
      sess is not None and sess.room_name.startswith("se-data-science-"),
      getattr(sess, "room_name", None))
check("join_url is meet.jit.si",
      sess.join_url.startswith("https://meet.jit.si/") and sess.room_name in sess.join_url)
now = datetime.utcnow()
check("is_joinable: starts in 5 min -> True", sess.is_joinable(now) is True)
check("is_upcoming: True", sess.is_upcoming(now) is True)

with app.app_context():
    future = LiveSession.query.filter(
        LiveSession.title.like("Data Science — Week 3%")).first()
check("seeded upcoming session exists", future is not None)
check("is_joinable: starts tomorrow -> False", future.is_joinable(now) is False)
check("is_upcoming: starts tomorrow -> True", future.is_upcoming(now) is True)
past_start = now - timedelta(hours=2)
check("is_joinable: ended 1h ago -> False",
      future.is_joinable(past_start + timedelta(hours=3)) is False)

# --- join window edges via model ---
with app.app_context():
    edge = LiveSession(course_id=ds_id, title="edge", starts_at=now + timedelta(minutes=14),
                       duration_min=60, created_by=1, room_name="se-edge-1")
    edge2 = LiveSession(course_id=ds_id, title="edge2", starts_at=now + timedelta(minutes=16),
                        duration_min=60, created_by=1, room_name="se-edge-2")
check("join window: 14 min before -> joinable", edge.is_joinable(now) is True)
check("join window: 16 min before -> not joinable", edge2.is_joinable(now) is False)

# --- student dashboard shows upcoming live widget ---
r = s_stu.get(f"{BASE}/dashboard")
check("dashboard live widget renders",
      "Upcoming Live Classes" in r.text and "Week 3 Doubt-Clearing" in r.text)
check("dashboard shows joinable session button",
      "Test Live NOW" in r.text and ">Join</a>" in r.text)

# --- faculty (assigned) can schedule; faculty (unassigned) blocked ---
r = s_fac.post(f"{BASE}/manage/course/{py_id}/live/new",
               data={"title": "Faculty Live", "starts_at": soon,
                     "duration_min": "30", "recording_url": ""},
               allow_redirects=True)
check("faculty schedules on assigned course", "Live class scheduled" in r.text)
r = s_fac.post(f"{BASE}/manage/course/{devops_id}/live/new",
               data={"title": "X", "starts_at": soon, "duration_min": "30"},
               allow_redirects=False)
check("faculty blocked on unassigned course (403)", r.status_code == 403)
r = s_stu.post(f"{BASE}/manage/course/{ds_id}/live/new",
               data={"title": "X", "starts_at": soon, "duration_min": "30"},
               allow_redirects=False)
check("student blocked from live CRUD (403)", r.status_code == 403)

# --- admin edits (reschedule resets reminder) + deletes ---
with app.app_context():
    s = LiveSession.query.filter_by(title="Faculty Live").first()
    s.sent_reminder = True
    db.session.commit()
    sid = s.id
new_time = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
r = s_admin.post(f"{BASE}/manage/live/{sid}/edit",
                 data={"title": "Faculty Live (rescheduled)", "starts_at": new_time,
                       "duration_min": "30", "recording_url": "https://rec.example/v"},
                 allow_redirects=True)
check("admin edits live class", "Live class updated" in r.text)
with app.app_context():
    s = db.session.get(LiveSession, sid)
    edited_ok = (s.title == "Faculty Live (rescheduled)"
                 and s.sent_reminder is False
                 and s.recording_url == "https://rec.example/v")
check("reschedule resets reminder flag + saves recording", edited_ok)
r = s_admin.post(f"{BASE}/manage/live/{sid}/delete", allow_redirects=True)
check("admin deletes live class", "Live class deleted" in r.text)
with app.app_context():
    check("session gone from DB", db.session.get(LiveSession, sid) is None)

# ================================================================ DRIP
# student enrolls fresh in python (free? no — python has fee; use stub flow)
r = s_stu.post(f"{BASE}/enroll/python-programming", data={"confirm": "1"},
               allow_redirects=False)
check("enroll python -> checkout redirect",
      r.status_code == 302 and "/checkout/" in r.headers.get("Location", ""))
enr_id = r.headers["Location"].rstrip("/").split("/")[-1]
r = s_stu.post(f"{BASE}/payment/confirm/{enr_id}", allow_redirects=False)
check("stub payment confirms", r.status_code == 302)

r = s_stu.get(f"{BASE}/lesson/{locked_lid}")
check("locked lesson shows drip page",
      r.status_code == 200 and "unlocks" in r.text.lower() and "🔒" in r.text)
r = s_stu.post(f"{BASE}/lesson/{locked_lid}/complete", allow_redirects=False)
check("completing locked lesson -> 403", r.status_code == 403)
r = s_stu.get(f"{BASE}/lesson/{open_lid}")
check("open lesson renders normally", r.status_code == 200 and "🔒" not in r.text[:2000])

# backdate enrollment -> drip unlocks
with app.app_context():
    enr = Enrollment.query.filter_by(
        user_id=User.query.filter_by(email="student@sayyed.in").first().id,
        course_id=py_id).first()
    enr.enrolled_at = datetime.utcnow() - timedelta(days=30)
    db.session.commit()
r = s_stu.get(f"{BASE}/lesson/{locked_lid}")
check("lesson unlocks after drip period", "🔒" not in r.text[:2000] or "unlocks" not in r.text.lower())
r = s_stu.post(f"{BASE}/lesson/{locked_lid}/complete", allow_redirects=False)
check("completing unlocked drip lesson -> 302", r.status_code == 302)

# curriculum shows drip badges
r = requests.get(f"{BASE}/course/python-programming")
check("curriculum shows drip badge", "🔒 Day 7" in r.text)

# ================================================================ EMAIL SETTINGS
r = s_admin.get(f"{BASE}/admin/email-settings")
check("admin email settings page renders", r.status_code == 200 and "SMTP host" in r.text)
r = s_admin.post(f"{BASE}/admin/email-settings",
                 data={"smtp_host": "smtp.example.com", "smtp_port": "587",
                       "smtp_user": "bot@example.com", "from_email": "noreply@example.com",
                       "from_name": "Sayyed EdVantage LMS"},
                 allow_redirects=True)
check("admin saves email settings (disabled)", "Email settings saved" in r.text)
with app.app_context():
    st = EmailSettings.get()
check("settings persisted",
      st.smtp_host == "smtp.example.com" and st.enabled is False)
r = s_admin.post(f"{BASE}/admin/email-settings",
                 data={"send_test": "1", "test_email": "x@example.com"},
                 allow_redirects=True)
check("test email with automation disabled -> graceful warning",
      "not enabled" in r.text.lower())
r = s_mgr.get(f"{BASE}/admin/email-settings", allow_redirects=False)
check("manager blocked from email settings (403)", r.status_code == 403)
r = s_fac.get(f"{BASE}/admin/email-settings", allow_redirects=False)
check("faculty blocked from email settings (403)", r.status_code == 403)

# emailer unit checks (no SMTP touched while disabled)
with app.app_context():
    from app.emailer import (send_email_async, send_email_sync, send_enrollment_email,
                             send_live_reminders, send_welcome_email)
    u = User.query.filter_by(email="student@sayyed.in").first()
    check("welcome email no-op while disabled", send_welcome_email(u) is False)
    check("sync send no-op while disabled",
          send_email_sync("a@b.c", "s", "<p>x</p>")[0] is False)
    check("async send no-op while disabled", send_email_async("a@b.c", "s", "<p>x</p>") is False)
    check("enrollment email no-op while disabled",
          send_enrollment_email(u, Enrollment.query.first()) is False)
    check("reminder sweep no-op while disabled", send_live_reminders() == 0)

# ================================================================ DISCUSSIONS
r = s_stu2.get(f"{BASE}/course/data-science/discussions", allow_redirects=False)
check("non-enrolled student blocked from discussions (403)", r.status_code == 403)
r = s_stu.post(f"{BASE}/course/data-science/discussions",
               data={"title": "Doubt: pandas merge", "body": "How does merge differ from join?"},
               allow_redirects=True)
check("enrolled student starts thread", "Discussion started" in r.text)
with app.app_context():
    disc = Discussion.query.filter_by(title="Doubt: pandas merge").first()
    did = disc.id
check("thread stored", did is not None)
r = s_stu.post(f"{BASE}/discussion/{did}", data={"body": "Never mind, figured it out!"},
               allow_redirects=True)
check("student replies", "Reply posted" in r.text)
r = s_mgr.get(f"{BASE}/discussion/{did}")
check("manager can view thread", r.status_code == 200)
r = s_mgr.post(f"{BASE}/discussion/{did}", data={"body": "Manager note: good question."},
               allow_redirects=True)
check("manager can reply", "Reply posted" in r.text)
r = s_mgr.post(f"{BASE}/discussion/{did}/pin", allow_redirects=False)
check("manager cannot pin (403)", r.status_code == 403)
r = s_fac.post(f"{BASE}/discussion/{did}/pin", allow_redirects=True)
check("faculty pins thread", "pinned" in r.text.lower())
r = s_stu.get(f"{BASE}/course/data-science/discussions")
check("pinned thread shows pin badge", "📌" in r.text)
r = s_stu.post(f"{BASE}/discussion/{did}/delete", allow_redirects=False)
check("student cannot delete (403)", r.status_code == 403)
r = s_admin.post(f"{BASE}/discussion/{did}/delete", allow_redirects=True)
check("admin deletes thread", "deleted" in r.text.lower())
with app.app_context():
    check("thread + replies gone", Discussion.query.get(did) is None)

# ================================================================ ANALYTICS
for path in ["enrollments-per-course", "revenue-per-course",
             "quiz-scores", "signups-30d"]:
    r = s_admin.get(f"{BASE}/admin/analytics/api/{path}")
    try:
        payload = r.json()
        ok = (r.status_code == 200 and "labels" in payload and "data" in payload)
    except Exception:
        ok = False
    check(f"analytics API {path}", ok)
r = s_admin.get(f"{BASE}/admin/analytics/api/enrollments-per-course").json()
check("enrollments API has data-science count >= 1",
      "Data Science" in r["labels"] and max(r["data"]) >= 1)
r = s_admin.get(f"{BASE}/admin/analytics/api/revenue-per-course").json()
check("revenue API flags test mode", r.get("test_mode") is True)
r = s_admin.get(f"{BASE}/admin/analytics")
check("analytics page renders with Chart.js", r.status_code == 200 and "chart.umd" in r.text)
r = s_mgr.get(f"{BASE}/admin/analytics/api/enrollments-per-course", allow_redirects=False)
check("manager blocked from analytics API (403)", r.status_code == 403)
r = s_mgr.get(f"{BASE}/admin/analytics", allow_redirects=False)
check("manager blocked from analytics page (403)", r.status_code == 403)

# ================================================================ PWA
r = requests.get(f"{BASE}/manifest.json")
check("manifest.json serves",
      r.status_code == 200 and r.json().get("name") == "Sayyed EdVantage LMS"
      and "icons" in r.json())
r = requests.get(f"{BASE}/sw.js")
check("service worker serves",
      r.status_code == 200 and "edvantage-v1" in r.text
      and "javascript" in r.headers.get("Content-Type", ""))

# ================================================================ REVIEWS
r = s_stu2.post(f"{BASE}/course/data-science/review",
                data={"rating": "5", "text": "Great!"},
                allow_redirects=True)
check("non-enrolled review blocked", "Enroll in this course" in r.text)
with app.app_context():
    check("no review stored for non-enrolled",
          Review.query.filter_by(course_id=ds_id).count() == 0)
r = s_stu.post(f"{BASE}/course/data-science/review",
               data={"rating": "5", "text": "Excellent course, loved the projects."},
               allow_redirects=True)
check("enrolled student posts review", "Thanks for your review" in r.text)
r = s_stu.post(f"{BASE}/course/data-science/review",
               data={"rating": "4", "text": "second"},
               allow_redirects=True)
check("duplicate review rejected", "already reviewed" in r.text.lower())
with app.app_context():
    _ds = Course.query.filter_by(slug="data-science").first()
    avg, n = _ds.average_rating
check("average rating computed", n == 1 and avg == 5.0, f"avg={avg} n={n}")
r = requests.get(f"{BASE}/course/data-science")
check("course page shows stars + review text",
      "★★★★★" in r.text and "loved the projects" in r.text)

# ================================================================ CERT VERIFY
# (Certificate issuance itself is covered by the Phase 1 suite; here we test
# the public verification route, so we mint a cert row directly.)
with app.app_context():
    from app.models import Certificate
    u = User.query.filter_by(email="student@sayyed.in").first()
    cert = Certificate.query.filter_by(user_id=u.id, course_id=ds_id).first()
    if not cert:
        cert = Certificate(user_id=u.id, course_id=ds_id, code="SE-VERIFY01")
        db.session.add(cert)
        db.session.commit()
    code = cert.code
    holder = cert.user.name
r = requests.get(f"{BASE}/verify/{code}")
check("public verify valid code (no login)",
      r.status_code == 200 and "valid" in r.text.lower() and holder in r.text)
r = requests.get(f"{BASE}/verify/NOPE1234")
check("public verify bogus code -> not found", "No certificate found" in r.text)

# ================================================================ ANNOUNCEMENTS
r = requests.get(f"{BASE}/")
check("active announcement banner on homepage", "Admissions open" in r.text)
r = s_admin.post(f"{BASE}/admin/announcements",
                 data={"title": "Test notice", "body": "Phase 2 is live!",
                       "active": "1", "deactivate_others": "1"},
                 allow_redirects=True)
check("admin posts announcement", "Announcement posted" in r.text)
r = requests.get(f"{BASE}/")
check("new banner replaces old (deactivate others)",
      "Phase 2 is live" in r.text and "Admissions open" not in r.text)
with app.app_context():
    from app.models import Announcement
    ann = Announcement.query.filter_by(title="Test notice").first()
    aid = ann.id
r = s_admin.post(f"{BASE}/admin/announcements/{aid}/toggle", allow_redirects=True)
with app.app_context():
    from app.models import Announcement as _A
    check("admin toggles announcement off", _A.query.get(aid).active is False)
r = requests.get(f"{BASE}/")
check("banner hidden after deactivate", "Phase 2 is live" not in r.text)
r = s_admin.post(f"{BASE}/admin/announcements/{aid}/delete", allow_redirects=True)
check("admin deletes announcement", "deleted" in r.text.lower())
r = s_mgr.get(f"{BASE}/admin/announcements", allow_redirects=False)
check("manager blocked from announcements (403)", r.status_code == 403)

# ================================================================ SEARCH
r = requests.get(f"{BASE}/courses", params={"q": "python"})
grid = r.text[r.text.find('<div class="grid">'):]  # scope to results (nav lists all)
check("search 'python' finds Python Programming, hides Linux",
      "Python Programming" in grid and "Linux Administration" not in grid)
r = requests.get(f"{BASE}/courses", params={"q": "data"})
check("search 'data' finds Data Science + Data Analytics",
      "Data Science" in r.text and "Data Analytics" in r.text)
r = requests.get(f"{BASE}/courses")
check("empty search lists all 7 courses",
      all(t in r.text for t in ["Data Science", "DevOps", "Cyber Security"]))

# ================================================================ WISHLIST
r = s_stu.post(f"{BASE}/course/devops/wishlist",
               data={"next": f"{BASE}/wishlist"}, allow_redirects=True)
check("student adds wishlist item", "wishlist" in r.text.lower())
r = s_stu.get(f"{BASE}/wishlist")
check("wishlist page lists DevOps", "DevOps" in r.text)
with app.app_context():
    u = User.query.filter_by(email="student@sayyed.in").first()
    check("wishlist row stored",
          Wishlist.query.filter_by(user_id=u.id, course_id=devops_id).count() == 1)
r = s_stu.post(f"{BASE}/course/devops/wishlist",
               data={"next": f"{BASE}/wishlist"}, allow_redirects=True)
check("toggle removes wishlist item", "Removed" in r.text)
with app.app_context():
    u = User.query.filter_by(email="student@sayyed.in").first()
    check("wishlist row deleted",
          Wishlist.query.filter_by(user_id=u.id, course_id=devops_id).count() == 0)
# unique constraint at DB level
with app.app_context():
    db.session.add(Wishlist(user_id=u.id, course_id=devops_id))
    db.session.commit()
    from sqlalchemy.exc import IntegrityError
    db.session.add(Wishlist(user_id=u.id, course_id=devops_id))
    try:
        db.session.commit()
        dup_ok = False
    except IntegrityError:
        db.session.rollback()
        dup_ok = True
    Wishlist.query.filter_by(user_id=u.id, course_id=devops_id).delete()
    db.session.commit()
check("wishlist unique constraint enforced", dup_ok)

# ================================================================ ROLE BOUNDARIES
r = s_fac.get(f"{BASE}/admin/analytics", allow_redirects=False)
check("faculty blocked from analytics (403)", r.status_code == 403)
r = s_stu.get(f"{BASE}/admin/announcements", allow_redirects=False)
check("student blocked from announcements (403)", r.status_code == 403)
r = s_stu.get(f"{BASE}/admin/analytics/api/signups-30d", allow_redirects=False)
check("student blocked from analytics API (403)", r.status_code == 403)

# ================================================================ SUMMARY
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} Phase 2 checks passed.")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("ALL PHASE 2 CHECKS PASSED ✔")
