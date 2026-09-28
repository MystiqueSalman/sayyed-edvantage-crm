"""Phase 12 — Advanced Scale/SaaS (end-to-end).

Runs against a dev server on http://localhost:5000 with a FRESH DB
(migrated via `flask db upgrade` + seeded), same SQLITE_PATH for server and
this script. Mixes HTTP flows with in-process checks.

Every app-context block re-fetches its rows (never reuse ORM instances
across blocks — the session closes between them).

Coverage: migration head, default tenant seed + idempotency, tenant
create/toggle + default-tenant protection + role gates, legacy NULL rows,
branding fallback/custom/invalid-color, EN/Hindi session switch,
sandbox success/blocked-import/blocked-file/timeout/check,
faculty lab authoring + student run/check + attempt persistence,
adaptive recommendations + class aggregates, virtual-lab authoring/
terminal/completion/idempotency, bulk-enroll CSV success/dup/unknown-course,
audit-log CSV export + filters, Google OAuth stub (coming soon, secret never
echoed), role restrictions on every new admin endpoint.
"""
import io
import os
import sys
from datetime import datetime

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app.models import (AuditLog, Course, Enrollment, LabAttempt,  # noqa: E402
                        LabExercise, Lesson, Module, Quiz, Question,
                        QuizAttempt, Tenant, TenantSetting, User,
                        VLabProgress, VLabScenario)

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
    r = session.post(f"{BASE}/login",
                     data={"email": email, "password": password})
    return "Logout" in r.text


# ---------------------------------------------------------------- 1. setup

s_adm = requests.Session()
assert login(s_adm, "admin@sayyed.in", "admin123"), "admin login failed"
s_fac = requests.Session()
assert login(s_fac, "faculty@sayyed.in", "faculty123"), "faculty login failed"
s_stu = requests.Session()
assert login(s_stu, "student@sayyed.in", "student123"), "student login failed"
s_anon = requests.Session()

with app.app_context():
    head = db.session.execute(
        db.text("SELECT version_num FROM alembic_version")).fetchone()[0]
    check("migration head is Phase 13", head == "p13f1a2b3c4d5", head)

# ---------------------------------------------------------------- 2. tenant seed

with app.app_context():
    from app import saas as S
    t = Tenant.query.filter_by(slug="sayyed-edvantage").first()
    check("default tenant seeded", t is not None and t.active)
    check("only one default tenant row",
          Tenant.query.filter_by(slug="sayyed-edvantage").count() == 1)
    S.ensure_saas_defaults()  # idempotent
    check("ensure_saas_defaults idempotent",
          Tenant.query.filter_by(slug="sayyed-edvantage").count() == 1)

# legacy rows keep working: seeded users have NULL tenant
with app.app_context():
    adm = User.query.filter_by(email="admin@sayyed.in").first()
    check("legacy admin row has NULL tenant_id", adm.tenant_id is None)

# ---------------------------------------------------------------- 3. tenant CRUD + protection

r = s_adm.post(f"{BASE}/admin/tenants/new",
               data={"name": "Acme Academy", "slug": "acme-academy"},
               allow_redirects=True)
with app.app_context():
    acme = Tenant.query.filter_by(slug="acme-academy").first()
    check("admin creates tenant", acme is not None and not acme.active)
    acme_id = acme.id

r = s_fac.get(f"{BASE}/admin/tenants")
check("faculty blocked from tenant list", r.status_code == 403, r.status_code)
r = s_stu.get(f"{BASE}/admin/tenants")
check("student blocked from tenant list", r.status_code == 403, r.status_code)

r = s_adm.post(f"{BASE}/admin/tenants/{acme_id}/toggle",
               allow_redirects=True)
with app.app_context():
    acme = Tenant.query.get(acme_id)
    check("admin toggles tenant active", acme.active is True)

with app.app_context():
    default_id = Tenant.query.filter_by(slug="sayyed-edvantage").first().id
r = s_adm.post(f"{BASE}/admin/tenants/{default_id}/toggle",
               allow_redirects=True)
with app.app_context():
    t = Tenant.query.get(default_id)
    check("default tenant cannot be deactivated", t.active is True)

r = s_adm.get(f"{BASE}/admin/tenants")
check("tenant list page renders", r.status_code == 200
      and "Acme Academy" in r.text, r.status_code)

# ---------------------------------------------------------------- 4. branding

with app.app_context():
    from app import saas as S
    b = S.get_brand()
    check("branding falls back to Sayyed EdVantage by default",
          b["brand_name"] == "Sayyed EdVantage" and not b["is_custom"])
    check("branding has no color overrides by default",
          b["primary_color"] == "" and b["accent_color"] == "")

r = s_adm.post(f"{BASE}/admin/branding",
               data={"brand_name": "Acme Academy",
                     "tagline": "Learn. Build. Earn.",
                     "primary_color": "#123456",
                     "accent_color": "not-a-color"},
               allow_redirects=True)
with app.app_context():
    from app import saas as S
    b = S.get_brand()
    check("custom brand name saved", b["brand_name"] == "Acme Academy")
    check("custom primary color saved", b["primary_color"] == "#123456")
    check("invalid accent color rejected", b["accent_color"] == "")
    check("brand marked custom", b["is_custom"] is True)

r = s_adm.get(f"{BASE}/")
check("homepage renders with custom brand",
      r.status_code == 200 and "--gold:#123456" in r.text, r.status_code)

# reset to default
r = s_adm.post(f"{BASE}/admin/branding",
               data={"brand_name": "", "tagline": "",
                     "primary_color": "", "accent_color": ""},
               allow_redirects=True)
with app.app_context():
    from app import saas as S
    b = S.get_brand()
    check("branding reset to default",
          b["brand_name"] == "Sayyed EdVantage" and not b["is_custom"])
r = s_adm.get(f"{BASE}/")
check("homepage identical by default",
      r.status_code == 200 and "--gold:" not in r.text
      and "Empowering Students for Success" in r.text, r.status_code)

r = s_fac.get(f"{BASE}/admin/branding")
check("faculty blocked from branding", r.status_code == 403, r.status_code)

# ---------------------------------------------------------------- 5. i18n

with app.app_context():
    from app import i18n as I
    check("supported languages are en+hi",
          tuple(c for c, _ in I.LANGUAGES) == ("en", "hi"))

r = s_anon.get(f"{BASE}/lang/hi", allow_redirects=True)
check("Hindi switch redirects home", r.status_code == 200, r.status_code)
check("Hindi hero rendered", "वो स्किल्स सीखें जिनसे नौकरी मिले।" in r.text)
check("Hindi nav rendered", "पाठ्यक्रम" in r.text and "नौकरियां" in r.text)
check("Hindi footer tagline", "छात्रों की सफलता के लिए सशक्तिकरण" in r.text)

r = s_anon.get(f"{BASE}/lang/en", allow_redirects=True)
check("English switch works",
      "Master the Skills That Get You Hired." in r.text)

r = s_anon.get(f"{BASE}/lang/xx", allow_redirects=True)
check("invalid language code ignored",
      r.status_code == 200 and "Master the Skills That Get You Hired." in r.text)

with app.app_context():
    with app.test_request_context("/"):
        from app import i18n as I
        I.set_lang("hi")
        check("t() translates in-process", I.t("courses") == "पाठ्यक्रम")
        I.set_lang("en")
        check("t() falls back to English", I.t("courses") == "Courses")
        check("missing key returns key", I.t("no_such_key_xyz") == "no_such_key_xyz")

# ---------------------------------------------------------------- 6. sandbox

with app.app_context():
    from app import labs as LAB
    ok, out, err = LAB.run_python_code('print(2 + 2)')
    check("sandbox runs normal code", ok and out == "4\n", f"{ok} {out!r} {err!r}")
    ok, out, err = LAB.run_python_code('import os\nprint("x")')
    check("sandbox blocks import os", not ok and "not allowed" in err.lower(), err)
    ok, out, err = LAB.run_python_code('open("/etc/passwd").read()')
    check("sandbox blocks open()", not ok and "not allowed" in err.lower(), err)
    ok, out, err = LAB.run_python_code('__import__("os")')
    check("sandbox blocks __import__", not ok, err)
    ok, out, err = LAB.run_python_code('while True:\n    pass')
    check("sandbox kills infinite loop", not ok and "ime" in err.lower(), err)
    ok, out, err = LAB.run_python_code('print("Hello")')
    check("output check passes on match", LAB.check_output(out, "Hello"))
    check("output check fails on mismatch", not LAB.check_output(out, "Goodbye"))
    ok, out, err = LAB.run_python_code('print("x" * 100000)')
    check("sandbox caps output size", ok and len(out) <= 20 * 1024 + 64, len(out))

# ---------------------------------------------------------------- 7. lab authoring (faculty)

with app.app_context():
    lesson_id = Lesson.query.first().id

r = s_fac.post(f"{BASE}/manage/labs/new",
               data={"lesson_id": lesson_id, "title": "P12 Sum Lab",
                     "instructions": "Add them.", "starter_code": "a = 1",
                     "expected_output": "3", "is_published": "1"},
               allow_redirects=True)
with app.app_context():
    ex = LabExercise.query.filter_by(title="P12 Sum Lab").first()
    check("faculty creates lab exercise", ex is not None and ex.is_published)
    ex_id = ex.id

r = s_fac.post(f"{BASE}/manage/labs/{ex_id}/edit",
               data={"lesson_id": lesson_id, "title": "P12 Sum Lab",
                     "instructions": "Add them.", "starter_code": "a = 1",
                     "expected_output": "3"},
               allow_redirects=True)  # unchecked = unpublish
with app.app_context():
    ex = LabExercise.query.get(ex_id)
    check("faculty can unpublish exercise", ex.is_published is False)

r = s_stu.get(f"{BASE}/manage/labs")
check("student blocked from lab manage", r.status_code == 403, r.status_code)
r = s_anon.get(f"{BASE}/manage/labs", allow_redirects=False)
check("anonymous redirected from lab manage",
      r.status_code in (301, 302), r.status_code)

# ---------------------------------------------------------------- 8. student lab run/check

with app.app_context():
    py = Course.query.filter_by(slug="python-programming").first()
    stu = User.query.filter_by(email="student@sayyed.in").first()
    if not Enrollment.query.filter_by(user_id=stu.id,
                                      course_id=py.id).first():
        db.session.add(Enrollment(user_id=stu.id, course_id=py.id,
                                  status="active"))
        db.session.commit()
    # re-publish the test exercise on the python course's first lesson
    lesson = py.modules[0].lessons[0]
    ex = LabExercise.query.get(ex_id)
    ex.lesson_id = lesson.id
    ex.is_published = True
    db.session.commit()

r = s_stu.get(f"{BASE}/labs")
check("lab list page renders",
      r.status_code == 200 and "P12 Sum Lab" in r.text, r.status_code)

r = s_stu.get(f"{BASE}/labs/{ex_id}")
check("lab detail page renders",
      r.status_code == 200 and "Your code" in r.text, r.status_code)

r = s_stu.post(f"{BASE}/labs/{ex_id}/run", json={"code": "print(1 + 2)"})
d = r.json()
check("student run executes", r.status_code == 200 and d["ok"]
      and d["output"] == "3\n", f"{r.status_code} {d}")

r = s_stu.post(f"{BASE}/labs/{ex_id}/check", json={"code": "print(1 + 2)"})
d = r.json()
check("student check passes on match",
      r.status_code == 200 and d["ok"] and d["passed"] is True, d)

r = s_stu.post(f"{BASE}/labs/{ex_id}/check", json={"code": "print(99)"})
d = r.json()
check("student check fails on mismatch",
      r.status_code == 200 and d["ok"] and d["passed"] is False, d)

r = s_stu.post(f"{BASE}/labs/{ex_id}/run", json={"code": "import os"})
d = r.json()
check("student run blocks unsafe code",
      r.status_code == 200 and not d["ok"], d)

with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    att = (LabAttempt.query.filter_by(user_id=stu.id, exercise_id=ex_id,
                                      passed=True)
             .order_by(LabAttempt.id.desc()).first())
    check("attempt persisted with pass flag",
          att is not None and "3" in att.output)

r = s_anon.post(f"{BASE}/labs/{ex_id}/run", json={"code": "print(1)"},
                allow_redirects=False)
check("anonymous run requires login", r.status_code in (301, 302),
      r.status_code)

# ---------------------------------------------------------------- 9. adaptive learning

with app.app_context():
    from app import adaptive as AD
    py = Course.query.filter_by(slug="python-programming").first()
    stu = User.query.filter_by(email="student@sayyed.in").first()
    mod = py.modules[0]
    q = Quiz(module_id=mod.id, title="P12 Quiz")
    db.session.add(q)
    db.session.flush()
    for i, letter in enumerate("AB"):
        db.session.add(Question(quiz_id=q.id, text=f"Q{i}",
                                option_a="a", option_b="b",
                                correct=letter, position=i))
    db.session.add(QuizAttempt(quiz_id=q.id, user_id=stu.id,
                               score=4.0, total=10.0,
                               submitted_at=datetime.utcnow()))
    db.session.commit()
    quiz_id, mod_id = q.id, mod.id

with app.app_context():
    from app import adaptive as AD
    py = Course.query.filter_by(slug="python-programming").first()
    stu = User.query.filter_by(email="student@sayyed.in").first()
    recs = AD.recommendations_for_student(stu.id, py.id)
    check("weak module recommended",
          any(r["module_id"] == mod_id and r["avg"] == 40.0 for r in recs),
          recs)
    agg = AD.class_weak_topics(py.id)
    row = next((a for a in agg if a["module_id"] == mod_id), None)
    check("class aggregate flags weak module",
          row is not None and row["weak"] and row["weak_students"] >= 1,
          agg)

r = s_stu.get(f"{BASE}/learn/recommended")
check("recommended page renders",
      r.status_code == 200 and "Recommended Next" in r.text, r.status_code)
r = s_adm.get(f"{BASE}/admin/adaptive")
check("adaptive admin 403-safe page loads", r.status_code == 200,
      r.status_code)
r = s_adm.get(f"{BASE}/admin/adaptive?course_id={py.id}")
check("adaptive admin aggregates render",
      r.status_code == 200 and "weak" in r.text.lower(), r.status_code)

# ---------------------------------------------------------------- 10. virtual labs

with app.app_context():
    from app import vlabs as V
    ok, msg = V.validate_scenario_json(
        '{"fs": {}, "tasks": [{"instruction": "x", '
        '"validate": {"command": "pwd"}}]}')
    check("scenario validator accepts minimal", ok, msg)
    bad, msg = V.validate_scenario_json("not json")
    check("scenario validator rejects bad JSON", not bad, msg)
    bad2, msg = V.validate_scenario_json('{"fs": {}}')
    check("scenario validator requires tasks", not bad2, msg)

with app.app_context():
    py = Course.query.filter_by(slug="linux-administration").first()
    py_id = py.id

r = s_fac.post(f"{BASE}/manage/vlabs/new",
               data={"title": "P12 Test Scenario",
                     "description": "desc",
                     "course_id": str(py_id),
                     "scenario_json": ('{"fs": {"home": {"student": {}}}, '
                                       '"tasks": [{"instruction": "Run pwd", '
                                       '"validate": {"command": "pwd"}}]}'),
                     "is_published": "1"},
               allow_redirects=True)
with app.app_context():
    sc = VLabScenario.query.filter_by(title="P12 Test Scenario").first()
    check("faculty creates vlab scenario", sc is not None and sc.is_published)
    sc_id = sc.id

r = s_stu.get(f"{BASE}/vlabs")
check("vlabs list shows scenario",
      r.status_code == 200 and "P12 Test Scenario" in r.text, r.status_code)
r = s_stu.get(f"{BASE}/vlabs/{sc_id}")
check("terminal page renders with scenario JSON",
      r.status_code == 200 and "P12 Test Scenario" in r.text
      and "tasks" in r.text, r.status_code)
r = s_stu.post(f"{BASE}/vlabs/{sc_id}/complete", json={"log": "$ pwd"})
d = r.json()
check("completion tracked", r.status_code == 200 and d["ok"] is True, d)
r = s_stu.post(f"{BASE}/vlabs/{sc_id}/complete", json={"log": "$ pwd"})
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    n = VLabProgress.query.filter_by(user_id=stu.id,
                                     scenario_id=sc_id).count()
    check("completion idempotent (one row)", n == 1, n)
r = s_stu.get(f"{BASE}/vlabs")
check("completed badge shown",
      r.status_code == 200 and "completed" in r.text.lower(), r.status_code)
r = s_fac.get(f"{BASE}/manage/vlabs")
check("faculty blocked from vlab manage? no — allowed",
      r.status_code == 200, r.status_code)
r = s_stu.get(f"{BASE}/manage/vlabs")
check("student blocked from vlab manage", r.status_code == 403,
      r.status_code)

# seeded example scenario visible
r = s_stu.get(f"{BASE}/vlabs")
check("seeded example scenario present",
      "Linux Basics" in r.text, r.status_code)

# ---------------------------------------------------------------- 11. bulk enrollment

csv_text = ("name,email,course\n"
            "Bulk One,bulkone@example.com,python-programming\n"
            "Bulk Two,bulktwo@example.com,python-programming\n"
            "Dup One,bulkone@example.com,python-programming\n"
            "Bad Course,badcourse@example.com,no-such-course\n"
            ",noname@example.com,python-programming\n")
r = s_adm.post(f"{BASE}/admin/bulk-enroll",
               files={"csv": ("enroll.csv", io.BytesIO(
                   csv_text.encode()), "text/csv")},
               allow_redirects=True)
with app.app_context():
    u1 = User.query.filter_by(email="bulkone@example.com").first()
    u2 = User.query.filter_by(email="bulktwo@example.com").first()
    py = Course.query.filter_by(slug="python-programming").first()
    e1 = Enrollment.query.filter_by(user_id=u1.id,
                                    course_id=py.id).count() if u1 else 0
    check("bulk enroll creates users", u1 is not None and u2 is not None)
    check("bulk enroll creates enrollments",
          e1 == 1 and Enrollment.query.filter_by(
              user_id=u2.id, course_id=py.id).count() == 1)
    check("bulk enroll skips duplicate rows", e1 == 1)
    check("bulk user role is student", u1.role == "student")
check("bulk enroll report shows counts",
      r.status_code == 200 and "Users created" in r.text
      and "unknown course: no-such-course" in r.text
      and "name/email missing or invalid" in r.text, r.status_code)

r = s_fac.post(f"{BASE}/admin/bulk-enroll",
               files={"csv": ("e.csv", io.BytesIO(b"name,email,course\n"),
                              "text/csv")})
check("faculty blocked from bulk enroll", r.status_code == 403,
      r.status_code)

# ---------------------------------------------------------------- 12. audit CSV export

with app.app_context():
    db.session.add(AuditLog(actor_email="admin@sayyed.in",
                            action="p12.test_export",
                            target_type="test", detail="hello"))
    db.session.commit()

r = s_adm.get(f"{BASE}/admin/audit-logs/export.csv")
check("audit export returns CSV",
      r.status_code == 200
      and "text/csv" in r.headers.get("Content-Type", "")
      and "p12.test_export" in r.text, r.status_code)
r = s_adm.get(f"{BASE}/admin/audit-logs/export.csv?action=p12.test_export")
check("audit export respects action filter",
      r.status_code == 200 and "p12.test_export" in r.text, r.status_code)
r = s_adm.get(f"{BASE}/admin/audit-logs/export.csv?action=zzz_no_match")
check("audit export empty on no match",
      r.status_code == 200 and "p12.test_export" not in r.text, r.status_code)
r = s_fac.get(f"{BASE}/admin/audit-logs/export.csv")
check("faculty blocked from audit export", r.status_code == 403,
      r.status_code)
r = s_adm.get(f"{BASE}/admin/audit-logs")
check("audit page has export button",
      r.status_code == 200 and "Export CSV" in r.text, r.status_code)

# ---------------------------------------------------------------- 13. OAuth stub

r = s_adm.get(f"{BASE}/admin/integrations")
check("integrations page marked coming soon",
      r.status_code == 200 and "coming soon" in r.text.lower()
      and "Google OAuth" in r.text, r.status_code)
r = s_adm.post(f"{BASE}/admin/integrations",
               data={"google_client_id": "test-client-id.apps.googleusercontent.com",
                     "google_client_secret": "shhh-secret-123"},
               allow_redirects=True)
check("oauth settings save",
      r.status_code == 200 and "test-client-id" in r.text, r.status_code)
check("oauth secret never echoed back",
      "shhh-secret-123" not in r.text)
r = s_anon.get(f"{BASE}/login")
check("login shows disabled Google button",
      r.status_code == 200 and "coming soon" in r.text.lower()
      and "disabled" in r.text, r.status_code)
r = s_fac.get(f"{BASE}/admin/integrations")
check("faculty blocked from integrations", r.status_code == 403,
      r.status_code)

# ---------------------------------------------------------------- 14. role gates on remaining endpoints

r = s_anon.get(f"{BASE}/admin/tenants", allow_redirects=False)
check("anonymous redirected from tenants",
      r.status_code in (301, 302), r.status_code)
r = s_anon.get(f"{BASE}/admin/branding", allow_redirects=False)
check("anonymous redirected from branding",
      r.status_code in (301, 302), r.status_code)
r = s_stu.get(f"{BASE}/admin/audit-logs/export.csv")
check("student blocked from audit export", r.status_code == 403,
      r.status_code)
r = s_anon.get(f"{BASE}/learn/recommended", allow_redirects=False)
check("anonymous redirected from recommended",
      r.status_code in (301, 302), r.status_code)

print(f"\n==== Phase 12: {passed} passed, {failed} failed ====")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
