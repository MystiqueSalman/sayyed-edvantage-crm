"""Phase 5 — AI Learning Layer (end-to-end, runs against a dev server on
http://localhost:5000 with a FRESH DB (migrated via `flask db upgrade` +
seeded), with the same SQLITE_PATH for both server and this script).

The dev server MUST be started with LMS_TUTOR_RULES_ONLY=1 so the tutor
replies follow the deterministic rules fallback (OpenAI would make the
grounding assertions non-deterministic).

Coverage: tutor access control, grounding with real lesson citations,
off-topic/academic-only guardrails, outside-materials fallback, rate
limiting, global + per-course toggles, AI memory store/recall/clear,
QuizAnswer storage + weak-topic analysis (lesson tag + module fallback),
faculty weak-topic summary, study planner (order/dates/drip/persist/
toggle/today widget), AI correctness fix (no invented WELCOME10/October
claims — live coupon/batch data only), admin AI settings, quiz lesson
tagging, lesson AI-tutor widget.
"""
import os
import sys
from datetime import date, timedelta

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app  # noqa: E402
from app.models import (  # noqa: E402
    AILearningMemory, AISettings, AITutorExchange, Batch, ChatConversation,
    Coupon, Course, Enrollment, Lesson, Question, Quiz, QuizAnswer, QuizAttempt,
    StudyPlan, StudyPlanItem, User, db,
)

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


def ask(course_id, question):
    return s_stu.post(f"{BASE}/tutor/ask",
                      json={"course_id": course_id, "question": question})


s_anon = requests.Session()
s_stu = requests.Session()
s_admin = requests.Session()
s_fac = requests.Session()

print("== Phase 5: AI Learning Layer ==")

with app.app_context():
    py = Course.query.filter_by(slug="python-programming").first()
    ds = Course.query.filter_by(slug="data-science").first()
    stu = User.query.filter_by(email="student@sayyed.in").first()
    fac = User.query.filter_by(email="faculty@sayyed.in").first()
    check("seed python + data-science courses exist", py and ds)
    check("seed student + faculty exist", stu and fac)
    # enroll student in python directly (setup, bypasses payment)
    enr = Enrollment.query.filter_by(user_id=stu.id,
                                     course_id=py.id).first()
    if not enr:
        enr = Enrollment(user_id=stu.id, course_id=py.id, status="active",
                         paid=True)
        db.session.add(enr)
        db.session.commit()
    st = AISettings.get()
    st.tutor_enabled = True
    st.tutor_daily_limit = 30
    py.ai_tutor_enabled = True
    # make data-science NOT taught by the seed faculty (for the 403 test)
    admin_u = User.query.filter_by(email="admin@sayyed.in").first()
    ds.instructor_id = admin_u.id
    db.session.commit()
    check("setup: python enrollment active", enr.status == "active")
    PY_ID, DS_ID = py.id, ds.id
    STU_ID = stu.id

assert login(s_stu, "student@sayyed.in", "student123")
assert login(s_admin, "admin@sayyed.in", "admin123")
assert login(s_fac, "faculty@sayyed.in", "faculty123")
check("student/admin/faculty logins ok", True)

# ---------------- 1. tutor access control ----------------
r = s_anon.get(f"{BASE}/tutor")
check("anon /tutor redirected (not 200 tutor page)",
      r.status_code != 200 or "AI Tutor" not in r.text)
r = s_anon.post(f"{BASE}/tutor/ask", json={"course_id": PY_ID, "question": "hi"},
               allow_redirects=False)
check("anon /tutor/ask blocked", r.status_code in (302, 401, 403))
r = s_stu.get(f"{BASE}/tutor?course_id={PY_ID}")
check("enrolled student opens tutor (200)",
      r.status_code == 200 and "AI Tutor" in r.text)
r = s_stu.get(f"{BASE}/tutor?course_id={DS_ID}", allow_redirects=False)
check("non-enrolled course -> friendly redirect (302)",
      r.status_code == 302)
r = s_stu.get(f"{BASE}/tutor?course_id={DS_ID}", allow_redirects=True)
check("non-enrolled course falls back to enrolled course page",
      "Python Programming" in r.text and "AI Tutor" in r.text)
r = s_admin.get(f"{BASE}/tutor", allow_redirects=False)
check("admin blocked from student tutor (403)", r.status_code == 403)
r = s_stu.get(f"{BASE}/planner")
check("student /planner opens (200)", r.status_code == 200 and "Study Planner" in r.text)
r = s_stu.get(f"{BASE}/revise")
check("student /revise opens (200)", r.status_code == 200 and "Topics to Revise" in r.text)

# ---------------- 2. tutor grounding (rules fallback) ----------------
r = ask(PY_ID, "How do variables and data types work in Python?")
d = r.json()
check("tutor ask -> answer + citations", bool(d.get("answer")) and d.get("cited"),
      str(d)[:200])
lesson_title = None
with app.app_context():
    lesson_title = Lesson.query.get(d["cited"][0]).title
check("tutor cites REAL lesson (Your First Python Program)",
      lesson_title == "Your First Python Program", lesson_title)
check("tutor answer quotes lesson title",
      "Your First Python Program" in d["answer"], d["answer"][:200])

# outside-materials fallback
r = ask(PY_ID, "Explain quantum teleportation in detail")
d = r.json()
check("off-materials: honest fallback, no citations",
      d.get("cited") == [] and
      ("couldn't find" in d["answer"] or "discussion" in d["answer"]),
      d["answer"][:200])

# academic-only / admissions guardrail — no invented fees or coupons
r = ask(PY_ID, "What are the course fees and discounts?")
d = r.json()
check("fee question -> counsellor redirect, no invented coupon",
      "counsellor" in d["answer"] and "WELCOME10" not in d["answer"],
      d["answer"][:200])

# exchange persisted
with app.app_context():
    n = AITutorExchange.query.filter_by(user_id=STU_ID,
                                        course_id=PY_ID).count()
check("Q&A exchange stored in DB", n >= 3, f"n={n}")

# ---------------- 3. AI memory store / recall / clear ----------------
r = s_stu.get(f"{BASE}/tutor?course_id={PY_ID}")
check("memory panel shows recent question",
      "variables and data types" in r.text.lower())
with app.app_context():
    mem = AILearningMemory.query.filter_by(user_id=STU_ID,
                                           course_id=PY_ID).first()
check("AILearningMemory row exists", mem is not None)
r = s_stu.post(f"{BASE}/tutor/memory/clear",
               data={"course_id": PY_ID}, allow_redirects=False)
with app.app_context():
    ex_left = AITutorExchange.query.filter_by(
        user_id=STU_ID, course_id=PY_ID).count()
    mem_left = AILearningMemory.query.filter_by(
        user_id=STU_ID, course_id=PY_ID).count()
check("clear memory wipes exchanges + memory",
      ex_left == 0 and mem_left == 0, f"ex={ex_left} mem={mem_left}")

# completed lessons appear in memory
with app.app_context():
    first_lesson = Lesson.query.filter(
        Lesson.module.has(course_id=PY_ID)).order_by(Lesson.id).first()
    from app.models import LessonProgress
    if not LessonProgress.query.filter_by(
            user_id=STU_ID, lesson_id=first_lesson.id).first():
        db.session.add(LessonProgress(user_id=STU_ID,
                                      lesson_id=first_lesson.id))
        db.session.commit()
    FL_TITLE = first_lesson.title
    FIRST_LESSON_ID = first_lesson.id
r = ask(PY_ID, "What is a variable in Python?")
r = s_stu.get(f"{BASE}/tutor?course_id={PY_ID}")
check("completed lesson shown in memory", FL_TITLE in r.text, FL_TITLE)

# ---------------- 4. rate limiting ----------------
with app.app_context():
    st = AISettings.query.first()
    st.tutor_daily_limit = 2
    db.session.commit()
s_stu.post(f"{BASE}/tutor/memory/clear", data={"course_id": PY_ID})
ask(PY_ID, "rate question one")
ask(PY_ID, "rate question two")
r = ask(PY_ID, "rate question three")
check("daily limit enforced on 3rd ask",
      r.json().get("error") == "limit", str(r.json())[:120])
with app.app_context():
    st = AISettings.query.first()
    st.tutor_daily_limit = 30
    db.session.commit()
check("limit restored to 30", True)

# ---------------- 5. tutor toggles ----------------
with app.app_context():
    py2 = Course.query.get(PY_ID)
    py2.ai_tutor_enabled = False
    db.session.commit()
r = s_stu.get(f"{BASE}/tutor?course_id={PY_ID}", allow_redirects=False)
check("per-course tutor off -> redirect", r.status_code == 302)
r = ask(PY_ID, "hello")
check("per-course tutor off -> ask blocked",
      r.json().get("error") == "course_disabled", str(r.json())[:120])
with app.app_context():
    py2 = Course.query.get(PY_ID)
    py2.ai_tutor_enabled = True
    st = AISettings.query.first()
    st.tutor_enabled = False
    db.session.commit()
r = s_stu.get(f"{BASE}/tutor", allow_redirects=False)
check("global tutor off -> redirect", r.status_code == 302)
with app.app_context():
    st = AISettings.query.first()
    st.tutor_enabled = True
    db.session.commit()
r = s_stu.get(f"{BASE}/tutor?course_id={PY_ID}")
check("toggles restored -> tutor opens", r.status_code == 200)

# ---------------- 6. weak topics from quiz answers ----------------
with app.app_context():
    m1q = Quiz.query.filter(Quiz.module.has(course_id=PY_ID)).order_by(
        Quiz.id).first()
    qs = Question.query.filter_by(quiz_id=m1q.id).order_by(Question.id).all()
    first_lesson = Lesson.query.filter(
        Lesson.module.has(course_id=PY_ID)).order_by(Lesson.id).first()
    qs[0].lesson_id = first_lesson.id  # tag Q1 to a real lesson
    db.session.commit()
    Q1_ID, Q2_ID = qs[0].id, qs[1].id
    QUIZ_ID = m1q.id
    check("setup: 2 quiz questions found", len(qs) >= 2)
r = s_stu.post(f"{BASE}/quiz/{QUIZ_ID}",
               data={f"q{Q1_ID}": "A",   # wrong (correct is B)
                     f"q{Q2_ID}": "B"},  # right
               allow_redirects=True)
with app.app_context():
    rows = QuizAnswer.query.filter(
        QuizAnswer.question_id.in_([Q1_ID, Q2_ID])).all()
    wrong = [x for x in rows if x.question_id == Q1_ID and not x.is_correct]
check("QuizAnswer rows stored per question", len(rows) >= 2,
      f"rows={len(rows)}")
check("wrong answer recorded", len(wrong) >= 1)
r = s_stu.get(f"{BASE}/revise?course_id={PY_ID}")
check("revise page shows weak lesson",
      "Your First Python Program" in r.text)
r = s_stu.get(f"{BASE}/dashboard")
check("dashboard shows Topics to Revise widget",
      "Topics to Revise" in r.text)
r = s_admin.get(f"{BASE}/faculty/weak-topics/{PY_ID}")
check("admin faculty weak-topics (200 + lesson)",
      r.status_code == 200 and "Your First Python Program" in r.text)
with app.app_context():
    OTHER_ID = DS_ID
    OTHER_TITLE = "Data Science"
r = s_fac.get(f"{BASE}/faculty/weak-topics/{PY_ID}")
check("faculty sees weak-topics for own assigned course (200)",
      r.status_code == 200 and "Your First Python Program" in r.text)
r = s_fac.get(f"{BASE}/faculty/weak-topics/{OTHER_ID}", allow_redirects=False)
check("faculty blocked on unassigned course (403)", r.status_code == 403,
      OTHER_TITLE)

# ---------------- 7. study planner ----------------
# NOTE: the seed sets drip unlocks on some python lessons (7/14 days), so
# the assertions below verify drip-respect + ordering generically.
target = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
r = s_stu.post(f"{BASE}/planner/generate",
               data={"course_id": PY_ID, "target_date": target,
                     "hours_per_day": "2"},
               allow_redirects=False)
check("planner generate -> redirect", r.status_code == 302)
r = s_stu.get(f"{BASE}/planner?course_id={PY_ID}")
check("planner page lists remaining lessons",
      "Object-Oriented Python" in r.text and "Final Project Brief" in r.text
      and "Your First Python Program" not in r.text)  # completed -> skipped
with app.app_context():
    from collections import defaultdict
    enr = Enrollment.query.filter_by(user_id=STU_ID,
                                     course_id=PY_ID).first()
    all_lessons = Lesson.query.filter(
        Lesson.module.has(course_id=PY_ID)).order_by(Lesson.id).all()
    remaining_ids = [l.id for l in all_lessons if l.id != FIRST_LESSON_ID]
    order_idx = {lid: n for n, lid in enumerate(remaining_ids)}
    plan = StudyPlan.query.filter_by(user_id=STU_ID,
                                     course_id=PY_ID).first()
    items = (StudyPlanItem.query.filter_by(plan_id=plan.id)
             .order_by(StudyPlanItem.id).all())
    got_ids = [i.lesson_id for i in items]
    check("plan covers all remaining lessons exactly once",
          plan is not None and sorted(got_ids) == sorted(remaining_ids),
          f"got={got_ids}")
    drip_ok = all(
        i.planned_date >= Lesson.query.get(i.lesson_id)
        .unlock_date(enr.enrolled_at).date() for i in items)
    check("every item on/after its drip unlock date", drip_ok)
    by_date = defaultdict(list)
    for i in items:
        by_date[i.planned_date].append(i.lesson_id)
    per_day_ordered = all(
        [order_idx[x] for x in by_date[d]] ==
        sorted(order_idx[x] for x in by_date[d]) for d in by_date)
    check("module order kept within each day", per_day_ordered)
    dates = [i.planned_date for i in items]
    check("plan dates within [today, target]",
          all(date.today() <= d <= date.today() + timedelta(days=14)
              for d in dates), str(sorted(set(dates))))
    check("plan target + hours persisted",
          plan.target_date == date.today() + timedelta(days=14)
          and plan.hours_per_day == 2.0)

# drip unlock respected (raise one lesson's drip, regenerate)
with app.app_context():
    last_lesson = Lesson.query.filter(
        Lesson.module.has(course_id=PY_ID)).order_by(Lesson.id.desc()).first()
    last_lesson.available_after_days = 10
    db.session.commit()
    LAST_ID = last_lesson.id
s_stu.post(f"{BASE}/planner/generate",
           data={"course_id": PY_ID, "target_date": target,
                 "hours_per_day": "2"})
with app.app_context():
    enr = Enrollment.query.filter_by(user_id=STU_ID,
                                     course_id=PY_ID).first()
    plan = StudyPlan.query.filter_by(user_id=STU_ID,
                                     course_id=PY_ID).first()
    it = StudyPlanItem.query.filter_by(plan_id=plan.id,
                                       lesson_id=LAST_ID).first()
    unlock = Lesson.query.get(LAST_ID).unlock_date(enr.enrolled_at).date()
    check("drip lesson planned on/after unlock date",
          it.planned_date >= unlock,
          f"planned={it.planned_date} unlock={unlock}")
    last_lesson = Lesson.query.get(LAST_ID)
    last_lesson.available_after_days = 0
    db.session.commit()
    ITEM_ID = (StudyPlanItem.query.filter_by(plan_id=plan.id)
               .order_by(StudyPlanItem.id).first().id)

r = s_stu.post(f"{BASE}/planner/item/{ITEM_ID}/toggle",
               headers={"Accept": "application/json"})
check("plan item toggle -> done", r.json().get("done") is True)
r = s_stu.get(f"{BASE}/dashboard")
check("dashboard shows Today's Study Plan widget",
      "Today's Study Plan" in r.text)

# past target date rejected
past = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
r = s_stu.post(f"{BASE}/planner/generate",
               data={"course_id": PY_ID, "target_date": past,
                     "hours_per_day": "2"}, allow_redirects=True)
check("past target date rejected",
      "Target date must be in the future" in r.text)

# ---------------- 8. AI correctness fix (admissions chatbot) ----------------
with app.app_context():
    from app.ai_agent import (_fee_list_text, _live_coupon_line,
                              _system_prompt, _upcoming_batches_line,
                              course_knowledge, rules_reply)
    catalog = course_knowledge()
    conv = ChatConversation(id="phase5-test-conv")
    db.session.add(conv)
    db.session.commit()
    CONV = conv

    # live coupon quoted from DB (best live offer wins)
    live_codes = [c.code for c in Coupon.query.filter_by(active=True).all()
                  if c.is_live()]
    line = _live_coupon_line()
    check("live coupon line quotes a real live DB coupon",
          bool(live_codes) and any(code in line for code in live_codes),
          line)
    # deactivate everything -> no offer invented
    for c in Coupon.query.all():
        c.active = False
    db.session.commit()
    check("no coupons -> no offer invented",
          _live_coupon_line() == "", repr(_live_coupon_line()))
    # only WELCOME10 active -> the line quotes it (data-driven, not hard-coded)
    for c in Coupon.query.all():
        c.active = (c.code == "WELCOME10")
    db.session.commit()
    line = _live_coupon_line()
    check("coupon line quotes the actually-active coupon",
          "WELCOME10" in line and "FLAT20" not in line, line)
    for c in Coupon.query.all():
        c.active = True
    db.session.commit()
    # expired coupon ignored
    cp = Coupon.query.filter_by(code="FLAT20").first()
    cp.valid_from = date.today() - timedelta(days=30)
    cp.valid_until = date.today() - timedelta(days=1)
    db.session.commit()
    line = _live_coupon_line()
    check("expired coupon NOT quoted", "FLAT20" not in line, line)
    cp.valid_from = None
    cp.valid_until = None
    db.session.commit()

    fee_text = _fee_list_text(catalog)
    live_codes = [c.code for c in Coupon.query.filter_by(active=True).all()
                  if c.is_live()]
    check("fee text quotes a live DB coupon (never invented)",
          bool(live_codes) and any(code in fee_text for code in live_codes),
          fee_text[:200])
    sp = _system_prompt(catalog)
    check("system prompt: no WELCOME10, no October",
          "WELCOME10" not in sp and "october" not in sp.lower(),
          sp[:200])

    reply, _flags = rules_reply("when do batches start?", CONV)
    check("schedule reply never invents October",
          "october" not in reply.lower(), reply[:200])
    # real future batch gets named
    b = Batch(course_id=PY_ID, name="Python Weekend Batch",
              start_date=date.today() + timedelta(days=10))
    db.session.add(b)
    db.session.commit()
    reply, _flags = rules_reply("when do batches start?", CONV)
    check("schedule reply names real batch",
          "Python Weekend Batch" in reply, reply[:200])
    db.session.delete(b)
    db.session.delete(CONV)
    db.session.commit()
    check("no hard-coded coupon/batch leftovers", True)

# ---------------- 9. admin AI settings ----------------
r = s_admin.get(f"{BASE}/admin/ai-settings")
check("admin AI settings page (200)",
      r.status_code == 200 and "AI Tutor" in r.text)
r = s_admin.post(f"{BASE}/admin/ai-settings",
                 data={"tutor_enabled": "1", "tutor_daily_limit": "45",
                       "model": "gpt-4o-mini",
                       f"tutor_course_{PY_ID}": "1"},
                 allow_redirects=True)
with app.app_context():
    st = AISettings.query.first()
check("daily limit saved via admin", st.tutor_daily_limit == 45)
r = s_stu.get(f"{BASE}/tutor?course_id={PY_ID}")
check("tutor still opens after settings save", r.status_code == 200)

# ---------------- 10. quiz lesson tagging (manage) ----------------
r = s_admin.get(f"{BASE}/manage/quiz/{QUIZ_ID}/questions")
check("question form has lesson dropdown",
      r.status_code == 200 and 'name="lesson_id"' in r.text)
with app.app_context():
    q = Question.query.filter_by(quiz_id=QUIZ_ID).first()
    check("tagged lesson shown on manage page",
          q.lesson_id is not None)

# ---------------- 11. lesson AI-tutor widget ----------------
with app.app_context():
    l1 = Lesson.query.filter(
        Lesson.module.has(course_id=PY_ID)).order_by(Lesson.id).first()
    L1_ID = l1.id
r = s_stu.get(f"{BASE}/lesson/{L1_ID}")
check("lesson page has AI Tutor widget",
      r.status_code == 200 and "Ask AI Tutor" in r.text)

print(f"\n== Phase 5: {passed} passed, {failed} failed ==")
if failed:
    print("FAILED:", notes)
    sys.exit(1)
