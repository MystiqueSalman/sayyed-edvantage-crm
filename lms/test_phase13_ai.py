"""Phase 13 Stream 3 — AI extras (end-to-end).

In-process via Flask test_client (blueprint registered here, tables created
via db.create_all since the coordinator ships the combined Alembic revision
separately). LLM is ALWAYS mocked — ai_generate is patched, never called.

Coverage: content assistant saves drafts (always 'draft', labeled),
quiz-draft copyable-text behavior, no-key graceful degradation, evaluator
pending_review -> student invisible -> approve -> visible, reject path,
at-risk rules fire/clear, memory refresh + page + context text.
"""
import os
import sys
from datetime import datetime, timedelta, date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402

app = create_app()
flask_app = app
from app.ai13 import ai13_bp  # noqa: E402
if "ai13" not in flask_app.blueprints:  # create_app() now registers all Phase 13 blueprints
    flask_app.register_blueprint(ai13_bp)
with flask_app.app_context():
    import app.models13_ai  # noqa: F401  (register tables)
    db.create_all()
client = flask_app.test_client()

from app.models import (Assignment, Course, Enrollment, Lesson,  # noqa: E402
                        LessonProgress, LiveSession, Module, Project,
                        ProjectSubmission, Quiz, QuizAttempt,
                        SessionAttendance, Submission, User)
from app.models13_ai import (AiDraft13, AtRiskFlag13, ProjectEvaluation13,  # noqa: E402
                             Rubric13, StudentMemory13)
from app.memory13 import get_memory, memory_context_text  # noqa: E402

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


def login(email, password):
    s = client.__class__(flask_app)
    r = s.post("/login", data={"email": email, "password": password},
               follow_redirects=True)
    assert "Logout" in r.get_data(as_text=True), f"login failed for {email}"
    return s


# ------------------------------------------------------------------ setup
with flask_app.app_context():
    def mkuser(name, email, pw, role):
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(name=name, email=email, role=role)
            u.set_password(pw)
            db.session.add(u)
        return u

    fac = mkuser("Fac Thirteen", "fac13@sayyed.in", "pw123", "faculty")
    stu = mkuser("Stu Thirteen", "stu13@sayyed.in", "pw123", "student")
    stu2 = mkuser("Stu Healthy", "stu13b@sayyed.in", "pw123", "student")
    coun = mkuser("Coun Thirteen", "coun13@sayyed.in", "pw123", "counsellor")
    db.session.flush()
    for u in (fac, stu, stu2, coun):
        db.session.refresh(u)

    course = Course(title="AI13 Test Course", slug="ai13-test", fee=10000,
                    instructor_id=fac.id)
    db.session.add(course)
    db.session.flush()
    mod = Module(course_id=course.id, title="Python Basics", position=0)
    db.session.add(mod)
    db.session.flush()
    les1 = Lesson(module_id=mod.id, title="Variables and types", position=0,
                  kind="text", body="x = 1")
    les2 = Lesson(module_id=mod.id, title="Loops", position=1, kind="text",
                  body="for i in range(3)")
    db.session.add_all([les1, les2])
    quiz = Quiz(module_id=mod.id, title="Basics quiz")
    db.session.add(quiz)
    assign = Assignment(course_id=course.id, title="Overdue homework",
                        due_date=date.today() - timedelta(days=1))
    db.session.add(assign)
    proj = Project(course_id=course.id, title="Capstone Web App",
                   max_marks=100, description="Build a small web app.")
    db.session.add(proj)
    proj2 = Project(course_id=course.id, title="Second Project",
                    max_marks=50, description="Another brief.")
    db.session.add(proj2)
    db.session.flush()
    for o in (course, mod, les1, les2, quiz, assign, proj, proj2):
        db.session.refresh(o)

    # enrollments
    db.session.add(Enrollment(user_id=stu.id, course_id=course.id,
                              status="active"))
    db.session.add(Enrollment(user_id=stu2.id, course_id=course.id,
                              status="active"))
    # lesson progress (stu completed one lesson)
    db.session.add(LessonProgress(user_id=stu.id, lesson_id=les1.id))
    # live sessions x3 + attendance: stu 1/3 present, stu2 3/3 present
    sess = []
    for i in range(3):
        s = LiveSession(course_id=course.id, title=f"Live {i+1}",
                        room_name=f"ai13-room-{i+1}",
                        starts_at=datetime.utcnow() - timedelta(days=10 - i))
        db.session.add(s)
        sess.append(s)
    db.session.flush()
    db.session.add(SessionAttendance(session_id=sess[0].id, user_id=stu.id,
                                     status="present"))
    db.session.add(SessionAttendance(session_id=sess[1].id, user_id=stu.id,
                                     status="absent"))
    db.session.add(SessionAttendance(session_id=sess[2].id, user_id=stu.id,
                                     status="absent"))
    for s in sess:
        db.session.add(SessionAttendance(session_id=s.id, user_id=stu2.id,
                                         status="present"))
    # assignment submitted only by stu2 -> stu misses the deadline
    db.session.add(Submission(assignment_id=assign.id, user_id=stu2.id,
                              note="done"))
    # quiz attempts: stu declining 90..40, stu2 stable
    def attempts(user, scores):
        for i, sc in enumerate(scores):
            t = datetime.utcnow() - timedelta(days=6 - i)
            db.session.add(QuizAttempt(quiz_id=quiz.id, user_id=user.id,
                                       score=sc, total=100, taken_at=t,
                                       started_at=t, submitted_at=t))
    attempts(stu, [90, 85, 88, 55, 45, 40])
    attempts(stu2, [78, 80, 82, 84, 85, 86])
    # project submissions
    sub1 = ProjectSubmission(project_id=proj.id, user_id=stu.id,
                             notes="Built with Flask.", project_url="")
    db.session.add(sub1)
    sub2 = ProjectSubmission(project_id=proj2.id, user_id=stu.id,
                             notes="Second attempt notes.", project_url="")
    db.session.add(sub2)
    db.session.commit()
    for o in (sub1, sub2):
        db.session.refresh(o)
    IDS = {"fac": fac.id, "stu": stu.id, "stu2": stu2.id,
           "coun": coun.id, "course": course.id, "sub1": sub1.id,
           "sub2": sub2.id, "proj": proj.id, "assign": assign.id}

s_fac = login("fac13@sayyed.in", "pw123")
s_stu = login("stu13@sayyed.in", "pw123")
s_stu2 = login("stu13b@sayyed.in", "pw123")
s_coun = login("coun13@sayyed.in", "pw123")

# ------------------------------------------------- 1. content assistant --
with patch("app.ai13.ai_generate", return_value="MOCKED OUTLINE") as m:
    r = s_fac.post("/faculty/ai-assistant",
                   data={"course_id": IDS["course"], "kind": "lesson-outline",
                         "topic": "List comprehensions"},
                   follow_redirects=False)
    check("assistant POST redirects", r.status_code in (301, 302, 303),
          r.status_code)
    check("ai_generate called with grounded prompt",
          m.called and "Variables and types" in m.call_args[0][1],
          str(m.call_args)[:120] if m.called else "not called")
with flask_app.app_context():
    d = AiDraft13.query.filter_by(topic="List comprehensions").first()
    check("draft saved", d is not None)
    check("draft ALWAYS 'draft' status", d and d.status == "draft", d.status if d else "")
    check("draft content is the AI text", d and d.content == "MOCKED OUTLINE")
    check("draft labeled kind", d and d.kind == "lesson-outline")
    check("draft linked to faculty+course",
          d and d.faculty_id == IDS["fac"] and d.course_id == IDS["course"])
    draft_id = d.id
r = s_fac.get("/faculty/ai-assistant")
t = r.get_data(as_text=True)
check("draft list shows AI banner",
      "AI-generated draft — review before use" in t)
check("draft list shows kind tag", "lesson-outline" in t)

# quiz-draft -> copyable text, no auto-import
with patch("app.ai13.ai_generate", return_value="Q1. MOCK QUESTION"):
    s_fac.post("/faculty/ai-assistant",
               data={"course_id": IDS["course"], "kind": "quiz-draft",
                     "topic": "Loops"})
r = s_fac.get("/faculty/ai-assistant/draft/999999")
check("draft detail 404 for missing", r.status_code == 404)
with flask_app.app_context():
    qd = AiDraft13.query.filter_by(kind="quiz-draft").first()
r = s_fac.get(f"/faculty/ai-assistant/draft/{qd.id}")
t = r.get_data(as_text=True)
check("quiz draft detail renders", r.status_code == 200, r.status_code)
check("quiz draft shows no-import notice",
      "no draft/inactive flag" in t)
check("quiz draft shows copyable text",
      "Q1. MOCK QUESTION" in t and "<textarea" in t)
with flask_app.app_context():
    check("no Quiz row created from quiz draft",
          Quiz.query.filter(Quiz.title.contains("MOCK")).count() == 0)

# edit keeps draft status
r = s_fac.post(f"/faculty/ai-assistant/draft/{draft_id}/edit",
               data={"topic": "List comprehensions v2",
                     "content": "edited content"},
               follow_redirects=True)
with flask_app.app_context():
    d = db.session.get(AiDraft13, draft_id)
    check("draft edit updates", d.topic == "List comprehensions v2")
    check("draft edit keeps status draft", d.status == "draft")

# student is forbidden from faculty pages
r = s_stu.get("/faculty/ai-assistant")
check("student 403 on ai-assistant", r.status_code == 403, r.status_code)

# no-key degradation: never traceback, clear message, nothing saved
os.environ.pop("OPENAI_API_KEY", None)
with flask_app.app_context():
    before = AiDraft13.query.count()
r = s_fac.post("/faculty/ai-assistant",
               data={"course_id": IDS["course"], "kind": "assignment-draft",
                     "topic": "No key topic"},
               follow_redirects=True)
t = r.get_data(as_text=True)
check("no-key shows AI unavailable message", "AI unavailable" in t)
with flask_app.app_context():
    check("no-key saves nothing", AiDraft13.query.count() == before)

# delete
r = s_fac.post(f"/faculty/ai-assistant/draft/{draft_id}/delete",
               follow_redirects=True)
with flask_app.app_context():
    check("draft delete works", db.session.get(AiDraft13, draft_id) is None)

# ------------------------------------------------- 2. AI evaluator --------
r = s_fac.post("/faculty/rubrics",
               data={"name": "Capstone rubric",
                     "course_id": IDS["course"],
                     "project_id": IDS["proj"],
                     "criteria": "Quality : 3\nCompleteness : 4"},
               follow_redirects=True)
with flask_app.app_context():
    rub = Rubric13.query.filter_by(name="Capstone rubric").first()
    check("rubric created", rub is not None)
    check("rubric criteria parsed",
          rub and rub.criteria == [{"name": "Quality", "weight": 3.0},
                                   {"name": "Completeness", "weight": 4.0}],
          str(rub.criteria) if rub else "")
    check("rubric attached to project",
          rub and rub.project_id == IDS["proj"])
    rub_id = rub.id

llm_json = ('{"scores": {"Quality": 8, "Completeness": 7}, '
            '"feedback": "Good job overall."}')
with patch("app.ai13.ai_generate", return_value=llm_json):
    r = s_fac.post(f"/faculty/evaluate/{IDS['sub1']}/ai",
                   data={"rubric_id": rub_id}, follow_redirects=False)
    check("AI evaluate POST redirects", r.status_code in (301, 302, 303),
          r.status_code)
with flask_app.app_context():
    ev = (ProjectEvaluation13.query
          .filter_by(project_submission_id=IDS["sub1"])
          .order_by(ProjectEvaluation13.id.desc()).first())
    check("evaluation row created", ev is not None)
    check("evaluation is pending_review", ev and ev.status == "pending_review",
          ev.status if ev else "")
    check("evaluation scores parsed",
          ev and ev.scores == {"Quality": 8.0, "Completeness": 7.0},
          str(ev.scores) if ev else "")
    check("evaluation feedback saved",
          ev and ev.feedback_text == "Good job overall.")
    sub = db.session.get(ProjectSubmission, IDS["sub1"])
    check("submission moved to under_review", sub.status == "under_review",
          sub.status)
    check("marks NOT set before approval", sub.marks is None)
    ev_id = ev.id

# student cannot see the pending evaluation
r = s_stu.get("/student/evaluations")
t = r.get_data(as_text=True)
check("student evaluations page 200", r.status_code == 200, r.status_code)
check("pending evaluation hidden from student",
      "Capstone Web App" not in t)
check("student page notes faculty approval only",
      "approved by faculty" in t)

# faculty review queue shows it
r = s_fac.get("/faculty/evaluations")
t = r.get_data(as_text=True)
check("review queue 200", r.status_code == 200, r.status_code)
check("review queue lists pending", "Capstone Web App" in t)
check("review queue warns students can't see",
      "Students cannot see them" in t)

# approve with corrected scores
r = s_fac.post(f"/faculty/evaluations/{ev_id}/review",
               data={"action": "approve", "feedback": "Great work",
                     "score_Quality": "9", "score_Completeness": "8"},
               follow_redirects=True)
with flask_app.app_context():
    ev = db.session.get(ProjectEvaluation13, ev_id)
    sub = db.session.get(ProjectSubmission, IDS["sub1"])
    check("evaluation approved", ev.status == "approved", ev.status)
    check("approval records reviewer",
          ev.reviewed_by == IDS["fac"] and ev.reviewed_at is not None)
    # weights 3+4=7: (9/10*3 + 8/10*4)/7*100 = 84.2857 -> 84.29
    check("marks computed from weighted scores", sub.marks == 84.29,
          f"got {sub.marks}")
    check("submission evaluated+visible", sub.status == "evaluated", sub.status)
    check("feedback copied to submission", sub.feedback == "Great work")
r = s_stu.get("/student/evaluations")
t = r.get_data(as_text=True)
check("approved evaluation visible to student",
      "Capstone Web App" in t and "Great work" in t)

# reject path: second submission -> AI evaluate -> reject
with flask_app.app_context():
    rub2 = Rubric13(name="Second rubric", course_id=IDS["course"],
                    project_id=None, criteria=[{"name": "Effort", "weight": 1}],
                    created_by=IDS["fac"])
    db.session.add(rub2)
    db.session.commit()
    rub2_id = rub2.id
with patch("app.ai13.ai_generate",
           return_value='{"scores": {"Effort": 5}, "feedback": "Okay."}'):
    s_fac.post(f"/faculty/evaluate/{IDS['sub2']}/ai",
               data={"rubric_id": rub2_id})
with flask_app.app_context():
    ev2 = (ProjectEvaluation13.query
           .filter_by(project_submission_id=IDS["sub2"])
           .order_by(ProjectEvaluation13.id.desc()).first())
    ev2_id = ev2.id
r = s_fac.post(f"/faculty/evaluations/{ev2_id}/review",
               data={"action": "reject", "feedback": "Okay."},
               follow_redirects=True)
with flask_app.app_context():
    ev2 = db.session.get(ProjectEvaluation13, ev2_id)
    sub2 = db.session.get(ProjectSubmission, IDS["sub2"])
    check("evaluation rejected", ev2.status == "rejected", ev2.status)
    check("rejected submission back to manual queue",
          sub2.status == "submitted", sub2.status)
r = s_stu.get("/student/evaluations")
check("rejected evaluation hidden from student",
      "Second Project" not in r.get_data(as_text=True))

# AI unavailable on evaluate: no row, no crash
os.environ.pop("OPENAI_API_KEY", None)
with flask_app.app_context():
    before = ProjectEvaluation13.query.count()
r = s_fac.post(f"/faculty/evaluate/{IDS['sub1']}/ai",
               data={"rubric_id": rub_id}, follow_redirects=True)
check("evaluate no-key shows AI unavailable",
      "AI unavailable" in r.get_data(as_text=True))
with flask_app.app_context():
    check("evaluate no-key saves nothing",
          ProjectEvaluation13.query.count() == before)

# ------------------------------------------------- 3. at-risk ------------
r = s_coun.post("/counsellor/at-risk/recompute", follow_redirects=True)
check("recompute redirects", r.status_code == 200, r.status_code)
with flask_app.app_context():
    flag = AtRiskFlag13.query.filter_by(user_id=IDS["stu"],
                                        resolved=False).first()
    check("at-risk flag created for struggling student", flag is not None)
    reasons = " ".join(flag.reasons) if flag else ""
    check("flag has low_attendance reason", "low_attendance" in reasons,
          reasons)
    check("flag has missed_deadlines:1", "missed_deadlines:1" in reasons,
          reasons)
    check("flag has quiz_trend:down", "quiz_trend:down" in reasons, reasons)
    check("no flag for healthy student",
          AtRiskFlag13.query.filter_by(user_id=IDS["stu2"],
                                       resolved=False).count() == 0)
    flag_id = flag.id

# recompute is idempotent (no duplicate open flags)
r = s_coun.post("/counsellor/at-risk/recompute", follow_redirects=True)
with flask_app.app_context():
    check("recompute does not duplicate flags",
          AtRiskFlag13.query.filter_by(user_id=IDS["stu"],
                                       resolved=False).count() == 1)

r = s_coun.get("/counsellor/at-risk")
t = r.get_data(as_text=True)
check("at-risk page 200", r.status_code == 200, r.status_code)
check("page documents the no-auto-message guarantee",
      "NEVER notified automatically" in t)
check("page lists flagged student", "Stu Thirteen" in t)
check("page shows reasons", "quiz_trend:down" in t)

# staff notification went to staff, not the student
with flask_app.app_context():
    from app.models import Notification
    staff_notifs = Notification.query.filter_by(ntype="at_risk").all()
    check("staff notified of new flags", len(staff_notifs) >= 1,
          str(len(staff_notifs)))
    check("student never notified",
          Notification.query.filter_by(ntype="at_risk",
                                       user_id=IDS["stu"]).count() == 0)

# resolve
r = s_coun.post(f"/counsellor/at-risk/{flag_id}/resolve",
                follow_redirects=True)
with flask_app.app_context():
    f = db.session.get(AtRiskFlag13, flag_id)
    check("resolve marks resolved",
          f.resolved is True and f.resolved_at is not None)

# students are forbidden
r = s_stu.get("/counsellor/at-risk")
check("student 403 on at-risk", r.status_code == 403, r.status_code)

# ------------------------------------------------- 4. memory -------------
r = s_stu.post("/student/memory/refresh", follow_redirects=True)
check("memory refresh redirects", r.status_code == 200, r.status_code)
with flask_app.app_context():
    mem = StudentMemory13.query.filter_by(user_id=IDS["stu"]).first()
    check("memory row exists", mem is not None)
    check("memory aggregates completed topics",
          mem and any("Variables and types" in t
                      for t in (mem.completed_topics or [])),
          str(mem.completed_topics) if mem else "")
    check("memory captures weak topics",
          mem and len(mem.weak_topics or []) > 0,
          str(mem.weak_topics) if mem else "")
    check("memory weak topic names the module",
          mem and any("Python Basics" in str(w)
                      for w in (mem.weak_topics or [])))
    ctx = memory_context_text(IDS["stu"])
    check("memory_context_text non-empty", bool(ctx.strip()))
    check("context text carries weak topics",
          "Weak topics" in ctx and "Python Basics" in ctx)
    check("context text carries completed lessons",
          "Completed lessons" in ctx and "Variables and types" in ctx)
r = s_stu.get("/student/memory")
t = r.get_data(as_text=True)
check("memory page 200", r.status_code == 200, r.status_code)
check("memory page shows profile", "My learning memory" in t)
check("memory page shows weak topics", "Python Basics" in t)

# get_memory creates empty for unknown user
with flask_app.app_context():
    fresh = User(name="Fresh", email="fresh13@sayyed.in", role="student")
    fresh.set_password("pw123")
    db.session.add(fresh)
    db.session.commit()
    m2 = get_memory(fresh.id)
    check("get_memory creates empty row",
          m2 is not None and (m2.completed_topics or []) == [] and
          (m2.weak_topics or []) == [])

print(f"\n{passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
