"""Live Classes page rework (2026-09-29): calendar removed, batch list.

Covers:
  1. GET /calendar is login-required (302 for anonymous).
  2. No calendar grid markup in the rendered page (no id="grid", no mtitle).
  3. Recorded Sessions tab: batch accordion grouped by enrolled batch;
     batch card shows batch details but NEVER faculty name/location.
  4. Date-wise rows newest-first; past session WITH linked recording ->
     green "Faculty joined" chip + signed Watch link (/rec/<token>);
     past session WITHOUT recording -> red "Faculty didn't join" chip,
     no Watch link. Rows show the REAL calendar date (e.g. "Mon, 8 Sep
     2026") — NO "Day N" labels anywhere.
  5. No student-attendance chip strings anywhere.
  6. Enrollment scoping: other course's batches/sessions invisible.
  7. Upcoming tab: soonest-first list; Join link only when is_joinable.
  8. Hash deep-link JS still present.
  9. Batch-level scoping (Phase 9 BatchMember roster):
     a. student in Batch A of a course does NOT see Batch B of same course;
     b. student in two batches sees exactly those two batch cards;
     c. enrolled student in no batch sees the empty state;
     d. faculty sees only their own batches.

Run: cd ~/workspace/lms && ./run_suite.sh test_live_classes_rework
"""
import os
import re
import sys
from datetime import date, datetime, timedelta

os.environ["LMS_SCHEDULER"] = "off"
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_live_classes_rework.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "lms-local-test-secret-not-for-production")

sys.path.insert(0, "/home/hatch/workspace/lms")

from app import create_app, db  # noqa: E402
from app.models import (Batch, BatchMember, Course, Enrollment, LiveSession,  # noqa: E402
                        Recording, User, ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name +
          (f" — {extra}" if extra else ""))


app = create_app()

with app.app_context():
    fac = User(name="LC Faculty Person", email="lcfac@example.com",
               role=ROLE_FACULTY)
    fac.set_password("pw-lc-fac")
    stu1 = User(name="LC Student One", email="lcstu1@example.com",
                role=ROLE_STUDENT)
    stu1.set_password("pw-lc-stu1")
    stu2 = User(name="LC Student Two", email="lcstu2@example.com",
                role=ROLE_STUDENT)
    stu2.set_password("pw-lc-stu2")
    stu3 = User(name="LC Student Three", email="lcstu3@example.com",
                role=ROLE_STUDENT)
    stu3.set_password("pw-lc-stu3")
    stu4 = User(name="LC Student Four", email="lcstu4@example.com",
                role=ROLE_STUDENT)
    stu4.set_password("pw-lc-stu4")
    fac2 = User(name="LC Other Faculty", email="lcotherfac@example.com",
                role=ROLE_FACULTY)
    fac2.set_password("pw-lc-fac2")
    adm = User(name="LC Admin", email="lcadm@example.com", role=ROLE_ADMIN)
    adm.set_password("pw-lc-adm")
    db.session.add_all([fac, fac2, stu1, stu2, stu3, stu4, adm])
    db.session.flush()

    ca = Course(title="LC Course A", slug="lc-course-a", fee=50000,
                instructor_id=fac.id)
    cb = Course(title="LC Course B", slug="lc-course-b", fee=60000,
                instructor_id=fac2.id)
    db.session.add_all([ca, cb])
    db.session.flush()

    db.session.add(Enrollment(user_id=stu1.id, course_id=ca.id,
                              status="active"))
    db.session.add(Enrollment(user_id=stu2.id, course_id=cb.id,
                              status="active"))
    db.session.add(Enrollment(user_id=stu3.id, course_id=ca.id,
                              status="active"))
    # stu4 is enrolled in course A but in NO batch -> sees empty state
    db.session.add(Enrollment(user_id=stu4.id, course_id=ca.id,
                              status="active"))

    batch1 = Batch(name="LC DS Weekday Batch", course_id=ca.id,
                   faculty_id=fac.id, schedule_text="Weekday",
                   start_date=date(2024, 7, 5), end_date=date(2024, 9, 30))
    batch2 = Batch(name="LC DS Weekend Batch", course_id=ca.id,
                   faculty_id=fac.id, schedule_text="Weekend",
                   start_date=date(2024, 8, 3), end_date=date(2024, 10, 26))
    batchb = Batch(name="LC B Other Batch", course_id=cb.id,
                   faculty_id=fac2.id, schedule_text="Evening",
                   start_date=date(2024, 7, 6), end_date=date(2024, 9, 28))
    db.session.add_all([batch1, batch2, batchb])
    db.session.flush()
    db.session.add(BatchMember(batch_id=batch1.id, user_id=stu1.id))
    db.session.add(BatchMember(batch_id=batch1.id, user_id=stu3.id))
    db.session.add(BatchMember(batch_id=batch2.id, user_id=stu3.id))

    now = datetime.utcnow()

    def sess(course, title, delta, room):
        s = LiveSession(course_id=course.id, title=title,
                        starts_at=now + delta, duration_min=60,
                        room_name=room, created_by=fac.id)
        db.session.add(s)
        db.session.flush()
        return s

    s_old = sess(ca, "Old Class", timedelta(days=-2), "lc-room-old")
    s_new = sess(ca, "New Class", timedelta(days=-1), "lc-room-new")
    s_b = sess(cb, "B Class", timedelta(days=-1), "lc-room-b")
    s_soon = sess(ca, "Soon Class", timedelta(minutes=5), "lc-room-soon")
    s_later = sess(ca, "Later Class", timedelta(days=1), "lc-room-later")
    s_future = sess(ca, "Future Class", timedelta(days=2), "lc-room-future")
    db.session.flush()

    rec1 = Recording(course_id=ca.id, title="Old Class Recording",
                     video_url="https://example.com/v.mp4",
                     duration_min=55, recorded_on=date(2024, 7, 3),
                     live_session_id=s_old.id)
    recb = Recording(course_id=cb.id, title="B Recording",
                     video_url="https://example.com/vb.mp4",
                     live_session_id=s_b.id)
    db.session.add_all([rec1, recb])
    db.session.commit()

    S_OLD_ID, S_NEW_ID = s_old.id, s_new.id


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


anon = app.test_client()

# ================================================== 1. auth
r = anon.get("/calendar")
check("anonymous /calendar -> redirect", r.status_code in (301, 302, 303),
      f"status={r.status_code}")

stu_c, code = login_as("lcstu1@example.com", "pw-lc-stu1")
check("student login ok", code in (301, 302, 303), f"status={code}")
r = stu_c.get("/calendar")
check("/calendar 200 for student", r.status_code == 200,
      f"status={r.status_code}")
html = r.get_data(as_text=True)

# ================================================== 2. no calendar markup
check("no calendar grid", 'id="grid"' not in html)
check("no month title element", 'id="mtitle"' not in html)
check("no day-list element", 'id="daylist"' not in html)

# ================================================== 3. tabs present
check("Upcoming tab", 'data-tab="upcoming"' in html)
check("Recorded Sessions tab", 'data-tab="recorded"' in html)
check("Course Materials tab", 'data-tab="materials"' in html)
check("hash deep-link JS", "location.hash" in html)

# ================================================== 4. batch card, no faculty info
check("batch card rendered", "LC DS Weekday Batch" in html)
check("batch schedule shown", "Weekday" in html)
check("faculty name never rendered", "LC Faculty Person" not in html)

# ================================================== 5. chips + watch links
check("'Faculty joined' chip", "Faculty joined" in html)
check("'Faculty didn't join' chip", "Faculty didn't join" in html)
n_watch = html.count("/rec/")
check("exactly one signed Watch link (only recorded session)",
      n_watch == 1, f"count={n_watch}")
check("no student-attendance chip text",
      "You joined" not in html and "You missed" not in html)

# ================================================== 6. newest-first within batch
i_new = html.find("New Class")
i_old = html.find("Old Class")
check("date-wise newest-first", 0 <= i_new < i_old,
      f"i_new={i_new} i_old={i_old}")

# ================================================== 7. enrollment scoping
check("other course invisible", "LC Course B" not in html)
check("other course session invisible", "B Class" not in html)

# ================================================== 8. upcoming list
for t in ("Soon Class", "Later Class", "Future Class"):
    check(f"upcoming shows {t}", t in html)
i_soon, i_later, i_future = (html.find("Soon Class"),
                             html.find("Later Class"),
                             html.find("Future Class"))
check("upcoming soonest-first",
      0 <= i_soon < i_later < i_future,
      f"{i_soon} {i_later} {i_future}")
check("past classes not in upcoming tab",
      html.find("Old Class") > html.find('id="tab-recorded"'),
      "Old Class must only appear in the recorded tab")
# joinable session -> live Join link; future session -> disabled button
check("joinable session has Join link",
      f"/live/join/" in html)
check("non-joinable session has disabled Join",
      "disabled" in html and "Join opens 15 minutes" in html)

# ================================================== 9. admin sees all batches
adm_c, _ = login_as("lcadm@example.com", "pw-lc-adm")
ahtml = adm_c.get("/calendar").get_data(as_text=True)
check("admin sees batch card", "LC DS Weekday Batch" in ahtml)
check("admin sees second batch", "LC DS Weekend Batch" in ahtml)
check("admin sees other course", "LC Course B" in ahtml)
check("admin: course with no batch gets fallback card",
      "(no batches)" in ahtml or "LC B Other Batch" in ahtml)

# ================================================== 10. real calendar dates, NO Day-N
# rows render like "Mon, 8 Sep 2026" (weekday bold + "D Mon YYYY" small)
date_pat = re.compile(
    r"<b>(Mon|Tue|Wed|Thu|Fri|Sat|Sun)</b>"
    r"<small>\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r" 20\d{2}</small>")
check("real calendar date rendered per row", date_pat.search(html) is not None,
      date_pat.search(html).group(0) if date_pat.search(html) else "")
check("no Day-N labels anywhere",
      re.search(r"\bDay \d+", html) is None)
check("no day-n css hook", 'class="day-n"' not in html and
      "day-n" not in html)

# ================================================== 11. batch-level scoping
# (a) stu1 in Batch A only -> does NOT see Batch B (same course)
check("(a) enrolled batch visible", "LC DS Weekday Batch" in html)
check("(a) other batch of same course hidden", "LC DS Weekend Batch" not in html)
# (b) stu3 in two batches -> sees exactly those two cards
s3_c, _ = login_as("lcstu3@example.com", "pw-lc-stu3")
h3 = s3_c.get("/calendar").get_data(as_text=True)
check("(b) first enrolled batch visible", "LC DS Weekday Batch" in h3)
check("(b) second enrolled batch visible", "LC DS Weekend Batch" in h3)
check("(b) other course batch hidden", "LC B Other Batch" not in h3)
n_cards = len(re.findall(r'class="card batch-card"', h3))
check("(b) exactly two batch cards", n_cards == 2, f"cards={n_cards}")
# (c) stu4 enrolled in course but in NO batch -> empty state
s4_c, _ = login_as("lcstu4@example.com", "pw-lc-stu4")
h4 = s4_c.get("/calendar").get_data(as_text=True)
check("(c) no batch cards", 'class="card batch-card"' not in h4)
check("(c) empty state shown",
      "No recorded sessions yet" in h4)
check("(c) no other-course leakage", "LC Course B" not in h4)
# (d) faculty sees only their own batches
f_c, _ = login_as("lcfac@example.com", "pw-lc-fac")
hf = f_c.get("/calendar").get_data(as_text=True)
check("(d) faculty sees own batch 1", "LC DS Weekday Batch" in hf)
check("(d) faculty sees own batch 2", "LC DS Weekend Batch" in hf)
check("(d) faculty does not see other faculty's batch",
      "LC B Other Batch" not in hf)
check("(d) no other-faculty name leaked", "LC Other Faculty" not in hf)

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
