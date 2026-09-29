"""Live Classes page rework (2026-09-29): calendar removed, batch list,
tab bar removed (hash-routed single section), Join -> session detail page.

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
  7. Upcoming section: enrolled-course cards (students) / instructed
     courses (faculty) / all (admin); each card shows ONLY course name,
     faculty, batch period, batch type (no module list on the card);
     clicking a card opens date-wise sessions soonest-first with the
     topic per date; Join link only when is_joinable.
  8. Hash section-router JS present (no tab bar): one section visible at a
     a time via #upcoming (default) / #recorded / #materials.
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
    stu5 = User(name="LC Student Five", email="lcstu5@example.com",
                role=ROLE_STUDENT)
    stu5.set_password("pw-lc-stu5")
    fac2 = User(name="LC Other Faculty", email="lcotherfac@example.com",
                role=ROLE_FACULTY)
    fac2.set_password("pw-lc-fac2")
    adm = User(name="LC Admin", email="lcadm@example.com", role=ROLE_ADMIN)
    adm.set_password("pw-lc-adm")
    db.session.add_all([fac, fac2, stu1, stu2, stu3, stu4, stu5, adm])
    db.session.flush()

    ca = Course(title="LC Course A", slug="lc-course-a", fee=50000,
                instructor_id=fac.id)
    cb = Course(title="LC Course B", slug="lc-course-b", fee=60000,
                instructor_id=fac2.id)
    cc = Course(title="LC Course C", slug="lc-course-c", fee=70000,
                instructor_id=fac.id)
    db.session.add_all([ca, cb, cc])
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
    # stu5 is enrolled in THREE courses -> sees three course cards
    for cid in (ca.id, cb.id, cc.id):
        db.session.add(Enrollment(user_id=stu5.id, course_id=cid,
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
    s_nourl = sess(ca, "No URL Class", timedelta(days=3), "   ")
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

    S_OLD_ID, S_NEW_ID, S_SOON_ID, S_LATER_ID, S_NOURL_ID = (
        s_old.id, s_new.id, s_soon.id, s_later.id, s_nourl.id)
    # plain values for later assertions (ORM instances detach after commit)
    SE_STARTS = sorted(s.starts_at for s in
                       (s_old, s_new, s_soon, s_later, s_future, s_nourl))
    SE_SOON_START = s_soon.starts_at
    # stu1 is a member of batch1 only -> only batch1's dates render
    SE_BATCH_DATES = [d for d in (batch1.start_date, batch1.end_date) if d]


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

# ================================================== 3. NO tab bar — sections stand alone
check("no tab-bar markup", 'rs-tabs' not in html)
check("no tab buttons", 'data-tab=' not in html and 'role="tablist"' not in html)
check("no tab-switch JS hooks", 'switchTab' not in html)
check("upcoming section present", 'id="sec-upcoming"' in html)
check("recorded section present", 'id="sec-recorded"' in html)
check("materials section present", 'id="sec-materials"' in html)
check("hash section-router JS",
      "location.hash" in html and "showSection" in html)

# ================================================== 4. batch card, no faculty info
check("batch card rendered", "LC DS Weekday Batch" in html)
check("batch schedule shown", "Weekday" in html)
# (recorded batch cards must never show faculty name/location; the
# Upcoming course cards DO show the faculty name per the card spec)
rec_sec = html.split('id="sec-recorded"')[1].split('id="sec-materials"')[0]
check("recorded: faculty name never rendered",
      "LC Faculty Person" not in rec_sec)

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

# ================================================== 8. upcoming: course cards
# (a) student enrolled in course A only -> only the course A card
check("(a) enrolled course card shown", "LC Course A" in html)
check("(a) unenrolled course B hidden", "LC Course B" not in html)
check("(a) unenrolled course C hidden", "LC Course C" not in html)
n_ccards = len(re.findall(r'class="card course-card"', html))
check("(a) exactly one course card", n_ccards == 1, f"cards={n_ccards}")
# card shows: course → batch type → faculty → period → timing (no module list)
check("card: course name", "LC Course A" in html)
check("card: faculty name", "LC Faculty Person" in html)
all_a = SE_STARTS
lo, hi = all_a[0], all_a[-1]
exp_per = (f"{lo.day} {lo.strftime('%B %Y')}" if lo.date() == hi.date()
           else f"{lo.day} {lo.strftime('%B')} to "
                f"{hi.day} {hi.strftime('%B')}")
check("card: batch period, full month", exp_per in html, exp_per)
up_sec = html.split('id="sec-recorded"')[0]
check("card: batch type label", "Weekday Batch" in up_sec)
check("card: no module list on card header",
      html.find("Soon Class") > html.find('class="body sess-list"'),
      "session topics appear only inside the date-wise view")
# (b) student enrolled in 3 courses -> exactly three cards
s5_c, _ = login_as("lcstu5@example.com", "pw-lc-stu5")
h5 = s5_c.get("/calendar").get_data(as_text=True)
for t in ("LC Course A", "LC Course B", "LC Course C"):
    check(f"(b) sees {t} card", t in h5)
n5 = len(re.findall(r'class="card course-card"', h5))
check("(b) exactly three course cards", n5 == 3, f"cards={n5}")
# (c) clicking a course opens date-wise sessions: topic per date, soonest first
i_soon, i_later, i_future = (html.find("Soon Class"),
                             html.find("Later Class"),
                             html.find("Future Class"))
check("(c) date-wise sessions listed",
      all(i >= 0 for i in (i_soon, i_later, i_future)))
check("(c) sessions soonest-first",
      0 <= i_soon < i_later < i_future,
      f"{i_soon} {i_later} {i_future}")
check("(c) real date per upcoming row, full month",
      re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{1,2} "
                r"(January|February|March|April|May|June|July|August|"
                r"September|October|November|December) 20\d{2}",
                html) is not None)
# (d) past classes not in upcoming section
check("(d) past classes not in upcoming section",
      html.find("Old Class") > html.find('id="sec-recorded"'),
      "Old Class must only appear in the recorded section")
# joinable session -> Join button linking to the session detail page;
# future session -> disabled button
check("joinable session has Join link to session page",
      f"/live-session/{S_SOON_ID}" in html)
check("no direct join links on calendar page",
      "/live/join/" not in html)
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
# rows render like "Mon, 8 September 2026" (weekday bold + "D Month YYYY" small)
date_pat = re.compile(
    r"<b>(Mon|Tue|Wed|Thu|Fri|Sat|Sun)</b>"
    r"<small>\d{1,2} (January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
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

# ================================================== 12. dashboard "View All →" links
d_c, _ = login_as("lcstu1@example.com", "pw-lc-stu1")
dr = d_c.get("/dashboard")
dhtml = dr.get_data(as_text=True)
check("dashboard renders", dr.status_code == 200,
      f"status={dr.status_code}")
check("View All: upcoming link", '/calendar#upcoming' in dhtml)
check("View All: recorded link", '/calendar#recorded' in dhtml)
check("View All: materials link", '/calendar#materials' in dhtml)
check("View All: upcoming panel heading",
      "Upcoming Live Classes" in dhtml)
check("View All: recorded panel heading",
      "Recorded Sessions" in dhtml)
check("View All: materials panel heading",
      "Course Materials" in dhtml)

# ================================================== 13. session detail page (new Join flow)
# (a) Join button links to the session page
check("(a) Join links to session page",
      f"/live-session/{S_SOON_ID}" in html)
check("(a) no direct join links on calendar page",
      "/live/join/" not in html)
# (b) session page renders date/topic/time + Connect button
p = stu_c.get(f"/live-session/{S_SOON_ID}")
phtml = p.get_data(as_text=True)
check("(b) session page 200", p.status_code == 200,
      f"status={p.status_code}")
check("(b) real date shown, full month",
      re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{1,2} "
                r"(January|February|March|April|May|June|July|August|"
                r"September|October|November|December) 20\d{2}",
                phtml) is not None)
check("(b) topic shown", "Soon Class" in phtml)
check("(b) course shown", "LC Course A" in phtml)
check("(b) faculty shown", "LC Faculty Person" in phtml)
check("(b) Connect button", "Connect to Live Class" in phtml)
check("(b) Connect goes through live_join",
      f"/live/join/{S_SOON_ID}" in phtml)
# (c) no meeting URL -> graceful note, no Connect button
pn = stu_c.get(f"/live-session/{S_NOURL_ID}")
nhtml = pn.get_data(as_text=True)
check("(c) no-URL page 200", pn.status_code == 200,
      f"status={pn.status_code}")
check("(c) graceful note",
      "The class link will appear here" in nhtml)
check("(c) no Connect button",
      "Connect to Live Class" not in nhtml)
# (d) unenrolled student blocked; admin can view
s2_c, _ = login_as("lcstu2@example.com", "pw-lc-stu2")
rb = s2_c.get(f"/live-session/{S_SOON_ID}")
check("(d) unenrolled student blocked", rb.status_code == 403,
      f"status={rb.status_code}")
pa = adm_c.get(f"/live-session/{S_SOON_ID}")
check("(d) admin can view", pa.status_code == 200,
      f"status={pa.status_code}")
# (e) Join disabled outside the join window; session page shows Scheduled
check("(e) non-joinable Join disabled on list",
      "disabled" in html and "Join opens 15 minutes" in html)
pl = stu_c.get(f"/live-session/{S_LATER_ID}")
lhtml = pl.get_data(as_text=True)
check("(e) session page 200 (future class)", pl.status_code == 200)
check("(e) Scheduled note before join window",
      "Scheduled" in lhtml)
check("(e) no Connect button before join window",
      "Connect to Live Class" not in lhtml)

# ================================================== 11. course card strip:
# five items, left → right, separated by → arrows
strip = html.split('class="card course-card"')[1].split("</summary>")[0]
check("strip: four arrow separators", strip.count("→") == 4,
      f"arrows={strip.count('→')}")
i_course, i_type = strip.find("LC Course A"), strip.find("Weekday Batch")
i_fac, i_per = strip.find("LC Faculty Person"), strip.find(exp_per)
m_time = re.search(r"\d{1,2}(:\d{2})? (?:AM|PM) – \d{1,2}(:\d{2})? (?:AM|PM)",
                  strip)
check("strip: all five items present",
      all(i >= 0 for i in (i_course, i_type, i_fac, i_per))
      and m_time is not None,
      m_time.group(0) if m_time else "no timing")
check("strip: order course → type → faculty → period → timing",
      0 <= i_course < i_type < i_fac < i_per < (m_time.start() if m_time else -1))
check("strip: no module list on card", "Soon Class" not in strip)

# ================================================== 12. full month names everywhere;
# no abbreviated months on the Live Classes page
months = {(d.strftime("%B"), d.strftime("%b")) for d in SE_STARTS}
# batch card smalls render batch start/end dates too (full months)
for d in SE_BATCH_DATES:
    months.add((d.strftime("%B"), d.strftime("%b")))
cal_html = html  # full /calendar page (upcoming + recorded sections)
for full_m, abbr_m in sorted(months):
    check(f"month: full '{full_m}' shown", full_m in cal_html)
    if full_m != abbr_m:  # e.g. May == May, skip
        check(f"month: abbreviated '{abbr_m}' not shown",
              f" {abbr_m} " not in cal_html and f" {abbr_m}," not in cal_html)
d_full, d_abbr = SE_SOON_START.strftime("%B"), SE_SOON_START.strftime("%b")
check("detail: full month shown", d_full in phtml)
if d_full != d_abbr:
    check("detail: no abbreviated month",
          f" {d_abbr} " not in phtml and f" {d_abbr}," not in phtml)

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
