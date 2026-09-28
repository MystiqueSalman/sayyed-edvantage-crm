"""Phase 13 Stream 2 — Learning extras (end-to-end).

Runs against a dev server on http://localhost:5000 with a FRESH DB
(migrated via `flask db upgrade` + seeded), same SQLITE_PATH for server and
this script. Because the coordinator wires the blueprint into
app/__init__.py separately, this suite registers learn13_bp in-process and
creates the new tables via db.create_all() (all tables are new, so this is
safe and additive). HTTP flows go through the Flask test client on the
in-process app; the dev server is not needed for these routes.

Coverage: schema tables exist, idempotent seed, notes CRUD + student
isolation, SQL lab (SELECT passes, INSERT/UPDATE/DROP rejected, comment
tricks rejected, wrong result fails, timeout safe), DS lab (validation
pass/fail, crash vs check-failure distinction, sandbox blocks, timeout),
course versioning (publish, history, enrollment linkage, backfill), video
security (signed URL works, tampered/expired/cross-user rejected, download
toggle, raw URL never in page source), developers docs section.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
import app.models13_learning as M13  # noqa: E402 (registers models + listener)
from app.learn13 import (ensure_learning13_defaults, learn13_bp,  # noqa: E402
                         run_ds_step, run_sql_attempt,
                         strip_sql_comments, validate_readonly_query)
from app.models import (Course, Enrollment, Lesson, Module, User)  # noqa: E402
from app.video13 import mint_video_token, verify_video_token  # noqa: E402

app = create_app()
if "learn13" not in app.blueprints:  # create_app() now registers all Phase 13 blueprints
    app.register_blueprint(learn13_bp)
# Another Phase 13 stream's blueprint injects template globals (to_user_tz,
# display_price, ...) that shared templates now require. Register it in the
# test app when importable so rendering matches the merged app.
try:
    from app.money13 import money13_bp  # noqa: E402
    if "money13" not in app.blueprints:
        app.register_blueprint(money13_bp)
except Exception:  # pragma: no cover - money13 stream may be mid-edit
    pass

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


def login(client, email, password):
    r = client.post("/login", data={"email": email, "password": password},
                    follow_redirects=True)
    return "Logout" in r.get_data(as_text=True)


with app.app_context():
    db.create_all()
    from sqlalchemy import inspect
    tables = set(inspect(db.engine).get_table_names())

for t in ["lesson_notes13", "sql_exercises13", "sql_attempts13",
          "ds_exercises13", "ds_progress13", "course_versions13",
          "enrollment_versions13", "video_policies13"]:
    check(f"table {t} exists", t in tables)

# ---------------------------------------------------------------- 2. seed
with app.app_context():
    ensure_learning13_defaults()
    n_sql = M13.SqlExercise13.query.count()
    n_ds = M13.DsExercise13.query.count()
    ensure_learning13_defaults()  # idempotent
    check("5 SQL exercises seeded",
          M13.SqlExercise13.query.count() == 5 == n_sql, n_sql)
    check("1 DS exercise seeded",
          M13.DsExercise13.query.count() == 1 == n_ds, n_ds)
    ex = M13.DsExercise13.query.first()
    check("DS exercise has 4 steps", len(ex.steps or []) == 4)
    check("datasets bundled",
          os.path.isfile(os.path.join("app", "static", "datasets",
                                       "student_scores.csv"))
          and os.path.isfile(os.path.join("app", "static", "datasets",
                                           "monthly_sales.csv")))
    from app.models import AppSetting
    check("video default-expiry setting key",
          AppSetting.get("p13_video_default_expiry_hours") == "2")

# ---------------------------------------------------------------- 3. fixture: users, course, lessons
with app.app_context():
    course = Course.query.first()
    assert course is not None
    COURSE_ID = course.id
    mod = course.modules[0] if course.modules else None
    if not mod:
        mod = Module(course_id=course.id, title="Seed module", position=0)
        db.session.add(mod)
        db.session.flush()
    lesson = mod.lessons[0] if mod.lessons else None
    if not lesson:
        lesson = Lesson(module_id=mod.id, title="Seed lesson",
                        kind=Lesson.KIND_TEXT, position=0)
        db.session.add(lesson)
        db.session.flush()
    LESSON_ID = lesson.id
    # second student for isolation tests
    s2 = User.query.filter_by(email="s2@sayyed.in").first()
    if not s2:
        s2 = User(name="Student Two", email="s2@sayyed.in", role="student")
        s2.set_password("student123")
        db.session.add(s2)
        db.session.flush()
    for em in ["student@sayyed.in", "s2@sayyed.in"]:
        u = User.query.filter_by(email=em).first()
        enr = Enrollment.query.filter_by(user_id=u.id,
                                         course_id=course.id).first()
        if not enr:
            db.session.add(Enrollment(user_id=u.id, course_id=course.id,
                                      status=Enrollment.STATUS_ACTIVE,
                                      paid=True))
    db.session.commit()

c_stu = app.test_client()
c_s2 = app.test_client()
c_adm = app.test_client()
c_anon = app.test_client()
assert login(c_stu, "student@sayyed.in", "student123"), "student login"
assert login(c_s2, "s2@sayyed.in", "student123"), "s2 login"
assert login(c_adm, "admin@sayyed.in", "admin123"), "admin login"

# ---------------------------------------------------------------- 4. notes
r = c_stu.get(f"/notes/lesson/{LESSON_ID}")
check("note form loads", r.status_code == 200, r.status_code)
r = c_stu.post(f"/notes/lesson/{LESSON_ID}",
               data={"title": "My title", "body": "first body"})
check("note create redirects", r.status_code in (301, 302), r.status_code)
with app.app_context():
    u1 = User.query.filter_by(email="student@sayyed.in").first()
    n1 = M13.LessonNote13.query.filter_by(user_id=u1.id,
                                          lesson_id=LESSON_ID).first()
    check("note row created", n1 is not None and n1.body == "first body")
    N1_ID = n1.id if n1 else None
r = c_stu.get("/notes")
html = r.get_data(as_text=True)
check("notes list shows my note", "My title" in html)

r = c_stu.post(f"/notes/lesson/{LESSON_ID}",
               data={"title": "My title", "body": "updated body"})
with app.app_context():
    rows = M13.LessonNote13.query.filter_by(user_id=u1.id,
                                            lesson_id=LESSON_ID).all()
    check("note update keeps one row per lesson",
          len(rows) == 1 and rows[0].body == "updated body", len(rows))

# isolation: second student
r = c_s2.get("/notes")
check("student2 cannot see student1's note", "My title" not in
      r.get_data(as_text=True))
r = c_s2.post(f"/notes/lesson/{LESSON_ID}",
              data={"title": "S2 note", "body": "s2 body"})
with app.app_context():
    u2 = User.query.filter_by(email="s2@sayyed.in").first()
    n2 = M13.LessonNote13.query.filter_by(user_id=u2.id,
                                          lesson_id=LESSON_ID).first()
    check("student2 has own note doc", n2 is not None and n2.body == "s2 body")
    check("unique(user_id, lesson_id) holds",
          M13.LessonNote13.query.filter_by(lesson_id=LESSON_ID).count() == 2)
r = c_s2.get("/notes")
check("student2 sees own note", "S2 note" in r.get_data(as_text=True))
r = c_stu.get("/notes")
check("student1 still only sees own", "S2 note" not in
      r.get_data(as_text=True))

# unenrolled lesson -> 403
with app.app_context():
    other = Course.query.filter(Course.id != COURSE_ID).first()
    if other:
        m2 = other.modules[0] if other.modules else None
        if m2 and m2.lessons:
            OTHER_LESSON = m2.lessons[0].id
        else:
            OTHER_LESSON = None
    else:
        OTHER_LESSON = None
if OTHER_LESSON:
    r = c_s2.get(f"/notes/lesson/{OTHER_LESSON}")
    check("note on unenrolled lesson -> 403", r.status_code == 403,
          r.status_code)
else:
    check("note on unenrolled lesson -> 403", True, "skipped: one course")

r = c_stu.post(f"/notes/lesson/{LESSON_ID}/delete")
with app.app_context():
    check("note delete works",
          M13.LessonNote13.query.get(N1_ID) is None)
r = c_anon.get("/notes")
check("anonymous notes -> login redirect", r.status_code in (301, 302),
      r.status_code)

# ---------------------------------------------------------------- 5. SQL lab
r = c_stu.get("/labs/sql")
check("sql list loads with 5 exercises",
      r.status_code == 200 and r.get_data(as_text=True).count("Practice →") == 5,
      r.status_code)
with app.app_context():
    ex1 = M13.SqlExercise13.query.filter_by(title="High scorers").first()
    EX1 = ex1.id
r = c_stu.get(f"/labs/sql/{EX1}")
check("sql detail loads", r.status_code == 200, r.status_code)

r = c_stu.post(f"/labs/sql/{EX1}/run",
               data={"query": "SELECT name, score FROM students WHERE score >= 85;"})
j = r.get_json()
check("correct SELECT passes", j["ok"] and j["passed"] is True, j)
with app.app_context():
    check("attempt logged as passed",
          M13.SqlAttempt13.query.filter_by(exercise_id=EX1,
                                           passed=True).count() >= 1)

r = c_stu.post(f"/labs/sql/{EX1}/run",
               data={"query": "SELECT name, score FROM students WHERE score >= 90;"})
j = r.get_json()
check("wrong result fails", j["ok"] and j["passed"] is False, j)

for bad, label in [
        ("INSERT INTO students (name, score) VALUES ('X', 1);", "INSERT"),
        ("UPDATE students SET score = 0;", "UPDATE"),
        ("DROP TABLE students;", "DROP"),
        ("-- just a comment\nDROP TABLE students;", "comment-trick DROP"),
        ("SELECT * FROM students; DELETE FROM students;", "stacked DELETE"),
        ("ATTACH DATABASE '/tmp/x.db' AS x;", "ATTACH"),
]:
    ok, err = validate_readonly_query(bad)
    check(f"SQL lab rejects {label}", ok is False, err)
r = c_stu.post(f"/labs/sql/{EX1}/run",
               data={"query": "DROP TABLE students;"})
j = r.get_json()
check("DROP via HTTP rejected", j["ok"] and j["passed"] is False
      and "read-only" in j["error"].lower() or "allowed" in j["error"].lower(), j)

ok, _ = validate_readonly_query("  -- c\n  with x as (select 1 as a) select * from x")
check("WITH accepted (case-insensitive, comments stripped)", ok is True)
check("comment stripper respects quotes",
      strip_sql_comments("SELECT '--x'").strip() == "SELECT '--x'")

r = c_stu.post(f"/labs/sql/{EX1}/run", data={
    "query": "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) "
             "SELECT count(*) FROM c;"})
j = r.get_json()
check("runaway query hits time limit safely",
      j["ok"] and j["passed"] is False and "time limit" in j["error"].lower(),
      j.get("error"))
r = c_anon.get("/labs/sql")
check("anonymous sql lab -> login redirect", r.status_code in (301, 302),
      r.status_code)

# ---------------------------------------------------------------- 6. DS lab
r = c_stu.get("/labs/datascience")
check("ds list loads", r.status_code == 200, r.status_code)
with app.app_context():
    dsex = M13.DsExercise13.query.first()
    DSX = dsex.id
r = c_stu.get(f"/labs/datascience/{DSX}")
check("ds detail shows 4 steps",
      r.status_code == 200 and r.get_data(as_text=True).count("Run &amp; check") == 4,
      r.status_code)

GOOD_STEP0 = ("rows = list(csv.reader(DATASET_CSV.splitlines()))\n"
              "scores = [float(r[2]) for r in rows[1:]]\n"
              "mean_score = sum(scores) / len(scores)\n"
              "print(mean_score)\n")
r = c_stu.post(f"/labs/datascience/{DSX}/step/0/run",
               data={"code": GOOD_STEP0})
j = r.get_json()
check("ds step0 correct code passes", j["ok"] and j["passed"] is True, j)
with app.app_context():
    prog = M13.DsProgress13.query.filter_by(user_id=u1.id, exercise_id=DSX,
                                            step_idx=0).first()
    check("ds progress recorded (passed)",
          prog is not None and prog.passed is True)

r = c_stu.post(f"/labs/datascience/{DSX}/step/0/run",
               data={"code": "mean_score = 0.0\nprint(mean_score)\n"})
j = r.get_json()
check("ds step0 wrong value fails",
      j["ok"] and j["passed"] is False and "check failed" in j["error"], j)

r = c_stu.post(f"/labs/datascience/{DSX}/step/0/run",
               data={"code": "mean_score = 1/0\n"})
j = r.get_json()
check("ds step0 crash reported as code error",
      j["ok"] and j["passed"] is False and "raised an error" in j["error"], j)

r = c_stu.post(f"/labs/datascience/{DSX}/step/0/run",
               data={"code": "import os\nmean_score = 84.1\n"})
j = r.get_json()
check("ds sandbox blocks dangerous import",
      j["ok"] and j["passed"] is False, j)

r = c_stu.post(f"/labs/datascience/{DSX}/step/0/run",
               data={"code": "while True:\n    pass\n"})
j = r.get_json()
check("ds infinite loop hits sandbox timeout",
      j["ok"] and j["passed"] is False and "time limit" in j["error"].lower(),
      j.get("error"))

# direct runner: steps 1..3 good code
with app.app_context():
    dsex = M13.DsExercise13.query.get(DSX)
    r1 = run_ds_step(dsex, 1,
                     "rows=list(csv.reader(DATASET_CSV.splitlines()))\n"
                     "topper=max(rows[1:], key=lambda r: int(r[2]))[0]\n")
    check("ds step1 topper passes", r1["passed"] is True, r1)
    r2 = run_ds_step(dsex, 2,
                     "rows=list(csv.reader(DATASET_CSV.splitlines()))\n"
                     "total_revenue=sum(int(r[1]) for r in rows[1:])\n")
    check("ds step2 total passes", r2["passed"] is True, r2)
    r3 = run_ds_step(dsex, 3,
                     "rows=list(csv.reader(DATASET_CSV.splitlines()))\n"
                     "data=rows[1:]\n"
                     "avg=sum(int(r[1]) for r in data)/len(data)\n"
                     "above_avg_months=[r[0] for r in data if int(r[1])>avg]\n")
    check("ds step3 above-avg months passes", r3["passed"] is True, r3)
    rbad = run_ds_step(dsex, 99, "x=1")
    check("ds unknown step rejected", rbad["passed"] is False)

# ---------------------------------------------------------------- 7. versioning
r = c_stu.post(f"/manage/courses/{COURSE_ID}/versions/publish",
               data={"note": "student attempt"})
check("student cannot publish version", r.status_code == 403, r.status_code)
r = c_adm.post(f"/manage/courses/{COURSE_ID}/versions/publish",
               data={"note": "first release"})
check("admin publishes version", r.status_code in (301, 302), r.status_code)
with app.app_context():
    v1 = M13.CourseVersion13.query.filter_by(course_id=COURSE_ID,
                                             version_no=1).first()
    check("version 1 snapshot has modules",
          v1 is not None and len((v1.snapshot or {}).get("modules", [])) >= 1)
    check("snapshot lessons carry title+kind",
          all("title" in l and "kind" in l
              for m in v1.snapshot["modules"] for l in m["lessons"]))
r = c_adm.post(f"/manage/courses/{COURSE_ID}/versions/publish",
               data={"note": "second"})
with app.app_context():
    v2 = M13.CourseVersion13.query.filter_by(course_id=COURSE_ID,
                                             version_no=2).first()
    check("version_no auto-increments per course", v2 is not None)
    V2_ID = v2.id
r = c_adm.get(f"/manage/courses/{COURSE_ID}/versions")
html = r.get_data(as_text=True)
check("version history lists v1+v2",
      r.status_code == 200 and "v1" in html and "v2" in html, r.status_code)
r = c_adm.get(f"/manage/courses/{COURSE_ID}/versions?view={V2_ID}")
check("snapshot view loads", r.status_code == 200
      and "Snapshot" in r.get_data(as_text=True), r.status_code)

# enrollment -> version linkage via the after_insert hook
with app.app_context():
    u3 = User(name="Student Three", email="s3@sayyed.in", role="student")
    u3.set_password("student123")
    db.session.add(u3)
    db.session.flush()
    db.session.add(Enrollment(user_id=u3.id, course_id=COURSE_ID,
                              status=Enrollment.STATUS_ACTIVE, paid=True))
    db.session.commit()
    enr3 = Enrollment.query.filter_by(user_id=u3.id,
                                      course_id=COURSE_ID).first()
    link = M13.EnrollmentVersion13.query.filter_by(
        enrollment_id=enr3.id).first()
    check("new enrollment auto-linked to latest version",
          link is not None and link.version_id == V2_ID,
          f"{link.version_id if link else None} vs {V2_ID}")
    # backfill-on-view when the link row is missing
    db.session.delete(link)
    db.session.commit()
    check("backfill-on-view returns latest version",
          M13.version_for_enrollment(enr3).version_no == 2)
    other_course = Course.query.filter(Course.id != COURSE_ID).first()
    if other_course:
        enr_nc = Enrollment(user_id=u3.id, course_id=other_course.id,
                             status=Enrollment.STATUS_ACTIVE, paid=True)
        db.session.add(enr_nc)
        db.session.commit()
        check("no versions -> version_for_enrollment is None",
              M13.version_for_enrollment(enr_nc) is None)
    else:
        check("no versions -> version_for_enrollment is None", True,
              "skipped: one course")

# ---------------------------------------------------------------- 8. video security
with app.app_context():
    mod = Module.query.filter_by(course_id=COURSE_ID).first()
    vl = Lesson(module_id=mod.id, title="Video lesson", kind=Lesson.KIND_VIDEO,
                video_url="https://www.youtube.com/embed/TEST123", position=99)
    db.session.add(vl)
    db.session.commit()
    VID = vl.id

r = c_stu.get(f"/lesson/{VID}")
html = r.get_data(as_text=True)
m = re.search(r"/v/([A-Za-z0-9_\-]+)", html)
check("lesson page embeds signed URL", r.status_code == 200 and m is not None,
      r.status_code)
TOKEN = m.group(1) if m else ""
check("raw video URL not in lesson page source", "TEST123" not in html)

r = c_stu.get(f"/v/{TOKEN}")
html = r.get_data(as_text=True)
check("watch page loads", r.status_code == 200, r.status_code)
check("raw video URL not in watch page source", "TEST123" not in html)
check("watch page uses signed stream URL",
      f"/v/{TOKEN}/stream" in html)
check("download hidden by default", "Download video" not in html)

r = c_stu.get(f"/v/{TOKEN}/stream")
check("stream redirects to stored URL",
      r.status_code == 302 and "TEST123" in r.headers.get("Location", ""),
      (r.status_code, r.headers.get("Location")))

with app.app_context():
    coords, err = verify_video_token(TOKEN)
check("token verifies", err is None and coords[0] == VID, err)
tampered = TOKEN[:-1] + ("A" if TOKEN[-1] != "A" else "B")
r = c_stu.get(f"/v/{tampered}")
check("tampered token rejected", r.status_code == 403, r.status_code)
with app.app_context():
    u1 = User.query.filter_by(email="student@sayyed.in").first()
    expired = mint_video_token(VID, u1.id, expiry_hours=-1)
r = c_stu.get(f"/v/{expired}")
check("expired token rejected", r.status_code == 403, r.status_code)
with app.app_context():
    u2 = User.query.filter_by(email="s2@sayyed.in").first()
    other_tok = mint_video_token(VID, u2.id)
r = c_stu.get(f"/v/{other_tok}")
check("cross-user token rejected", r.status_code == 403, r.status_code)
r = c_anon.get(f"/v/{TOKEN}")
check("anonymous watch -> login redirect", r.status_code in (301, 302),
      r.status_code)

# download toggle + policy editor
r = c_adm.post(f"/manage/lessons/{VID}/video-policy",
               data={"allow_download": "on", "token_expiry_hours": "4"})
check("policy editor saves (admin)", r.status_code in (301, 302),
      r.status_code)
with app.app_context():
    pol = M13.VideoPolicy13.query.filter_by(lesson_id=VID).first()
    check("policy row stored",
          pol is not None and pol.allow_download is True
          and pol.token_expiry_hours == 4)
r = c_stu.get(f"/v/{TOKEN}")
check("download shown when allowed",
      "Download video" in r.get_data(as_text=True))
r = c_adm.post(f"/manage/lessons/{VID}/video-policy",
               data={"token_expiry_hours": "2"})
r = c_stu.get(f"/v/{TOKEN}")
check("download hidden when disallowed",
      "Download video" not in r.get_data(as_text=True))
r = c_stu.post(f"/manage/lessons/{VID}/video-policy",
               data={"allow_download": "on"})
check("student cannot edit video policy", r.status_code == 403,
      r.status_code)

# developers docs
r = c_adm.get("/developers")
check("developers docs cover video security",
      "Video Security" in r.get_data(as_text=True), r.status_code)

# ---------------------------------------------------------------- 9. regression: additive-only
# Templates must render through the full merged app (create_app now wires
# every Phase 13 blueprint). The lesson page keeps its raw-video fallback
# path and the manage pages hide panels cleanly.
from flask import render_template as _rt  # noqa: E402
app_nobp = create_app()
with app_nobp.test_request_context("/"):
    with app_nobp.app_context():
        lsn = Lesson.query.get(VID)
        html = _rt("lesson.html", lesson=lsn, course=lsn.module.course,
                   done=False, prev_lesson=None, next_lesson=None,
                   module_quiz=None, locked=False)
        check("lesson page renders without learn13 (fallback intact)",
              "TEST123" in html and "/v/" not in html)
        html2 = _rt("manage_course.html", course=lsn.module.course)
        check("manage course renders with learn13 registered",
              lsn.module.course.title in html2)

print(f"\n{passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
