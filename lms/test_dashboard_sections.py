"""Dashboard content sections: Upcoming Live Classes -> Recorded Sessions ->
Course Materials -> Announcements.

Covers:
  1. Sections render in the exact order: Upcoming -> Recorded Sessions ->
     Course Materials -> Announcements.
  2. Recorded Sessions grouped by course in catalog order (Data Science
     before AI & Generative AI), date-wise newest first within each course.
  3. Materials grouped the same way, newest first, with download links.
  4. Student enrolled in course A sees NO course B recordings/materials.
  5. Anonymous -> login redirect; faculty -> 403 (student_only dashboard).

Run: cd ~/workspace/lms && ./run_suite.sh test_dashboard_sections
"""
import os
import sys
from datetime import date

os.environ["LMS_SCHEDULER"] = "off"
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_dashboard_sections.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "lms-local-test-secret-not-for-production")

sys.path.insert(0, "/home/hatch/workspace/lms")

from app import create_app, db  # noqa: E402
from app.models import (Announcement, Course, CourseMaterial, Enrollment,  # noqa: E402
                        Recording, User, ROLE_FACULTY, ROLE_STUDENT)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name +
          (f" — {extra}" if extra else ""))


app = create_app()

with app.app_context():
    stu = User(name="DS Student", email="dsstu@example.com", role=ROLE_STUDENT)
    stu.set_password("pw-ds-stu")
    fac = User(name="DS Faculty", email="dsfac@example.com", role=ROLE_FACULTY)
    fac.set_password("pw-ds-fac")
    db.session.add_all([stu, fac])
    db.session.flush()

    ds = Course(title="Data Science", slug="data-science", fee=50000,
                short_desc="DS")
    ai = Course(title="AI & Generative AI", slug="ai-generative-ai", fee=70000,
                short_desc="AI")
    py = Course(title="Python Programming", slug="python-programming",
                fee=35000, short_desc="PY")
    db.session.add_all([ds, ai, py])
    db.session.flush()

    for c in (ds, ai):
        db.session.add(Enrollment(user_id=stu.id, course_id=c.id,
                                  status="active", paid=True))
    db.session.flush()

    recs = [
        Recording(course_id=ds.id, title="DS-OLD: EDA Basics",
                  video_url="https://www.youtube.com/embed/dsold1",
                  recorded_on=date(2026, 9, 20)),
        Recording(course_id=ds.id, title="DS-NEW: Regression Live",
                  video_url="https://www.youtube.com/embed/dsnew2",
                  recorded_on=date(2026, 9, 25)),
        Recording(course_id=ai.id, title="AI-MID: Prompt Workshop",
                  video_url="https://www.youtube.com/embed/aimid3",
                  recorded_on=date(2026, 9, 22)),
        Recording(course_id=py.id, title="PY-HIDDEN: Loops",
                  video_url="https://www.youtube.com/embed/pyhid4",
                  recorded_on=date(2026, 9, 26)),
    ]
    db.session.add_all(recs)
    mats = [
        CourseMaterial(course_id=ds.id, title="DS Cheatsheet",
                       file_path="mat_ds1.pdf", file_ext="pdf",
                       file_size=2048, uploaded_by=fac.id),
        CourseMaterial(course_id=ai.id, title="AI Prompt Pack",
                       file_path="mat_ai1.xlsx", file_ext="xlsx",
                       file_size=4096, uploaded_by=fac.id),
        CourseMaterial(course_id=py.id, title="PY-HIDDEN Notes",
                       file_path="mat_py1.pdf", file_ext="pdf",
                       file_size=1024, uploaded_by=fac.id),
    ]
    db.session.add_all(mats)
    db.session.add(Announcement(title="Welcome onboard", body="Hello",
                                active=True))
    db.session.commit()


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


# ================================================== 1. anonymous denied
anon = app.test_client()
r = anon.get("/dashboard", follow_redirects=False)
check("anonymous /dashboard redirects to login",
      r.status_code in (301, 302) and "/login" in r.headers.get("Location", ""),
      f"got {r.status_code}")

# ================================================== 2. faculty denied
fs, sc = login_as("dsfac@example.com", "pw-ds-fac")
check("faculty login ok", sc in (302, 303), f"got {sc}")
r = fs.get("/dashboard", follow_redirects=False)
check("faculty /dashboard -> 403 (student_only)", r.status_code == 403,
      f"got {r.status_code}")

# ================================================== 3. student dashboard
ss, sc = login_as("dsstu@example.com", "pw-ds-stu")
check("student login ok", sc in (302, 303), f"got {sc}")
r = ss.get("/dashboard")
html = r.get_data(as_text=True)
check("student /dashboard 200", r.status_code == 200, f"got {r.status_code}")

i_up = html.find("<h3>Upcoming Live Classes")
i_rec = html.find("🎬 Recorded Sessions")
i_mat = html.find("📚 Course Materials")
i_ann = html.find("<h3>Announcements")
check("all four sections present",
      all(i >= 0 for i in (i_up, i_rec, i_mat, i_ann)),
      f"idx={i_up},{i_rec},{i_mat},{i_ann}")
check("section order: Upcoming -> Recorded -> Materials -> Announcements",
      0 <= i_up < i_rec < i_mat < i_ann)

# ================================================== 4. grouping & ordering
i_ds = html.find("Data Science", i_rec)
i_ai = html.find("AI &amp; Generative AI", i_rec)
if i_ai < 0:
    i_ai = html.find("AI & Generative AI", i_rec)
check("catalog order: Data Science group before AI & Gen AI group",
      0 < i_ds < i_ai, f"ds={i_ds} ai={i_ai}")
i_new = html.find("DS-NEW: Regression Live")
i_old = html.find("DS-OLD: EDA Basics")
check("date-wise newest first within course", 0 < i_new < i_old,
      f"new={i_new} old={i_old}")
check("deep link #recorded present", "#recorded" in html)
check("deep link #materials present", "#materials" in html)
check("Watch button uses signed URL (no raw video_url)",
      "youtube.com/embed" not in html and "/rec/" in html)
check("material download links present", "/materials/" in html and
      "download" in html.lower())
check("material file-type icon present", "📊" in html or "📕" in html)

# ================================================== 5. no cross-course leakage
check("unenrolled course recording hidden",
      "PY-HIDDEN: Loops" not in html)
check("unenrolled course material hidden", "PY-HIDDEN Notes" not in html)
check("enrolled recording visible", "DS-NEW: Regression Live" in html)
check("enrolled material visible", "DS Cheatsheet" in html)
check("announcement still renders", "Welcome onboard" in html)

# ================================================== 6. /calendar hash tab JS
r = ss.get("/calendar")
cal = r.get_data(as_text=True)
check("/calendar renders", r.status_code == 200, f"got {r.status_code}")
check("hash deep-link JS present",
      "location.hash" in cal and "tabFromHash" in cal or
      "location.hash" in cal)

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
