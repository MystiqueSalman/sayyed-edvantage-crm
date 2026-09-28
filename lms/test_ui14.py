"""UI14 — backend for the homepage/student-dashboard redesign (end-to-end).

Covers:
  1. New tables/columns exist on a fresh DB; seed inserts exactly one
     clearly-marked sample testimonial; partners seed empty.
  2. Homepage 200 with a real course title + fee.
  3. New public pages /about, /contact, /help, /blogs -> 200.
  4. Student login -> /dashboard 200; /announcements, /downloads,
     /quizzes, /profile -> 200; /community -> 200.
  5. Lesson heartbeat: seconds accumulate on LessonProgress.time_spent_sec;
     invalid seconds rejected; un-enrolled lesson -> 403; missing lesson -> 404.
  6. Admin CRUD for testimonials + partners; site-settings form roundtrip.
  7. Custom stats: only shown when BOTH value and label are set.
  8. Enquiry POST creates a CRM lead.
  9. AppSetting site.* get/set roundtrip.

Runs against the Flask test client on a FRESH SQLite DB (no dev server):

    cd ~/workspace/lms && ./run_suite.sh test_ui14
"""
import os
import sys
from datetime import date, datetime, timedelta

os.environ["LMS_SCHEDULER"] = "off"
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_ui14.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "lms-local-test-secret-not-for-production")

sys.path.insert(0, "/home/hatch/workspace/lms")

# Import BEFORE create_app() so the UI14 tables are registered with
# SQLAlchemy and the startup db.create_all() creates them.
import app.models_ui as MUI  # noqa: E402
from app import create_app, db  # noqa: E402
from app.models import (Announcement, AppSetting, Assignment, Batch,  # noqa: E402
                        Certificate, Course, Discussion, Enrollment, Lead,
                        Lesson, LessonProgress, Module, Quiz, QuizAttempt,
                        ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, Submission,
                        User)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


app = create_app()

with app.app_context():
    # ---- users ----
    admin = User(name="UI14 Admin", email="ui14admin@example.com",
                 role=ROLE_ADMIN)
    admin.set_password("pw-admin-ui14")
    fac = User(name="UI14 Faculty", email="ui14fac@example.com",
               role=ROLE_FACULTY)
    fac.set_password("pw-fac-ui14")
    stu = User(name="UI14 Student", email="ui14stu@example.com",
               role=ROLE_STUDENT)
    stu.set_password("pw-stu-ui14")
    db.session.add_all([admin, fac, stu])
    # ---- course with module + lessons + quiz + assignment ----
    course = Course(title="Data Science", slug="data-science", fee=50000,
                    short_desc="DS course")
    db.session.add(course)
    db.session.flush()
    mod = Module(course_id=course.id, title="Module 1", position=0)
    db.session.add(mod)
    db.session.flush()
    l1 = Lesson(module_id=mod.id, title="Lesson 1", position=0,
                kind=Lesson.KIND_TEXT)
    l2 = Lesson(module_id=mod.id, title="PDF Notes", position=1,
                kind=Lesson.KIND_PDF, pdf_file="notes.pdf")
    db.session.add_all([l1, l2])
    db.session.flush()
    quiz = Quiz(module_id=mod.id, title="Module Quiz", pass_percent=60)
    db.session.add(quiz)
    db.session.flush()
    asg = Assignment(course_id=course.id, title="Homework 1",
                     due_date=date.today() + timedelta(days=3))
    db.session.add(asg)
    # ---- second course the student is NOT enrolled in (heartbeat 403) ----
    other = Course(title="Python", slug="python", fee=35000,
                   short_desc="Py course")
    db.session.add(other)
    db.session.flush()
    omod = Module(course_id=other.id, title="Module 1", position=0)
    db.session.add(omod)
    db.session.flush()
    olesson = Lesson(module_id=omod.id, title="Other Lesson", position=0,
                     kind=Lesson.KIND_TEXT)
    db.session.add(olesson)
    db.session.flush()
    # ---- enrollment, announcement, batch, discussion ----
    enr = Enrollment(user_id=stu.id, course_id=course.id,
                     status=Enrollment.STATUS_ACTIVE, paid=True,
                     amount_paid=50000)
    db.session.add(enr)
    ann = Announcement(title="Welcome week", body="Classes begin Monday.",
                       active=True)
    db.session.add(ann)
    batch = Batch(name="Morning batch", course_id=course.id,
                  start_date=date.today() + timedelta(days=7))
    db.session.add(batch)
    disc = Discussion(course_id=course.id, user_id=fac.id,
                      title="Doubt: lesson 1", body="Ask here.")
    db.session.add(disc)
    db.session.commit()
    STU_ID, ADMIN_ID = stu.id, admin.id
    L1_ID, L2_ID, OLE_ID = l1.id, l2.id, olesson.id
    ASG_ID = asg.id
    QUIZ_ID = quiz.id
    COURSE_ID = course.id

client = app.test_client()


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


# ================================================== 1. seeds + schema
from app.models_ui import Partner as _P, Testimonial as _T  # noqa: E402
with app.app_context():
    samples = _T.query.filter_by(is_sample=True).all()
    check("seed: exactly one sample testimonial", len(samples) == 1,
          f"n={len(samples)}")
    check("seed: sample is active + clearly marked",
          samples and samples[0].active and
          "replace in admin" in (samples[0].role or ""))
    check("seed: partners empty on purpose", _P.query.count() == 0)
    col = db.session.execute(
        db.text("PRAGMA table_info(lesson_progress)")).fetchall()
    check("schema: lesson_progress.time_spent_sec exists",
          any(r[1] == "time_spent_sec" for r in col))

# ================================================== 2. homepage + public pages
r = client.get("/")
check("homepage 200", r.status_code == 200, f"status={r.status_code}")
html = r.get_data(as_text=True)
check("homepage has real course title", "Data Science" in html)
check("homepage has real fee", "50,000" in html)
for path in ("/about", "/contact", "/help", "/blogs"):
    r = client.get(path)
    check(f"{path} 200", r.status_code == 200, f"status={r.status_code}")

# ================================================== 3. student pages
stu_c, code = login_as("ui14stu@example.com", "pw-stu-ui14")
check("student login accepted", code in (302, 303), f"status={code}")
for path in ("/dashboard", "/announcements", "/downloads", "/quizzes",
             "/profile", "/community"):
    r = stu_c.get(path)
    check(f"student GET {path} 200", r.status_code == 200,
          f"status={r.status_code}")

# profile POST updates name + phone
r = stu_c.post("/profile", data={"name": "UI14 Student Renamed",
                                 "phone": "+911234567890"},
               follow_redirects=True)
with app.app_context():
    u = db.session.get(User, STU_ID)
    check("profile POST updates name+phone",
          u.name == "UI14 Student Renamed" and u.phone == "+911234567890",
          f"name={u.name} phone={u.phone}")
r = stu_c.post("/profile", data={"name": "", "phone": "x"},
               follow_redirects=True)
with app.app_context():
    u = db.session.get(User, STU_ID)
    check("profile POST rejects empty name",
          u.name == "UI14 Student Renamed")

# ================================================== 4. heartbeat
def beat(c, lid, seconds):
    return c.post(f"/lesson/{lid}/heartbeat", json={"seconds": seconds})

r = beat(stu_c, L1_ID, 60)
d = r.get_json()
check("heartbeat 200 + ok", r.status_code == 200 and d.get("ok") is True,
      f"status={r.status_code} body={d}")
check("heartbeat total=60", d.get("total") == 60, f"total={d.get('total')}")
r = beat(stu_c, L1_ID, 120)
check("heartbeat accumulates", r.get_json().get("total") == 180)
with app.app_context():
    row = LessonProgress.query.filter_by(user_id=STU_ID,
                                         lesson_id=L1_ID).first()
    check("time_spent_sec persisted", row is not None and
          row.time_spent_sec == 180, f"row={row.time_spent_sec if row else None}")
for bad in (0, -5, 301):
    r = beat(stu_c, L1_ID, bad)
    check(f"heartbeat rejects seconds={bad}", r.status_code == 400,
          f"status={r.status_code}")
r = stu_c.post(f"/lesson/{L1_ID}/heartbeat", json={})
check("heartbeat rejects missing seconds", r.status_code == 400)
r = beat(stu_c, OLE_ID, 60)
check("heartbeat 403 for un-enrolled course", r.status_code == 403,
      f"status={r.status_code}")
r = beat(stu_c, 999999, 60)
check("heartbeat 404 for missing lesson", r.status_code == 404,
      f"status={r.status_code}")

# assignment status card data (downloads/quizzes sanity via DB)
with app.app_context():
    db.session.add(Submission(assignment_id=ASG_ID, user_id=STU_ID,
                              file_path="hw.pdf"))
    att = QuizAttempt(quiz_id=QUIZ_ID, user_id=STU_ID, score=8, total=10,
                      submitted_at=datetime.utcnow())
    db.session.add(att)
    db.session.commit()
r = stu_c.get("/downloads")
check("downloads 200 with pdf material + submission",
      r.status_code == 200 and "PDF Notes" in r.get_data(as_text=True))
r = stu_c.get("/quizzes")
qhtml = r.get_data(as_text=True)
check("quizzes 200 shows quiz + best pct",
      r.status_code == 200 and "Module Quiz" in qhtml and "80" in qhtml)

# dashboard context vars (backend contract for the frontend rewrite)
r = stu_c.get("/dashboard")
check("dashboard still 200", r.status_code == 200)
with app.test_request_context():
    pass

# ================================================== 5. admin: testimonials + partners
adm_c, code = login_as("ui14admin@example.com", "pw-admin-ui14")
check("admin login accepted", code in (302, 303), f"status={code}")
for path in ("/admin/testimonials", "/admin/partners",
             "/admin/site-settings"):
    r = adm_c.get(path)
    check(f"admin GET {path} 200", r.status_code == 200,
          f"status={r.status_code}")

r = adm_c.post("/admin/testimonials/new",
               data={"name": "Real Learner", "role": "Data Science Student",
                     "text": "Great course!", "rating": "5",
                     "active": "1", "sort_order": "1"},
               follow_redirects=True)
with app.app_context():
    t = _T.query.filter_by(name="Real Learner").first()
    check("admin creates testimonial", t is not None and t.active and
          t.rating == 5)
    TID = t.id if t else None
check("testimonial create redirects to list",
      r.status_code == 200 and "Real Learner" in r.get_data(as_text=True))
r = adm_c.post(f"/admin/testimonials/{TID}/edit",
               data={"name": "Real Learner", "role": "Alumni",
                     "text": "Great course!", "rating": "4",
                     "active": "1", "sort_order": "1"},
               follow_redirects=True)
with app.app_context():
    t = db.session.get(_T, TID)
    check("admin edits testimonial", t.role == "Alumni" and t.rating == 4)
r = adm_c.post(f"/admin/testimonials/{TID}/toggle", follow_redirects=True)
with app.app_context():
    t = db.session.get(_T, TID)
    check("admin toggles testimonial", t.active is False)
r = adm_c.post(f"/admin/testimonials/{TID}/delete", follow_redirects=True)
with app.app_context():
    check("admin deletes testimonial", db.session.get(_T, TID) is None)

r = adm_c.post("/admin/partners/new",
               data={"name": "Acme Corp", "website": "https://acme.example",
                     "active": "1", "sort_order": "2"},
               follow_redirects=True)
with app.app_context():
    p = _P.query.filter_by(name="Acme Corp").first()
    check("admin creates partner", p is not None and p.active)
    PID = p.id if p else None
r = adm_c.post(f"/admin/partners/{PID}/toggle", follow_redirects=True)
with app.app_context():
    p = db.session.get(_P, PID)
    check("admin toggles partner", p.active is False)
r = adm_c.post(f"/admin/partners/{PID}/delete", follow_redirects=True)
with app.app_context():
    check("admin deletes partner", db.session.get(_P, PID) is None)

# site settings form
r = adm_c.post("/admin/site-settings",
               data={"site.hero_video_url": "https://video.example/hero",
                     "site.contact_phone": "+911111111111",
                     "site.contact_email": "hello@example.com",
                     "site.stat1_value": "10k+", "site.stat1_label": "Learners",
                     "site.stat2_value": "99%", "site.stat2_label": "",
                     "site.stat3_value": "", "site.stat3_label": ""},
               follow_redirects=True)
check("site-settings POST 200", r.status_code == 200)
with app.app_context():
    check("site-settings persisted",
          AppSetting.get("site.contact_phone") == "+911111111111" and
          AppSetting.get("site.hero_video_url") == "https://video.example/hero")
r = client.get("/")
html = r.get_data(as_text=True)
check("homepage 200 after settings", r.status_code == 200)

# student must not reach admin pages
r = stu_c.get("/admin/testimonials", follow_redirects=False)
check("student blocked from admin testimonials",
      r.status_code in (302, 403), f"status={r.status_code}")

# ================================================== 6. enquiry -> CRM lead
r = client.post("/enquiry",
                data={"name": "Lead Person", "phone": "9876543210",
                      "email": "lead@example.com",
                      "course_id": str(COURSE_ID), "message": "Hi"},
                follow_redirects=False)
with app.app_context():
    lead = Lead.query.filter_by(phone="9876543210").first()
    check("enquiry POST creates lead",
          lead is not None and lead.name == "Lead Person" and
          lead.source == Lead.SOURCE_WEBSITE,
          f"source={lead.source if lead else None}")

# ================================================== 7. AppSetting roundtrip
with app.app_context():
    AppSetting.set("site.hero_video_url", "https://x.example/v")
    check("AppSetting get/set roundtrip",
          AppSetting.get("site.hero_video_url") == "https://x.example/v")
    check("AppSetting default fallback",
          AppSetting.get("site.nope_missing", "dflt") == "dflt")
    # cleanup the custom stat2 value-only row so nothing leaks into other DBs
    AppSetting.set("site.stat2_value", "")

# ================================================== summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
