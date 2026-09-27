"""Phase 6 — Advanced Assessments (end-to-end, runs against a dev server on
http://localhost:5000 with a FRESH DB (migrated via `flask db upgrade` +
seeded), with the same SQLITE_PATH for both server and this script).

Coverage: 6 question types + grading engine (single/multiple partial credit,
true/false, fill-blank variants, matching partial, descriptive pending),
exam settings (timer auto-submit, randomization, negative marking, attempt
limits, best/latest score policy), question bank (filters/create/deactivate/
manual + auto build), descriptive grading queue, exam analytics, projects
(brief -> submit -> resubmit -> overdue block -> evaluate), access control,
bank-quiz invisibility to students.
"""
import io
import json
import os
import sys
from datetime import date, datetime, timedelta

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Course, Enrollment, Module, Project, ProjectSubmission, Question, Quiz,
    QuizAnswer, QuizAttempt, User, db,
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
    r = session.post(f"{BASE}/login", data={"email": email, "password": password})
    return "Logout" in r.text


s_stu = requests.Session()
s_fac = requests.Session()
s_anon = requests.Session()

print("== Phase 6: Advanced Assessments ==")

with app.app_context():
    ds = Course.query.filter_by(slug="data-science").first()
    mod = Module.query.filter_by(course_id=ds.id).first()
    stu = User.query.filter_by(email="student@sayyed.in").first()
    fac = User.query.filter_by(email="faculty@sayyed.in").first()
    check("seed data present", ds and mod and stu and fac)
    enr = Enrollment.query.filter_by(user_id=stu.id, course_id=ds.id).first()
    if not enr:
        enr = Enrollment(user_id=stu.id, course_id=ds.id, status="active",
                         paid=True)
        db.session.add(enr)
        db.session.commit()
    STU_ID, FAC_ID, DS_ID, MOD_ID = stu.id, fac.id, ds.id, mod.id

check("faculty login", login(s_fac, "faculty@sayyed.in", "faculty123"))
check("student login", login(s_stu, "student@sayyed.in", "student123"))

# ---------------- faculty builds an exam quiz ----------------
r = s_fac.post(f"{BASE}/manage/module/{MOD_ID}/quiz/new", data={
    "title": "Phase6 Final Exam", "pass_percent": "60",
    "time_limit_min": "30", "max_attempts": "3", "negative_marking": "0.25",
    "score_policy": "best", "shuffle_questions": "on",
    "shuffle_options": "on"}, allow_redirects=False)
check("exam quiz created -> questions page",
      r.status_code == 302 and "/questions" in r.headers.get("Location", ""))
with app.app_context():
    quiz = Quiz.query.filter_by(title="Phase6 Final Exam").first()
    check("exam settings stored",
          quiz and quiz.time_limit_min == 30 and quiz.shuffle_questions
          and quiz.shuffle_options and quiz.negative_marking == 0.25
          and quiz.max_attempts == 3 and quiz.score_policy == "best")
    QUIZ_ID = quiz.id

QBASE = f"{BASE}/manage/quiz/{QUIZ_ID}/questions"


def add_q(data):
    return s_fac.post(QBASE, data=data, allow_redirects=True)


add_q({"text": "2+2=?", "qtype": "mcq_single", "marks": "2",
       "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6",
       "correct": "B", "difficulty": "easy", "topic": "arithmetic"})
add_q({"text": "Pick the even numbers", "qtype": "mcq_multiple", "marks": "4",
       "option_a": "1", "option_b": "2", "option_c": "4", "option_d": "7",
       "correct_multi": ["B", "C"], "difficulty": "medium"})
add_q({"text": "Python is a snake only", "qtype": "true_false", "marks": "1",
       "correct_tf": "false"})
add_q({"text": "Python was created by ____", "qtype": "fill_blank",
       "marks": "2", "accepted": "Guido van Rossum\nGuido Rossum"})
add_q({"text": "Match the terms", "qtype": "matching", "marks": "3",
       "match_left": "list\ndict", "match_right": "ordered\nkey-value"})
add_q({"text": "Explain overfitting", "qtype": "descriptive", "marks": "5",
       "model_answer": "model fits training noise"})
with app.app_context():
    qs = Question.query.filter_by(quiz_id=QUIZ_ID).order_by(Question.id).all()
    check("6 typed questions added", len(qs) == 6,
          f"got {len(qs)}")
    types = [q.qtype for q in qs]
    check("all 6 types present",
          types == ["mcq_single", "mcq_multiple", "true_false", "fill_blank",
                    "matching", "descriptive"], str(types))
    QIDS = [q.id for q in qs]

# ---------------- student takes the exam ----------------
r = s_stu.get(f"{BASE}/quiz/{QUIZ_ID}")
check("exam page renders with exam-mode UI",
      r.status_code == 200 and "Exam mode" in r.text and 'id="timer"' in r.text)
with app.app_context():
    a0 = QuizAttempt.query.filter_by(quiz_id=QUIZ_ID, user_id=STU_ID,
                                     submitted_at=None).first()
    check("attempt started on GET (timer running)", a0 is not None
          and a0.started_at is not None)

qid = dict(zip(["single", "multi", "tf", "fill", "match", "desc"], QIDS))
form = [
    (f"q{qid['single']}", "B"),                       # correct: +2
    (f"q{qid['multi']}", "B"), (f"q{qid['multi']}", "C"),  # 2/2 correct: +4
    (f"q{qid['tf']}", "false"),                        # correct: +1
    (f"q{qid['fill']}", "guido VAN rossum"),           # variant+case: +2
    (f"q{qid['match']}_m0", "ordered"),                 # 1/2 pairs: +1.5
    (f"q{qid['match']}_m1", "nope"),
    (f"q{qid['desc']}", "Overfitting means the model memorises noise."),
]
r = s_stu.post(f"{BASE}/quiz/{QUIZ_ID}", data=form, allow_redirects=False)
check("exam submitted -> result redirect",
      r.status_code == 302 and "/quiz/result/" in r.headers.get("Location", ""))
with app.app_context():
    att = QuizAttempt.query.filter_by(quiz_id=QUIZ_ID, user_id=STU_ID).order_by(
        QuizAttempt.id.desc()).first()
    check("attempt submitted with pending review",
          att.submitted_at is not None and att.pending_review)
    check("partial-credit score math",
          abs(att.score - (2 + 4 + 1 + 2 + 1.5)) < 0.01 and att.total == 17,
          f"score={att.score} total={att.total}")
    dans = QuizAnswer.query.filter_by(attempt_id=att.id,
                                      question_id=qid["desc"]).first()
    check("descriptive queued for faculty review",
          dans and dans.needs_review and dans.marks_awarded == 0)
    ATT_ID, DANS_ID = att.id, dans.id

# ---------------- faculty grading queue ----------------
r = s_fac.get(f"{BASE}/manage/grading")
check("grading queue lists pending descriptive",
      r.status_code == 200 and "memorises noise" in r.text)
r = s_fac.post(f"{BASE}/manage/grading/{DANS_ID}",
               data={"marks": "4", "feedback": "Good explanation."},
               allow_redirects=True)
with app.app_context():
    att = QuizAttempt.query.get(ATT_ID)
    check("faculty grade recomputes attempt score",
          abs(att.score - (2 + 4 + 1 + 2 + 1.5 + 4)) < 0.01
          and not att.pending_review, f"score={att.score}")
    dans = QuizAnswer.query.get(DANS_ID)
    check("answer marked reviewed with feedback",
          not dans.needs_review and dans.feedback == "Good explanation."
          and dans.reviewed_by == FAC_ID)

# ---------------- attempt limits ----------------
with app.app_context():
    lim = Quiz(module_id=MOD_ID, title="P6 One-shot", max_attempts=1)
    db.session.add(lim)
    db.session.flush()
    db.session.add(Question(quiz_id=lim.id, text="1+1=?", qtype="mcq_single",
                            option_a="1", option_b="2", option_c="3",
                            option_d="4", correct="B", marks=1.0))
    db.session.commit()
    LIM_ID = lim.id
    LIM_Q = lim.questions[0].id
r = s_stu.post(f"{BASE}/quiz/{LIM_ID}", data={f"q{LIM_Q}": "B"},
               allow_redirects=False)
check("first attempt on limited quiz submits", r.status_code == 302)
r = s_stu.get(f"{BASE}/quiz/{LIM_ID}")
check("second attempt blocked by max_attempts",
      "used all 1 attempt" in r.text)

# ---------------- timer auto-submit ----------------
with app.app_context():
    tq = Quiz(module_id=MOD_ID, title="P6 Timed", time_limit_min=1)
    db.session.add(tq)
    db.session.flush()
    db.session.add(Question(quiz_id=tq.id, text="3+3=?", qtype="mcq_single",
                            option_a="5", option_b="6", option_c="7",
                            option_d="8", correct="B", marks=1.0))
    db.session.commit()
    TQ_ID = tq.id
r = s_stu.get(f"{BASE}/quiz/{TQ_ID}")
check("timed quiz starts", r.status_code == 200 and 'id="timer"' in r.text)
with app.app_context():
    ta = QuizAttempt.query.filter_by(quiz_id=TQ_ID, user_id=STU_ID,
                                     submitted_at=None).first()
    ta.started_at = datetime.utcnow() - timedelta(minutes=10)
    db.session.commit()
r = s_stu.get(f"{BASE}/quiz/{TQ_ID}", allow_redirects=False)
check("expired timer auto-submits",
      r.status_code == 302 and "/quiz/result/" in r.headers.get("Location", ""))
with app.app_context():
    ta = QuizAttempt.query.filter_by(quiz_id=TQ_ID, user_id=STU_ID).order_by(
        QuizAttempt.id.desc()).first()
    check("attempt flagged time_expired",
          ta.time_expired and ta.submitted_at is not None)

# ---------------- negative marking ----------------
with app.app_context():
    nq = Quiz(module_id=MOD_ID, title="P6 Negative", negative_marking=0.25)
    db.session.add(nq)
    db.session.flush()
    db.session.add(Question(quiz_id=nq.id, text="9+9=?", qtype="mcq_single",
                            option_a="17", option_b="18", option_c="19",
                            option_d="20", correct="B", marks=1.0))
    db.session.add(Question(quiz_id=nq.id, text="Sky is green",
                            qtype="true_false", correct="F", marks=1.0,
                            answer_data=json.dumps({"correct": "false"}),
                            option_a="True", option_b="False"))
    db.session.commit()
    NQ_ID = nq.id
    NQ_QS = [q.id for q in nq.questions]
r = s_stu.post(f"{BASE}/quiz/{NQ_ID}",
               data={f"q{NQ_QS[0]}": "A", f"q{NQ_QS[1]}": "true"},
               allow_redirects=True)
with app.app_context():
    na = QuizAttempt.query.filter_by(quiz_id=NQ_ID, user_id=STU_ID).order_by(
        QuizAttempt.id.desc()).first()
    nans = {a.question_id: a for a in na.answers}
    check("wrong MCQ gets -0.25 negative marking",
          nans[NQ_QS[0]].marks_awarded == -0.25,
          f"awarded={nans[NQ_QS[0]].marks_awarded}")
    check("wrong T/F gets -0.25 negative marking",
          nans[NQ_QS[1]].marks_awarded == -0.25)
    check("attempt score clamped at zero", na.score == 0.0)

# ---------------- randomization across attempts ----------------
r = s_stu.get(f"{BASE}/quiz/{QUIZ_ID}")
with app.app_context():
    orders = [a.question_order for a in
              QuizAttempt.query.filter_by(quiz_id=QUIZ_ID, user_id=STU_ID)
              .filter(QuizAttempt.submitted_at.is_(None)).all()]
    check("fresh attempt stores a question order", len(orders) == 1
          and len(json.loads(orders[0])) == 6)
# submit a second full attempt to compare orders
form2 = [(f"q{qid['single']}", "B"), (f"q{qid['multi']}", "B"),
         (f"q{qid['multi']}", "C"), (f"q{qid['tf']}", "false"),
         (f"q{qid['fill']}", "Guido Rossum"),
         (f"q{qid['match']}_m0", "ordered"),
         (f"q{qid['match']}_m1", "key-value"),
         (f"q{qid['desc']}", "second attempt")]
s_stu.post(f"{BASE}/quiz/{QUIZ_ID}", data=form2, allow_redirects=True)
with app.app_context():
    done = QuizAttempt.query.filter_by(quiz_id=QUIZ_ID, user_id=STU_ID).filter(
        QuizAttempt.submitted_at.isnot(None)).order_by(QuizAttempt.id).all()
    check("two submitted attempts with different orders",
          len(done) == 2 and done[0].question_order != done[1].question_order)

# ---------------- score policy best vs latest ----------------
# grade the 2nd attempt's descriptive so both attempts fully count
with app.app_context():
    att2 = QuizAttempt.query.filter_by(quiz_id=QUIZ_ID, user_id=STU_ID).order_by(
        QuizAttempt.id.desc()).first()
    d2 = QuizAnswer.query.filter_by(attempt_id=att2.id,
                                    question_id=qid["desc"]).first()
    D2_ID = d2.id
s_fac.post(f"{BASE}/manage/grading/{D2_ID}", data={"marks": "5", "feedback": "ok"},
           allow_redirects=True)
with app.app_context():
    from app.routes_student import _policy_attempt
    quiz = Quiz.query.get(QUIZ_ID)
    best = _policy_attempt(quiz, STU_ID)
    check("score_policy=best picks higher attempt",
          best and abs(best.score - 17.0) < 0.01, f"score={best.score if best else None}")
    quiz.score_policy = "latest"
    db.session.commit()
    latest = _policy_attempt(quiz, STU_ID)
    check("score_policy=latest picks last attempt",
          latest and latest.id == att2.id)
    quiz.score_policy = "best"
    db.session.commit()

# ---------------- question bank ----------------
r = s_fac.post(f"{BASE}/manage/question-bank/new", data={
    "course_id": str(DS_ID), "quiz_id": "", "text": "Bank: capital of France?",
    "qtype": "mcq_single", "marks": "1", "difficulty": "easy",
    "topic": "geography", "skills": "gk",
    "option_a": "Paris", "option_b": "Rome", "option_c": "Madrid",
    "option_d": "Lyon", "correct": "A"}, allow_redirects=True)
with app.app_context():
    bq = Question.query.filter_by(text="Bank: capital of France?").first()
    check("bank question created (bank placeholder quiz)",
          bq is not None and bq.quiz.title == "__question_bank__")
    BQ_ID = bq.id
    bank_quiz_id = bq.quiz_id
r = s_fac.get(f"{BASE}/manage/question-bank?topic=geography")
check("bank filter by topic", "capital of France" in r.text)
r = s_fac.get(f"{BASE}/manage/question-bank?topic=zzz_nomatch")
check("bank filter excludes non-matches", "capital of France" not in r.text)
r = s_fac.post(f"{BASE}/manage/question/{BQ_ID}/toggle", allow_redirects=True)
with app.app_context():
    check("bank question deactivated",
          Question.query.get(BQ_ID).is_active is False)
r = s_fac.get(f"{BASE}/manage/question-bank")
check("deactivated hidden from active-only bank",
      "capital of France" not in r.text)
s_fac.post(f"{BASE}/manage/question/{BQ_ID}/toggle", allow_redirects=True)
# bank quiz invisible to students
r = s_stu.get(f"{BASE}/quiz/{bank_quiz_id}")
check("bank placeholder quiz hidden from students (404)",
      r.status_code == 404)

# build from bank: manual pick
with app.app_context():
    tq2 = Quiz(module_id=MOD_ID, title="P6 Built Quiz")
    db.session.add(tq2)
    db.session.commit()
    BUILT_ID = tq2.id
r = s_fac.post(f"{BASE}/manage/quiz/{BUILT_ID}/from-bank",
               data={"mode": "manual", "qid": [str(BQ_ID)]},
               allow_redirects=True)
with app.app_context():
    bq2 = Quiz.query.get(BUILT_ID)
    check("manual bank pick copied into quiz",
          len(bq2.questions) == 1
          and bq2.questions[0].text == "Bank: capital of France?")
# build from bank: auto-generate
with app.app_context():
    for i in range(3):
        db.session.add(Question(
            quiz_id=Question.query.get(BQ_ID).quiz_id,
            text=f"Auto bank Q{i}", qtype="mcq_single", option_a="x",
            option_b="y", option_c="z", option_d="w", correct="A",
            difficulty="easy" if i < 2 else "hard", topic="geography",
            marks=1.0))
    db.session.commit()
r = s_fac.post(f"{BASE}/manage/quiz/{BUILT_ID}/from-bank",
               data={"mode": "auto", "count": "2", "difficulty": "easy"},
               allow_redirects=True)
with app.app_context():
    bq2 = Quiz.query.get(BUILT_ID)
    check("auto-generate adds N random easy questions",
          len(bq2.questions) == 3, f"got {len(bq2.questions)}")

# ---------------- exam analytics ----------------
r = s_fac.get(f"{BASE}/manage/quiz/{QUIZ_ID}/analytics")
check("faculty exam analytics renders",
      r.status_code == 200 and "Average score" in r.text
      and "Per-question performance" in r.text)

# ---------------- projects ----------------
future = (date.today() + timedelta(days=30)).isoformat()
r = s_fac.post(f"{BASE}/manage/projects/new", data={
    "course_id": str(DS_ID), "title": "P6 Capstone",
    "description": "Build a data dashboard.", "skills": "python, pandas",
    "deadline": future, "max_marks": "100"}, allow_redirects=True)
with app.app_context():
    proj = Project.query.filter_by(title="P6 Capstone").first()
    check("faculty publishes project brief",
          proj is not None and proj.deadline.isoformat() == future)
    PROJ_ID = proj.id
r = s_stu.get(f"{BASE}/projects")
check("student My Projects lists brief",
      r.status_code == 200 and "P6 Capstone" in r.text)
r = s_stu.post(f"{BASE}/project/{PROJ_ID}",
               data={"project_url": "https://github.com/x/y",
                     "notes": "first cut"}, allow_redirects=True)
with app.app_context():
    sub = ProjectSubmission.query.filter_by(project_id=PROJ_ID,
                                            user_id=STU_ID).first()
    check("student submits project (URL + notes)",
          sub is not None and sub.status == "submitted"
          and sub.project_url == "https://github.com/x/y")
    SUB_ID = sub.id
# resubmit with a file before deadline
r = s_stu.post(f"{BASE}/project/{PROJ_ID}",
               data={"project_url": "https://github.com/x/y2",
                     "notes": "v2"},
               files={"file": ("work.py", io.BytesIO(b"print('hi')"),
                               "text/x-python")},
               allow_redirects=True)
with app.app_context():
    sub = ProjectSubmission.query.get(SUB_ID)
    check("resubmission before deadline accepted",
          sub.status == "submitted" and sub.file_path.endswith(".py")
          and sub.notes == "v2")
# overdue blocks submission
with app.app_context():
    proj = Project.query.get(PROJ_ID)
    proj.deadline = date.today() - timedelta(days=1)
    db.session.commit()
r = s_stu.post(f"{BASE}/project/{PROJ_ID}", data={"notes": "late"},
               allow_redirects=True)
check("overdue submission rejected", "deadline has passed" in r.text.lower())
with app.app_context():
    Project.query.get(PROJ_ID).deadline = date.today() + timedelta(days=30)
    db.session.commit()
# faculty evaluates
r = s_fac.get(f"{BASE}/manage/projects/{PROJ_ID}/submissions")
check("faculty sees submission queue",
      r.status_code == 200 and "Student User" in r.text)
r = s_fac.post(f"{BASE}/manage/projects/submission/{SUB_ID}/evaluate",
               data={"marks": "85", "feedback": "Well structured."},
               allow_redirects=True)
with app.app_context():
    sub = ProjectSubmission.query.get(SUB_ID)
    check("faculty evaluation stored",
          sub.status == "evaluated" and sub.marks == 85
          and sub.feedback == "Well structured."
          and sub.evaluated_by == FAC_ID)
r = s_stu.get(f"{BASE}/project/{PROJ_ID}")
check("student sees marks + feedback",
      "85" in r.text and "Well structured." in r.text)
# project file download
r = s_stu.get(f"{BASE}/project/submission/{SUB_ID}/file")
check("student can download own project file",
      r.status_code == 200 and r.content == b"print('hi')")

# ---------------- access control ----------------
r = s_stu.get(f"{BASE}/manage/question-bank")
check("student blocked from question bank (403)", r.status_code == 403)
r = s_stu.get(f"{BASE}/manage/grading")
check("student blocked from grading queue (403)", r.status_code == 403)
r = s_stu.post(f"{BASE}/manage/projects/new", data={"title": "x"},
               allow_redirects=False)
check("student blocked from project creation (403)", r.status_code == 403)
r = s_anon.get(f"{BASE}/projects", allow_redirects=False)
check("anonymous redirected from projects",
      r.status_code in (301, 302))

print(f"\n{passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
