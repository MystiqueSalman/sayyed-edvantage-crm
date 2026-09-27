"""Phase 8 — Gamification & engagement (end-to-end).

Runs against a dev server on http://localhost:5000 with a FRESH DB
(migrated via `flask db upgrade` + seeded), same SQLITE_PATH for server and
this script. Mixes HTTP flows (login, lesson complete, pages, admin config,
challenge join) with in-process checks (badges, streaks, backfill, ledger).

Coverage: point awards per activity + no double-award, ledger reconciles to
totals, each badge criterion triggers, streak extends/resets across day
boundaries, challenge progress auto-tracks and completes with reward,
backfill correctness, admin point-value config changes future awards.
"""
import os
import sys
from datetime import datetime, timedelta

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app import gamification as G  # noqa: E402
from app.models import (Badge, Challenge, ChallengeEnrollment, Course,
                        Enrollment, GameProfile, LessonProgress, PointSetting,
                        PointTransaction, QuizAttempt, Resume, User,
                        UserBadge)  # noqa: E402

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


s_stu = requests.Session()
s_adm = requests.Session()
s_anon = requests.Session()

print("== Phase 8: Gamification & Engagement ==")

with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    adm = User.query.filter_by(email="admin@sayyed.in").first()
    check("seed users present", stu and adm)
    check("point settings seeded", PointSetting.query.count() >= 10)
    check("system badges seeded", Badge.query.filter_by(
        is_system=True).count() >= 10)
    # enroll the seeded student in the first course for HTTP flows
    course = Course.query.order_by(Course.id).first()
    enr = Enrollment.query.filter_by(user_id=stu.id,
                                    course_id=course.id).first()
    if not enr:
        enr = Enrollment(user_id=stu.id, course_id=course.id,
                         status="active", paid=True)
        db.session.add(enr)
        db.session.commit()
    lesson = course.lessons[0]
    lesson_id = int(lesson.id)
    check("course has lessons", bool(lesson))

# --- 1. daily login points (once per day) -------------------------------
check("student login", login(s_stu, "student@sayyed.in", "student123"))
check("admin login", login(s_adm, "admin@sayyed.in", "admin123"))
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    logins = PointTransaction.query.filter_by(
        user_id=stu.id, action="daily_login").all()
    check("daily_login awarded once", len(logins) == 1,
          f"got {len(logins)}")
    check("daily_login = 2 pts", logins[0].points == 2)
# login again — still one transaction
s_stu2 = requests.Session()
login(s_stu2, "student@sayyed.in", "student123")
with app.app_context():
    n = PointTransaction.query.filter_by(
        user_id=stu.id, action="daily_login").count()
    check("no double daily_login", n == 1, f"got {n}")

# --- 2. lesson completion points via HTTP --------------------------------
with app.app_context():
    before = PointTransaction.query.filter_by(
        user_id=stu.id, action="lesson_complete").count()
r = s_stu.post(f"{BASE}/lesson/{lesson_id}/complete", allow_redirects=False)
check("lesson complete POST ok", r.status_code in (302, 303),
      f"got {r.status_code}")
with app.app_context():
    txns = PointTransaction.query.filter_by(
        user_id=stu.id, action="lesson_complete").all()
    check("lesson_complete points awarded", len(txns) == before + 1)
    check("lesson_complete = 10 pts", txns[-1].points == 10,
          f"got {txns[-1].points}")
    prof = GameProfile.query.filter_by(user_id=stu.id).first()
    check("streak extended to 1", prof.current_streak == 1,
          f"got {prof.current_streak}")
    first_steps = Badge.query.filter_by(name="First Steps").first()
    earned = UserBadge.query.filter_by(
        user_id=stu.id, badge_id=first_steps.id).first()
    check("First Steps badge auto-awarded", earned is not None)
# re-POST the same lesson → no double award
r = s_stu.post(f"{BASE}/lesson/{lesson_id}/complete", allow_redirects=False)
with app.app_context():
    n = PointTransaction.query.filter_by(
        user_id=stu.id, action="lesson_complete").count()
    check("no double-award for same lesson", n == before + 1, f"got {n}")

# --- 3. ledger reconciles ------------------------------------------------
with app.app_context():
    prof = GameProfile.query.filter_by(user_id=stu.id).first()
    ledger = db.session.query(
        db.func.coalesce(db.func.sum(PointTransaction.points), 0)).filter_by(
        user_id=stu.id).scalar() or 0
    check("ledger == profile total", prof.points_total == int(ledger),
          f"{prof.points_total} vs {ledger}")
    total2 = G.recompute_points_total(stu.id)
    check("recompute_points_total stable", total2 == int(ledger),
          f"{total2} vs {ledger}")

# --- 4. badge criteria ----------------------------------------------------
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    course = Course.query.order_by(Course.id).first()
    # quiz mastery: 95% attempt
    quiz = course.quizzes[0] if course.quizzes else None
    if quiz:
        att = QuizAttempt(quiz_id=quiz.id, user_id=stu.id, score=95.0,
                          total=100.0, submitted_at=datetime.utcnow())
        db.session.add(att)
        db.session.commit()
        G.award_points(stu.id, "quiz_attempt", "attempt", att.id)
        G.award_points(stu.id, "quiz_score_bonus", "attempt", att.id,
                       points=int(95 * 0.2))
    whiz = Badge.query.filter_by(name="Quiz Whiz").first()
    check("Quiz Whiz badge (95% quiz)",
          UserBadge.query.filter_by(user_id=stu.id,
                                    badge_id=whiz.id).first() is not None)
    # resume complete → Polished
    res = Resume(user_id=stu.id, headline="Dev", summary="S",
                 skills_text="Python")
    db.session.add(res)
    db.session.commit()
    newb = G.check_badges(stu.id)
    db.session.commit()
    polished = Badge.query.filter_by(name="Polished").first()
    check("Polished badge (resume complete)",
          any(b.id == polished.id for b in newb) or
          UserBadge.query.filter_by(user_id=stu.id,
                                    badge_id=polished.id).first() is not None)
    # streak: 7 consecutive mocked days → Consistent (dedicated fresh user)
    u3 = User(name="Streak Sam", email="sam8@example.com", role="student")
    u3.set_password("x")
    db.session.add(u3)
    db.session.flush()
    u3_id = int(u3.id)
    db.session.commit()
    for i in range(6, -1, -1):
        G.record_activity(u3_id,
                          on_date=G.kolkata_today() - timedelta(days=i))
    db.session.commit()
    prof = GameProfile.query.filter_by(user_id=u3_id).first()
    check("7-day streak built", prof.current_streak == 7,
          f"got {prof.current_streak}")
    G.check_badges(u3_id)
    db.session.commit()
    consistent = Badge.query.filter_by(name="Consistent").first()
    check("Consistent badge (7-day streak)",
          UserBadge.query.filter_by(user_id=u3_id,
                                    badge_id=consistent.id).first() is not None)
    # missed day → reset
    G.record_activity(u3_id, on_date=G.kolkata_today() + timedelta(days=2))
    db.session.commit()
    prof = GameProfile.query.filter_by(user_id=u3_id).first()
    check("streak resets after missed day", prof.current_streak == 1,
          f"got {prof.current_streak}")
    check("longest streak kept", prof.longest_streak == 7,
          f"got {prof.longest_streak}")

# --- 5. challenges ---------------------------------------------------------
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    adm = User.query.filter_by(email="admin@sayyed.in").first()
    course = Course.query.order_by(Course.id).first()
    ch = Challenge(title="P8 Test Sprint", description="Earn 10 pts",
                   criterion="points", target_json='{"points": 10}',
                   reward_points=40, is_active=True,
                   starts_at=datetime.utcnow() - timedelta(hours=1),
                   created_by=adm.id)
    db.session.add(ch)
    db.session.commit()
    ch_id = ch.id
r = s_stu.post(f"{BASE}/challenges/{ch_id}/join")
check("challenge join", r.status_code == 200, f"got {r.status_code}")
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    stu_id = int(stu.id)
    course = Course.query.order_by(Course.id).first()
    lesson2_id = int(course.lessons[1].id)
    enr = ChallengeEnrollment.query.filter_by(
        challenge_id=ch_id, user_id=stu_id).first()
    check("enrollment created", enr is not None)
    # earn points → progress auto-tracks
    G.award_points(stu_id, "lesson_complete", "lesson", lesson2_id)
    enr = ChallengeEnrollment.query.filter_by(
        challenge_id=ch_id, user_id=stu_id).first()
    db.session.refresh(enr)
    check("challenge progress tracked", enr.progress > 0,
          f"got {enr.progress}")
    check("challenge completed at 10+ pts", enr.completed is True)
    reward = PointTransaction.query.filter_by(
        user_id=stu_id, action="challenge_reward", ref_id=str(enr.id)).first()
    check("challenge reward awarded", reward is not None and
          reward.points == 40, f"got {reward.points if reward else None}")
    # winners visible on detail page
r = s_stu.get(f"{BASE}/challenges/{ch_id}")
check("challenge detail shows winners",
      r.status_code == 200 and "Winners" in r.text)

# --- 6. backfill ------------------------------------------------------------
with app.app_context():
    # brand-new student with real historical activity
    course = Course.query.order_by(Course.id).first()
    lesson_a, lesson_b = course.lessons[0], course.lessons[1]
    u2 = User(name="Backfill Bob", email="bob8@example.com", role="student")
    u2.set_password("x")
    db.session.add(u2)
    db.session.flush()
    db.session.add(LessonProgress(user_id=u2.id, lesson_id=lesson_a.id,
                                 completed_at=datetime.utcnow() -
                                 timedelta(days=2)))
    db.session.add(LessonProgress(user_id=u2.id, lesson_id=lesson_b.id,
                                 completed_at=datetime.utcnow() -
                                 timedelta(days=1)))
    db.session.commit()
    stats = G.run_backfill(force=True)
    db.session.refresh(u2)
    txns = PointTransaction.query.filter_by(user_id=u2.id).all()
    check("backfill created transactions", len(txns) >= 2,
          f"got {len(txns)}")
    prof2 = GameProfile.query.filter_by(user_id=u2.id).first()
    check("backfill points = 2 lessons × 10", prof2.points_total == 20,
          f"got {prof2.points_total}")
    pioneer = Badge.query.filter_by(name="Pioneer", is_system=True).first()
    check("Pioneer badge awarded",
          UserBadge.query.filter_by(user_id=u2.id,
                                    badge_id=pioneer.id).first() is not None)
    check("backfill rebuilt 2-day streak",
          prof2.current_streak == 2, f"got {prof2.current_streak}")
    # second run is idempotent
    before_n = PointTransaction.query.filter_by(user_id=u2.id).count()
    G.run_backfill(force=True)
    after_n = PointTransaction.query.filter_by(user_id=u2.id).count()
    check("backfill idempotent", before_n == after_n,
          f"{before_n} vs {after_n}")

# --- 7. admin point-value config changes future awards ----------------------
r = s_adm.post(f"{BASE}/admin/gamification",
               data={"points_lesson_complete": "25"})
check("admin point config saved", r.status_code == 200,
      f"got {r.status_code}")
with app.app_context():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    course = Course.query.order_by(Course.id).first()
    lesson3 = course.lessons[2]
    pts, _ = G.award_points(stu.id, "lesson_complete", "lesson", lesson3.id)
    check("new point value applies to future awards", pts == 25,
          f"got {pts}")
    # old awards untouched
    lesson1_id = course.lessons[0].id
    old = PointTransaction.query.filter_by(
        user_id=stu.id, action="lesson_complete", ref_id=str(lesson1_id)
    ).first()
    check("past awards unchanged", old.points == 10, f"got {old.points}")

# --- 8. pages + access control ----------------------------------------------
r = s_stu.get(f"{BASE}/achievements")
check("/achievements renders",
      r.status_code == 200 and "My Achievements" in r.text)
r = s_stu.get(f"{BASE}/challenges")
check("/challenges renders",
      r.status_code == 200 and "Challenges" in r.text)
r = s_adm.get(f"{BASE}/admin/gamification")
check("/admin/gamification renders",
      r.status_code == 200 and "Point values" in r.text)
r = s_adm.get(f"{BASE}/admin/gamification/badges")
check("/admin/gamification/badges renders",
      r.status_code == 200 and "Badge" in r.text)
r = s_adm.get(f"{BASE}/manage/challenges")
check("/manage/challenges renders",
      r.status_code == 200 and "Challenges" in r.text)
r = s_stu.get(f"{BASE}/admin/gamification")
check("student blocked from admin gamification", r.status_code == 403,
      f"got {r.status_code}")
r = s_adm.get(f"{BASE}/achievements")
check("admin blocked from /achievements", r.status_code == 403,
      f"got {r.status_code}")
r = s_anon.get(f"{BASE}/achievements", allow_redirects=False)
check("anon redirected to login", r.status_code in (302, 303),
      f"got {r.status_code}")
r = s_stu.get(f"{BASE}/dashboard")
check("dashboard shows gamification strip",
      r.status_code == 200 and "day streak" in r.text)

print(f"\nPhase 8: {passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
