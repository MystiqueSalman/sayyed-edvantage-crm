"""End-to-end verification of the Sayyed EdVantage LMS (Phase 1)."""
import io
import sys

sys.path.insert(0, "/home/hatch/workspace/lms")
import requests
from app import create_app, db
from app.models import (Course, Lesson, Quiz, Question, Assignment, Submission,
                        Certificate, Enrollment, User)

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
    lesson_ids = [l.id for l in ds.lessons]
    quizzes = ds.quizzes
    answers = {}
    for qz in quizzes:
        for qu in qz.questions:
            answers[f"q{qu.id}"] = qu.correct
    assign = Assignment.query.filter_by(course_id=ds.id).first()
    devops = Course.query.filter_by(slug="devops").first()  # not faculty-assigned
    py_course = Course.query.filter_by(slug="python-programming").first()

# ---------------- 1. logins for all 4 roles ----------------
s_admin, s_mgr, s_fac, s_stu = (requests.Session() for _ in range(4))
check("admin login", login(s_admin, "admin@sayyed.in", "admin123"))
check("manager login", login(s_mgr, "manager@sayyed.in", "manager123"))
check("faculty login", login(s_fac, "faculty@sayyed.in", "faculty123"))
check("student login", login(s_stu, "student@sayyed.in", "student123"))
check("wrong password rejected",
      not login(requests.Session(), "student@sayyed.in", "nope"))

# ---------------- 2. role gates ----------------
r = s_mgr.get(f"{BASE}/admin/users")
check("manager blocked from user management (403)", r.status_code == 403)
r = s_fac.get(f"{BASE}/manage/course/{devops.id}")
check("faculty blocked from unassigned course (403)", r.status_code == 403)
r = s_fac.get(f"{BASE}/manage/course/{py_course.id}")
check("faculty can manage assigned course", r.status_code == 200)
r = s_stu.get(f"{BASE}/admin/")
check("student blocked from admin (403)", r.status_code == 403)

# ---------------- 3. student enroll with coupon (stub payment) ----------------
r = s_stu.post(f"{BASE}/enroll/data-science",
               data={"coupon_code": "WELCOME10", "confirm": "1"},
               allow_redirects=False)
check("enroll POST -> checkout redirect",
      r.status_code == 302 and "/checkout/" in r.headers.get("Location", ""),
      r.headers.get("Location", ""))
enr_id = r.headers["Location"].rstrip("/").split("/")[-1]
r = s_stu.get(f"{BASE}/checkout/{enr_id}")
check("checkout page renders (stub order)", r.status_code == 200 and "order_stub_" in r.text)
r = s_stu.post(f"{BASE}/payment/confirm/{enr_id}", allow_redirects=False)
check("stub payment confirms -> dashboard",
      r.status_code == 302 and "/dashboard" in r.headers.get("Location", ""))
with app.app_context():
    enr = Enrollment.query.get(int(enr_id))
    check("enrollment active + coupon applied",
          enr.status == "active" and enr.paid and enr.coupon_code == "WELCOME10"
          and enr.amount_paid == 45000, f"paid={enr.amount_paid}")

# invalid coupon
r = s_stu.post(f"{BASE}/enroll/devops", data={"coupon_code": "BOGUS"},
               allow_redirects=True)
check("invalid coupon warned", "invalid or expired" in r.text.lower())

# ---------------- 4. lessons -> quizzes -> certificate ----------------
# Phase 2: lessons 2+ are drip-locked (7/14 days). Backdate the enrollment so
# the original "complete everything" flow still exercises the full path.
from datetime import datetime as _dt, timedelta as _td
with app.app_context():
    _enr = Enrollment.query.get(int(enr_id))
    _enr.enrolled_at = _dt.utcnow() - _td(days=30)
    db.session.commit()
for lid in lesson_ids:
    r = s_stu.post(f"{BASE}/lesson/{lid}/complete", allow_redirects=False)
    assert r.status_code == 302, f"lesson {lid} complete failed: {r.status_code}"
check("all lessons marked complete", True, f"{len(lesson_ids)} lessons")

for qz in quizzes:
    r = s_stu.post(f"{BASE}/quiz/{qz.id}", data=answers, allow_redirects=False)
    assert r.status_code == 302, f"quiz {qz.id} failed: {r.status_code}"
check("all quizzes attempted with correct answers", True, f"{len(quizzes)} quizzes")

with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    cert = Certificate.query.filter_by(user_id=stu.id, course_id=ds.id).first()
check("certificate auto-issued on completion", cert is not None,
      getattr(cert, "code", ""))
if cert:
    r = s_stu.get(f"{BASE}/certificate/{cert.code}/download")
    check("certificate PDF downloads",
          r.status_code == 200 and r.headers.get("Content-Type") == "application/pdf"
          and r.content[:5] == b"%PDF-", f"{len(r.content)} bytes")

# ---------------- 5. assignment submit + grade ----------------
fake_pdf = io.BytesIO(b"%PDF-1.4 fake assignment content")
r = s_stu.post(f"{BASE}/assignment/{assign.id}",
               files={"file": ("work.pdf", fake_pdf, "application/pdf")},
               data={"note": "My EDA report"},
               allow_redirects=True)
check("student submits assignment (file upload)", "Assignment submitted" in r.text)
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    sub = Submission.query.filter_by(assignment_id=assign.id, user_id=stu.id).first()
check("submission stored", sub is not None and bool(sub.file_path))

r = s_fac.get(f"{BASE}/manage/assignment/{assign.id}/submissions")
check("faculty sees submissions", r.status_code == 200 and "student@sayyed.in" in r.text)
r = s_fac.post(f"{BASE}/manage/submission/{sub.id}/grade",
               data={"grade": "85", "feedback": "Great insights, well structured."},
               allow_redirects=True)
check("faculty grades submission", "Submission graded" in r.text)
r = s_stu.get(f"{BASE}/assignment/{assign.id}")
check("student sees grade + feedback",
      "85" in r.text and "Great insights" in r.text)

# ---------------- 6. admin assignment CRUD ----------------
with app.app_context():
    n0 = Assignment.query.filter_by(course_id=ds.id).count()
r = s_admin.post(f"{BASE}/manage/course/{ds.id}/assignment/new",
                 data={"title": "CRUD Test Assignment", "description": "tmp",
                       "max_marks": "50", "due_date": ""},
                 allow_redirects=True)
with app.app_context():
    n1 = Assignment.query.filter_by(course_id=ds.id).count()
    tmp = Assignment.query.filter_by(title="CRUD Test Assignment").first()
check("admin creates assignment", n1 == n0 + 1)
r = s_admin.post(f"{BASE}/manage/assignment/{tmp.id}/edit",
                 data={"title": "CRUD Test Assignment v2", "description": "tmp",
                       "max_marks": "50", "due_date": ""},
                 allow_redirects=True)
with app.app_context():
    check("admin edits assignment",
          Assignment.query.get(tmp.id).title == "CRUD Test Assignment v2")
r = s_admin.post(f"{BASE}/manage/assignment/{tmp.id}/delete", allow_redirects=True)
with app.app_context():
    check("admin deletes assignment",
          Assignment.query.get(tmp.id) is None)

# manager can also manage assignments (content), but not coupons
r = s_mgr.post(f"{BASE}/manage/course/{ds.id}/assignment/new",
               data={"title": "Mgr Assignment", "description": "x",
                     "max_marks": "10", "due_date": ""},
               allow_redirects=True)
check("manager creates assignment (content perm)", "Assignment created" in r.text)
with app.app_context():
    mg = Assignment.query.filter_by(title="Mgr Assignment").first()
    db.session.delete(mg); db.session.commit()
r = s_mgr.get(f"{BASE}/admin/coupons")
check("manager blocked from coupons (403)", r.status_code == 403)

# ---------------- 7. bonus course free enroll ----------------
r = s_stu.post(f"{BASE}/enroll/git-github-essentials",
               data={"confirm": "1"}, allow_redirects=False)
check("bonus course enrolls free (no checkout)",
      r.status_code == 302 and "/dashboard" in r.headers.get("Location", ""))

# ---------------- 8. public pages ----------------
for path in ["/", "/courses", "/bonus-courses", "/course/data-science",
             "/course/data-science/recordings", "/login", "/register"]:
    r = requests.get(BASE + path)
    check(f"GET {path} -> 200", r.status_code == 200)

print()
failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
