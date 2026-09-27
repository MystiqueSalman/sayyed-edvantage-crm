"""Phase 7 — Career & Placements (end-to-end, runs against a dev server on
http://localhost:5000 with a FRESH DB (migrated via `flask db upgrade` +
seeded), with the same SQLITE_PATH for both server and this script).

Start the server with LMS_TUTOR_RULES_ONLY=1 so mock interviews use the
rules fallback (one OpenAI-mocked check runs in-process).

Coverage: resume builder (verified-data-only, PDF), portfolio public/private
toggle + public resume PDF, mock interview full flow + scoring (rules +
OpenAI-mocked), readiness score math + weight config + no-guarantee copy,
employer signup/approval gate/isolation, employer job + candidate pipeline,
placement analytics, access control.
"""
import os
import re
import sys

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app  # noqa: E402
from app.models import (Course, Enrollment, Job, JobApplication, MockInterview,
                        Portfolio, ReadinessWeights, Resume, User, db)  # noqa: E402

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
    r = session.post(f"{BASE}/login", data={"email": email,
                                            "password": password})
    return "Logout" in r.text


s_stu = requests.Session()
s_adm = requests.Session()
s_emp = requests.Session()
s_emp2 = requests.Session()
s_anon = requests.Session()

print("== Phase 7: Career & Placements ==")

with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    adm = User.query.filter_by(email="admin@sayyed.in").first()
    check("seed users present", stu and adm)

check("student login", login(s_stu, "student@sayyed.in", "student123"))
check("admin login", login(s_adm, "admin@sayyed.in", "admin123"))

# ---------------- resume builder ----------------
r = s_stu.get(f"{BASE}/career/resume")
check("resume builder page 200", r.status_code == 200 and "Resume Builder" in r.text)

r = s_stu.post(f"{BASE}/career/resume", allow_redirects=False, data={
    "headline": "Aspiring Data Analyst",
    "summary": "Fresher with hands-on Python and SQL practice.",
    "skills_text": "Communication, Excel",
    "experience_json": "[]",
    "education_json": '[{"degree":"B.Sc","school":"XYZ College","year":"2024"}]',
    "links_json": '{"github":"https://github.com/testuser"}'})
check("resume save redirects", r.status_code in (301, 302))

with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    rr = Resume.query.filter_by(user_id=stu.id).first()
    check("resume saved", rr and rr.headline == "Aspiring Data Analyst"
          and rr.is_complete())
    # enroll in one real course so verified sections have exactly one entry
    ds = Course.query.filter_by(slug="data-science").first()
    if not Enrollment.query.filter_by(user_id=stu.id, course_id=ds.id).first():
        db.session.add(Enrollment(user_id=stu.id, course_id=ds.id,
                                 status="active", paid=True))
        db.session.commit()
    enrolled_titles = {e.course.title for e in
                       Enrollment.query.filter_by(user_id=stu.id)
                       .filter(Enrollment.status.in_(["active", "completed"])).all()}
    check("fixture: one enrollment", enrolled_titles == {ds.title})

r = s_stu.get(f"{BASE}/career/resume")
# verified-only: exactly the enrolled course is shown — nothing invented
shown = set(re.findall(r"<li>([^<]+?) \u2014", r.text))
check("resume shows only verified courses",
      shown == enrolled_titles, f"shown={shown} enrolled={enrolled_titles}")

r = s_stu.get(f"{BASE}/career/resume/pdf")
check("resume PDF downloads", r.status_code == 200
      and r.content[:4] == b"%PDF", f"status={r.status_code}")

# ---------------- portfolio ----------------
r = s_stu.post(f"{BASE}/career/portfolio", allow_redirects=False, data={
    "headline": "Builder", "about": "I build things.", "is_public": "1",
    "show_resume": "1"})
check("portfolio save", r.status_code in (301, 302))
with app.app_context():
    pf = Portfolio.query.filter_by(
        user_id=User.query.filter_by(email="student@sayyed.in").first().id).first()
    code = pf.code if pf else None
    check("portfolio code issued", bool(code))

r = s_anon.get(f"{BASE}/portfolio/{code}")
check("public portfolio visible when public",
      r.status_code == 200 and "Builder" in r.text)
r = s_anon.get(f"{BASE}/portfolio/{code}/resume.pdf")
check("public resume PDF works",
      r.status_code == 200 and r.content[:4] == b"%PDF")

r = s_stu.post(f"{BASE}/career/portfolio",
               data={"headline": "Builder", "about": "I build things."})
with app.app_context():
    db.session.expire_all()
    pf2 = Portfolio.query.filter_by(code=code).first()
    check("portfolio toggled private", pf2 and not pf2.is_public)
r = s_anon.get(f"{BASE}/portfolio/{code}")
check("private portfolio hidden (404)", r.status_code == 404)

# ---------------- mock interviews (rules fallback) ----------------
r = s_stu.post(f"{BASE}/career/interviews",
               data={"target_role": "Junior Data Analyst", "course_id": ""},
               allow_redirects=False)
m = re.search(r"/career/interviews/(\d+)", r.headers.get("Location", ""))
check("interview session created", r.status_code in (301, 302) and m)
sid = int(m.group(1)) if m else 0

r = s_stu.get(f"{BASE}/career/interviews/{sid}")
check("interview session page 200",
      r.status_code == 200 and "Junior Data Analyst" in r.text)

done = False
overall = None
for i in range(5):
    r = s_stu.post(f"{BASE}/career/interviews/{sid}/answer", json={
        "answer": ("I would approach this by understanding the problem first, "
                   "then applying Python and SQL techniques I learned in the "
                   "course, testing my solution and documenting results.")})
    d = r.json()
    if i < 4:
        check(f"answer {i+1} scored + next question",
              d.get("score", 0) > 0 and d.get("next_question") and not d.get("done"),
              str(d)[:120])
    else:
        done, overall = d.get("done"), d.get("overall")
check("interview completes after 5 answers with overall score",
      done and overall is not None and 0 <= overall <= 100,
      f"done={done} overall={overall}")

with app.app_context():
    s = db.session.get(MockInterview, sid)
    check("session completed in DB",
          s.status == "completed" and s.score == overall and s.weak_areas)

r = s_stu.get(f"{BASE}/career/interviews")
check("interview history listed", r.status_code == 200 and "Junior Data Analyst" in r.text)

# OpenAI-mocked feedback path (in-process)
with app.app_context():
    import app.career as career_mod
    real = career_mod._openai_interview
    career_mod._openai_interview = lambda sp, msgs: "SCORE: 8.5\nFEEDBACK: Great structure."
    try:
        sc, fb = career_mod.interview_feedback(s, "Tell me about yourself", "I am a fresher.")
        check("OpenAI-mocked feedback parsed", sc == 8.5 and "Great structure" in fb,
              f"{sc} {fb}")
    finally:
        career_mod._openai_interview = real

# ---------------- readiness ----------------
r = s_stu.get(f"{BASE}/career/readiness")
check("readiness page 200 with score", r.status_code == 200 and "Readiness" in r.text)
check("no-guarantee copy present",
      "not a job guarantee" in r.text.lower() and "guidance" in r.text.lower())

with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    from app.career import readiness_for
    rd = readiness_for(stu)
    w = ReadinessWeights.get().as_dict()
    expect = round(sum(w[c["key"]] / sum(w.values()) * c["value"]
                       for c in rd["breakdown"]), 1)
    check("readiness math = weighted mean",
          abs(rd["score"] - expect) < 0.05, f"{rd['score']} vs {expect}")
    check("breakdown has 6 criteria", len(rd["breakdown"]) == 6)

r = s_adm.post(f"{BASE}/admin/career-settings", allow_redirects=False, data={
    "w_completion": "40", "w_quiz": "20", "w_projects": "10",
    "w_resume": "10", "w_interviews": "10", "w_certificates": "10"})
check("admin saves weights", r.status_code in (301, 302))
with app.app_context():
    db.session.expire_all()
    w2 = ReadinessWeights.get()
    check("weights persisted", w2.w_completion == 40.0 and w2.w_projects == 10.0)
    stu3 = User.query.filter_by(email="student@sayyed.in").first()
    rd2 = readiness_for(stu3)
    w3 = ReadinessWeights.get().as_dict()
    expect3 = round(sum(w3[c["key"]] / sum(w3.values()) * c["value"]
                        for c in rd2["breakdown"]), 1)
    check("score correct under new weights",
          abs(rd2["score"] - expect3) < 0.05, f"{rd2['score']} vs {expect3}")
r = s_stu.post(f"{BASE}/admin/career-settings", data={})
check("student blocked from career settings (403)", r.status_code == 403)

# ---------------- employer portal ----------------
r = s_emp.post(f"{BASE}/employer/signup", allow_redirects=False, data={
    "name": "Priya HR", "email": "hr@testco.example", "company": "TestCo",
    "phone": "+919999999999", "password": "employer123"})
check("employer signup -> pending approval", r.status_code in (301, 302))
with app.app_context():
    emp = User.query.filter_by(email="hr@testco.example").first()
    check("employer created inactive", emp and emp.role == "employer"
          and not emp.is_active and emp.company == "TestCo")
check("inactive employer cannot log in",
      not login(s_emp, "hr@testco.example", "employer123"))

r = s_adm.get(f"{BASE}/admin/employers")
check("admin sees pending employer", r.status_code == 200 and "TestCo" in r.text)
with app.app_context():
    emp_id = User.query.filter_by(email="hr@testco.example").first().id
r = s_adm.post(f"{BASE}/admin/employers/{emp_id}/approve", allow_redirects=False)
check("admin approves employer", r.status_code in (301, 302))
check("approved employer can log in",
      login(s_emp, "hr@testco.example", "employer123"))

r = s_emp.get(f"{BASE}/employer")
check("employer dashboard 200", r.status_code == 200 and "TestCo" in r.text)

r = s_emp.post(f"{BASE}/employer/jobs/new", allow_redirects=False, data={
    "title": "Junior Data Analyst", "company": "TestCo", "type": "job",
    "location": "Mumbai", "description": "Entry-level analyst role.",
    "skills": "Python, SQL", "active": "1", "apply_mode": "internal"})
check("employer posts job", r.status_code in (301, 302))
with app.app_context():
    job = Job.query.filter_by(title="Junior Data Analyst").first()
    check("job linked to employer", job and job.employer_id == emp_id)
    job_id = job.id if job else 0

r = s_anon.get(f"{BASE}/jobs")
check("employer job visible on public board",
      r.status_code == 200 and "Junior Data Analyst" in r.text)

# student applies
r = s_stu.post(f"{BASE}/jobs/{job_id}/apply", allow_redirects=False,
               data={"cover_note": "Excited to apply!", "phone": ""})
check("student applies", r.status_code in (301, 302))
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    app_row = JobApplication.query.filter_by(job_id=job_id,
                                             user_id=stu.id).first()
    check("application recorded", app_row and app_row.status == "applied")
    app_id = app_row.id if app_row else 0

# employer moves candidate through pipeline + note
for st in ("shortlisted", "interviewed", "offered", "placed"):
    r = s_emp.post(f"{BASE}/employer/jobs/{job_id}/applications", allow_redirects=False, data={
        "application_id": str(app_id), "status": st,
        "employer_note": f"moved to {st}"})
    check(f"employer sets status {st}", r.status_code in (301, 302))
with app.app_context():
    db.session.expire_all()
    a = db.session.get(JobApplication, app_id)
    check("final status placed + note saved",
          a.status == "placed" and a.employer_note == "moved to placed")

# employer isolation: second employer
s_emp2.post(f"{BASE}/employer/signup", allow_redirects=False, data={
    "name": "Rival HR", "email": "rival@testco.example", "company": "RivalCo",
    "password": "employer123"})
with app.app_context():
    emp2 = User.query.filter_by(email="rival@testco.example").first()
    emp2.is_active = True
    db.session.commit()
check("second employer login", login(s_emp2, "rival@testco.example", "employer123"))
r = s_emp2.get(f"{BASE}/employer/jobs/{job_id}/edit")
check("employer cannot edit another's job (404)", r.status_code == 404)
r = s_emp2.get(f"{BASE}/employer/jobs/{job_id}/applications")
check("employer cannot view another's applications (404)", r.status_code == 404)
r = s_emp2.get(f"{BASE}/employer")
check("employer sees only own jobs (0 jobs)",
      r.status_code == 200 and "Junior Data Analyst" not in r.text)

# student sees updated status
r = s_stu.get(f"{BASE}/applications")
check("student sees placed status", r.status_code == 200 and "placed" in r.text.lower())

# admin job board still sees everything
r = s_adm.get(f"{BASE}/admin/jobs")
check("admin job board intact", r.status_code == 200 and "Junior Data Analyst" in r.text)

# ---------------- placement analytics ----------------
r = s_adm.get(f"{BASE}/admin/placement-analytics")
check("placement analytics 200",
      r.status_code == 200 and "Placement Analytics" in r.text
      and "TestCo" in r.text)
r = s_stu.get(f"{BASE}/admin/placement-analytics")
check("student blocked from placement analytics (403)", r.status_code == 403)

# ---------------- access control ----------------
r = s_anon.get(f"{BASE}/career", allow_redirects=False)
check("anonymous redirected from /career", r.status_code in (301, 302))
r = s_emp.get(f"{BASE}/career")
check("employer blocked from student career (403)", r.status_code == 403)
r = s_stu.get(f"{BASE}/employer")
check("student blocked from employer portal (403)", r.status_code == 403)
r = s_anon.get(f"{BASE}/portfolio/does-not-exist-123")
check("bogus portfolio code 404", r.status_code == 404)

print(f"\n{passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
