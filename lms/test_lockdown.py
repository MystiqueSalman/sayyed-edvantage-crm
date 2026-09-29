"""Public-content lockdown: the public site is teaser-only.

Covers:
  1. GET /course/<slug>/recordings logged out -> redirect to login.
  2. Logged in but NOT enrolled -> 302 to the course page with the
     "Enroll to watch recorded sessions." flash (no video served).
  3. Pending-enrollment student -> same redirect (no video).
  4. Enrolled student -> 200 with the recording listed.
  5. Faculty of the course / admin -> 200 (staff bypass).
  6. Public course detail page is teaser-only: no <video, no live-join
     URL, no material /download link, no raw recording link — but the
     curriculum titles and live-class schedule still show.
  7. Public marketing pages (/, /courses) still render 200 anonymously.

Run: cd ~/workspace/lms && ./run_suite.sh test_lockdown
"""
import os
import sys
from datetime import datetime, timedelta

os.environ["LMS_SCHEDULER"] = "off"
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_lockdown.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "lms-local-test-secret-not-for-production")

sys.path.insert(0, "/home/hatch/workspace/lms")

from app import create_app, db  # noqa: E402
from app.models import (Course, Enrollment, LiveSession, Recording, User,  # noqa: E402
                        ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name +
          (f" — {extra}" if extra else ""))


app = create_app()

with app.app_context():
    stu = User(name="LD Student", email="ldstu@example.com", role=ROLE_STUDENT)
    stu.set_password("pw-ld-stu")
    outsider = User(name="LD Outsider", email="ldout@example.com",
                    role=ROLE_STUDENT)
    outsider.set_password("pw-ld-out")
    pending = User(name="LD Pending", email="ldpend@example.com",
                   role=ROLE_STUDENT)
    pending.set_password("pw-ld-pend")
    fac = User(name="LD Faculty", email="ldfac@example.com", role=ROLE_FACULTY)
    fac.set_password("pw-ld-fac")
    adm = User(name="LD Admin", email="ldadm@example.com", role=ROLE_ADMIN)
    adm.set_password("pw-ld-adm")
    db.session.add_all([stu, outsider, pending, fac, adm])
    db.session.flush()

    course = Course(title="LD Course", slug="ld-course", fee=40000,
                    short_desc="Lockdown test course",
                    description="Full description here.",
                    instructor_id=fac.id)
    db.session.add(course)
    db.session.flush()

    db.session.add(Enrollment(user_id=stu.id, course_id=course.id,
                              status="active", paid=True))
    db.session.add(Enrollment(user_id=pending.id, course_id=course.id,
                              status="pending", paid=False))
    rec = Recording(course_id=course.id, title="LD Recorded Class",
                    video_url="https://www.youtube.com/embed/ldxyz999",
                    duration_min=30)
    db.session.add(rec)
    sess = LiveSession(course_id=course.id, title="LD Upcoming Live",
                       starts_at=datetime.utcnow() + timedelta(days=1),
                       duration_min=60, room_name="ld-room-1",
                       recording_url="https://example.com/secret-rec.mp4")
    db.session.add(sess)
    db.session.commit()

client = app.test_client()


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


REC_URL = "/course/ld-course/recordings"
DETAIL_URL = "/course/ld-course"

# ================================================== 1. anonymous blocked
r = client.get(REC_URL, follow_redirects=False)
check("anonymous recordings -> login redirect",
      r.status_code in (301, 302, 303) and
      "login" in r.headers.get("Location", ""),
      f"status={r.status_code} loc={r.headers.get('Location')!r}")

# ================================================== 2/3. not enrolled / pending
out_c, _ = login_as("ldout@example.com", "pw-ld-out")
r = out_c.get(REC_URL, follow_redirects=False)
check("non-enrolled recordings -> redirect (no video)",
      r.status_code in (301, 302, 303) and DETAIL_URL in
      r.headers.get("Location", ""),
      f"status={r.status_code} loc={r.headers.get('Location')!r}")
r2 = out_c.get(r.headers["Location"])
check("non-enrolled sees enroll flash",
      "Enroll to watch recorded sessions." in r2.text)

pend_c, _ = login_as("ldpend@example.com", "pw-ld-pend")
r = pend_c.get(REC_URL, follow_redirects=False)
check("pending-enrollment recordings -> redirect (no video)",
      r.status_code in (301, 302, 303) and DETAIL_URL in
      r.headers.get("Location", ""),
      f"status={r.status_code}")

# ================================================== 4/5. enrolled + staff
stu_c, _ = login_as("ldstu@example.com", "pw-ld-stu")
r = stu_c.get(REC_URL)
check("enrolled student recordings -> 200", r.status_code == 200,
      f"status={r.status_code}")
check("enrolled student sees recording title",
      "LD Recorded Class" in r.text)

fac_c, _ = login_as("ldfac@example.com", "pw-ld-fac")
r = fac_c.get(REC_URL)
check("course faculty recordings -> 200 (staff bypass)",
      r.status_code == 200, f"status={r.status_code}")

adm_c, _ = login_as("ldadm@example.com", "pw-ld-adm")
r = adm_c.get(REC_URL)
check("admin recordings -> 200 (staff bypass)", r.status_code == 200,
      f"status={r.status_code}")

# ================================================== 6. teaser-only course page
r = client.get(DETAIL_URL)
check("public course detail -> 200", r.status_code == 200,
      f"status={r.status_code}")
html = r.text
check("no <video on public course page", "<video" not in html.lower())
check("no live-join URL on public course page", "live_join" not in html)
check("no Join button on public course page", "Join Live Class" not in html)
check("no material download link on public course page",
      "/download" not in html)
check("no raw recording URL on public course page",
      "secret-rec.mp4" not in html)
check("no Watch-recording shortcut for anonymous",
      "Watch recording" not in html)
check("teaser: course title shown", "LD Course" in html)
check("teaser: live class schedule listed", "LD Upcoming Live" in html)

# enrolled student sees the gated shortcut, not the raw URL
r = stu_c.get(DETAIL_URL)
check("enrolled sees Watch-recording shortcut",
      "Watch recording" in r.text)
check("enrolled page still hides raw recording URL",
      "secret-rec.mp4" not in r.text)

# enrolled recordings page routes playback through signed watch URLs
r = stu_c.get(REC_URL)
rec_html = r.text
check("enrolled recordings page -> 200", r.status_code == 200,
      f"status={r.status_code}")
check("enrolled recordings page uses signed watch URL",
      "/rec/" in rec_html)
check("enrolled recordings page hides raw video URL",
      "secret-rec.mp4" not in rec_html)
check("enrolled recordings page has no direct iframe embed",
      "<iframe" not in rec_html)

# ================================================== 7. marketing pages open
r = client.get("/")
check("public homepage -> 200", r.status_code == 200,
      f"status={r.status_code}")
r = client.get("/courses")
check("public catalog -> 200", r.status_code == 200,
      f"status={r.status_code}")

# ================================================== summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
