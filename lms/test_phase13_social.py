"""Phase 13, Stream 4 — Direct messaging + Leaderboard (end-to-end).

Runs in-process via the Flask test client against a FRESH DB
(migrated via `flask db upgrade` + seeded by run_suite.sh). The blueprint
is registered here directly (the coordinator moves that one line into
app/__init__.py) and the new tables are created with db.create_all()
(the combined Phase 13 Alembic revision is added later by the coordinator).

Every direct DB/helper access runs inside its own short-lived
``with app.app_context():`` block (never a persistent pushed context),
so no session holds the SQLite file open across HTTP assertions.

Coverage:
  messaging: faculty can initiate; student can reply; student cannot
    initiate (403) and can never message another student; non-participant
    gets 403; admin moderation (list all / read thread / archive) works
    and admin views never mark messages read; unread counts correct.
  leaderboard: ordering correct; opt-out honored; anonymous viewers see
    masked names; course and batch filters work; badge counts shown.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db  # noqa: E402
from app import gamification as G  # noqa: E402
from app.models import (Badge, Batch, BatchMember, Course, Enrollment,  # noqa: E402
                        User, UserBadge)
from app.models13_social import (Conversation13, DirectMessage13,  # noqa: E402
                                 PrivacyPrefs13)
from app.social13 import (mask_name, social13_bp,  # noqa: E402
                          unread_dm_count)

app = create_app()
# Phase 13 merge: create_app() now registers social13_bp alongside the others.
if "social13" not in app.blueprints:
    app.register_blueprint(social13_bp)
with app.app_context():
    db.create_all()  # creates dm_conversations / dm_messages / leaderboard_privacy

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


def in_ctx(fn, *args, **kwargs):
    """Run fn inside a short-lived app context and return its result."""
    with app.app_context():
        return fn(*args, **kwargs)


def mk_user(name, email, role):
    def _mk():
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(name=name, email=email, role=role, is_active=True)
            u.set_password("test1234")
            db.session.add(u)
            db.session.commit()
        return u.id
    return in_ctx(_mk)


def client_for(email):
    c = app.test_client()
    r = c.post("/login", data={"email": email, "password": "test1234"})
    assert r.status_code in (200, 302), f"login failed for {email}: {r.status_code}"
    return c


def latest_conv_id():
    def _q():
        c = Conversation13.query.order_by(Conversation13.id.desc()).first()
        return c.id if c else None
    return in_ctx(_q)


def conv_row(cid):
    def _q():
        return Conversation13.query.get(cid)
    c = in_ctx(_q)
    return (c.student_id, c.faculty_id, c.subject, c.archived)


# ---------------------------------------------------------------- users
FAC = mk_user("Fiona Faculty", "p13_faculty@example.com", "faculty")
STU_A = mk_user("Aarav Student", "p13_stu_a@example.com", "student")
STU_B = mk_user("Bina Student", "p13_stu_b@example.com", "student")
STU_C = mk_user("Chetan Student", "p13_stu_c@example.com", "student")
STU_D = mk_user("Diya Student", "p13_stu_d@example.com", "student")
ADM = mk_user("Admin Root", "p13_admin@example.com", "admin")
COUN = mk_user("Cora Counsellor", "p13_counsellor@example.com", "counsellor")
MGR = mk_user("Mira Manager", "p13_manager@example.com", "manager")

c_fac = client_for("p13_faculty@example.com")
c_a = client_for("p13_stu_a@example.com")
c_b = client_for("p13_stu_b@example.com")
c_c = client_for("p13_stu_c@example.com")
c_d = client_for("p13_stu_d@example.com")
c_adm = client_for("p13_admin@example.com")
c_coun = client_for("p13_counsellor@example.com")
c_mgr = client_for("p13_manager@example.com")
c_anon = app.test_client()

print("== Phase 13 Stream 4: Direct messaging ==")

# 1. faculty can initiate a conversation with a student
r = c_fac.post("/messages/new", data={"student_id": STU_A, "subject": "Doubt",
                                       "body": "Hi Aarav, ask your doubts here."})
check("faculty initiates with student", r.status_code == 302,
      f"got {r.status_code}")
conv_id = latest_conv_id()
sid, fid, subj, _arch = conv_row(conv_id)
check("conversation row correct",
      sid == STU_A and fid == FAC and subj == "Doubt",
      f"conv={conv_id} sid={sid} fid={fid}")
n = in_ctx(unread_dm_count, STU_A)
check("unread count for student after initiation", n == 1, f"got {n}")
n = in_ctx(unread_dm_count, STU_B)
check("unread count zero for non-participant", n == 0, f"got {n}")

# 2. inbox shows conversation with unread badge for the student
r = c_a.get("/messages")
check("student inbox 200", r.status_code == 200, f"got {r.status_code}")
check("student inbox shows unread badge", b"notif-count" in r.data)

# 3. student views thread -> marks read; thread shows the message
r = c_a.get(f"/messages/{conv_id}")
check("student thread 200", r.status_code == 200, f"got {r.status_code}")
check("thread shows faculty message",
      b"Hi Aarav, ask your doubts here." in r.data)
n = in_ctx(unread_dm_count, STU_A)
check("viewing marks thread read", n == 0, f"got {n}")

# 4. student can reply within their own conversation
r = c_a.post(f"/messages/{conv_id}/reply", data={"body": "Thanks! My doubt is about joins."})
check("student reply 302", r.status_code == 302, f"got {r.status_code}")
n = in_ctx(unread_dm_count, FAC)
check("faculty now has 1 unread", n == 1, f"got {n}")
r = c_fac.get(f"/messages/{conv_id}")
check("faculty sees student reply",
      b"Thanks! My doubt is about joins." in r.data)

# 5. student can NEVER initiate (403), not even with another student
r = c_a.post("/messages/new", data={"student_id": STU_B, "subject": "x", "body": "yo"})
check("student cannot initiate with another student", r.status_code == 403,
      f"got {r.status_code}")
r = c_a.get("/messages/new")
check("student cannot open new-message form", r.status_code == 403,
      f"got {r.status_code}")
n = in_ctx(lambda: Conversation13.query.filter_by(student_id=STU_B).count())
check("no student-student conversation created", n == 0, f"got {n}")

# 6. non-participant gets 403
r = c_b.get(f"/messages/{conv_id}")
check("non-participant thread 403", r.status_code == 403, f"got {r.status_code}")
r = c_b.post(f"/messages/{conv_id}/reply", data={"body": "sneaky"})
check("non-participant reply 403", r.status_code == 403, f"got {r.status_code}")

# 7. manager cannot initiate either
r = c_mgr.post("/messages/new", data={"student_id": STU_A, "subject": "x", "body": "yo"})
check("manager cannot initiate", r.status_code == 403, f"got {r.status_code}")

# 8. counsellor CAN initiate with a student
r = c_coun.post("/messages/new", data={"student_id": STU_B, "subject": "Fees",
                                        "body": "Fee plans are ready."})
check("counsellor initiates with student", r.status_code == 302,
      f"got {r.status_code}")
conv2 = latest_conv_id()
n = in_ctx(unread_dm_count, STU_B)
check("counsellor thread unread for student B", n == 1, f"got {n}")
r = c_b.post(f"/messages/{conv2}/reply", data={"body": "Got it, thanks."})
check("student B replies to counsellor", r.status_code == 302,
      f"got {r.status_code}")

# 9. re-initiating reuses the open conversation
r = c_fac.post("/messages/new", data={"student_id": STU_A, "subject": "Doubt",
                                       "body": "another thread?"})
check("duplicate initiation reuses thread", r.status_code == 302,
      f"got {r.status_code}")
n = in_ctx(lambda: Conversation13.query.filter_by(
    student_id=STU_A, faculty_id=FAC, archived=False).count())
check("no duplicate open conversation", n == 1, f"got {n}")

# 10. anonymous users are redirected to login
r = c_anon.get("/messages")
check("anonymous /messages redirects", r.status_code == 302, f"got {r.status_code}")

# 11. admin moderation: list all, read thread, archive.
# Give the faculty one fresh unread message first, so the read-state check is real.
r = c_a.post(f"/messages/{conv_id}/reply", data={"body": "One more question on subqueries."})
check("student posts again", r.status_code == 302, f"got {r.status_code}")
r = c_adm.get("/messages")
check("admin inbox 200", r.status_code == 200, f"got {r.status_code}")
check("admin sees both student names",
      b"Aarav Student" in r.data and b"Bina Student" in r.data)
unread_before_admin = in_ctx(unread_dm_count, FAC)
check("faculty has 1 unread before admin view", unread_before_admin == 1,
      f"got {unread_before_admin}")
r = c_adm.get(f"/messages/{conv_id}")
check("admin can read any thread", r.status_code == 200
      and b"One more question on subqueries." in r.data)
n = in_ctx(unread_dm_count, FAC)
check("admin view does not mark read", n == unread_before_admin,
      f"before={unread_before_admin} after={n}")
r = c_adm.post(f"/messages/{conv_id}/reply", data={"body": "admin intruding"})
check("admin cannot post into a thread", r.status_code == 403,
      f"got {r.status_code}")
r = c_adm.post(f"/messages/{conv_id}/archive")
check("admin archives conversation", r.status_code == 302,
      f"got {r.status_code}")
_archived = conv_row(conv_id)[3]
check("conversation archived flag", _archived is True)

# 12. archived thread drops out of unread badge counts
na = in_ctx(unread_dm_count, STU_A)
nf = in_ctx(unread_dm_count, FAC)
check("archived conv excluded from unread", na == 0 and nf == 0,
      f"A={na} F={nf}")

print("== Phase 13 Stream 4: Leaderboard ==")

# seed points through the gamification API (not raw SQL)
def _seed():
    G.award_points(STU_A, "p13_seed", "seed", "a", points=100, counts_for_streak=False)
    G.award_points(STU_B, "p13_seed", "seed", "b", points=200, counts_for_streak=False)
    G.award_points(STU_C, "p13_seed", "seed", "c", points=50, counts_for_streak=False)
    G.award_points(STU_D, "p13_seed", "seed", "d", points=300, counts_for_streak=False)
    badge = Badge(name="P13 Test Badge", icon="🏅", description="test",
                  criterion="p13_custom", threshold=1)
    db.session.add(badge)
    db.session.flush()
    db.session.add(UserBadge(user_id=STU_A, badge_id=badge.id))
    db.session.commit()
in_ctx(_seed)

# 13. ordering correct on the platform tab (D 300 > B 200 > A 100 > C 50)
r = c_a.get("/leaderboard")
check("leaderboard 200", r.status_code == 200, f"got {r.status_code}")
body = r.data.decode()
ia, ib, ic, idd = (body.find(nm) for nm in
                   ("Aarav Student", "Bina Student", "Chetan Student", "Diya Student"))
check("leaderboard order D>B>A>C",
      -1 not in (ia, ib, ic, idd) and idd < ib < ia < ic,
      f"pos D={idd} B={ib} A={ia} C={ic}")
check("badge count shown", "🏅 1" in body)

# 14. opt-out honored
def _optout_b():
    db.session.add(PrivacyPrefs13(user_id=STU_B, leaderboard_opt_out=True))
    db.session.commit()
in_ctx(_optout_b)
r = c_a.get("/leaderboard")
body = r.data.decode()
check("opted-out user absent", "Bina Student" not in body)
ia, ic, idd = (body.find(nm) for nm in ("Aarav Student", "Chetan Student", "Diya Student"))
check("ranks reflow after opt-out", idd < ia < ic,
      f"pos D={idd} A={ia} C={ic}")
check("top rank medal present", "🥇" in body)

# 15. anonymous viewers see masked names
r = c_anon.get("/leaderboard")
check("anonymous leaderboard 200", r.status_code == 200, f"got {r.status_code}")
body = r.data.decode()
check("anonymous sees masked Diya", mask_name("Diya Student") in body,
      f"expected {mask_name('Diya Student')}")
check("anonymous does NOT see real names",
      "Diya Student" not in body and "Aarav Student" not in body)
check("mask helper format", mask_name("Aarav") == "A***v",
      f"got {mask_name('Aarav')}")

# 16. course filter: enroll A and C in a course, D stays out
def _enroll():
    course = Course.query.first()
    db.session.add(Enrollment(user_id=STU_A, course_id=course.id,
                              status=Enrollment.STATUS_ACTIVE, paid=True))
    db.session.add(Enrollment(user_id=STU_C, course_id=course.id,
                              status=Enrollment.STATUS_ACTIVE, paid=True))
    db.session.commit()
    return course.id
course_id = in_ctx(_enroll)
r = c_a.get(f"/leaderboard?tab=course&course_id={course_id}")
body = r.data.decode()
check("course tab 200", r.status_code == 200, f"got {r.status_code}")
check("course tab shows enrolled A", "Aarav Student" in body)
check("course tab shows enrolled C", "Chetan Student" in body)
check("course tab excludes non-enrolled D", "Diya Student" not in body)

# 17. batch filter: roster B (opted out) + D
def _batch():
    batch = Batch(name="P13 Test Batch", course_id=course_id, faculty_id=FAC)
    db.session.add(batch)
    db.session.flush()
    db.session.add(BatchMember(batch_id=batch.id, user_id=STU_B))
    db.session.add(BatchMember(batch_id=batch.id, user_id=STU_D))
    db.session.commit()
    return batch.id
batch_id = in_ctx(_batch)
r = c_a.get(f"/leaderboard?tab=batch&batch_id={batch_id}")
body = r.data.decode()
check("batch tab 200", r.status_code == 200, f"got {r.status_code}")
check("batch tab shows roster D", "Diya Student" in body)
check("batch tab excludes non-roster A", "Aarav Student" not in body)
check("opt-out honored on batch tab", "Bina Student" not in body)

# 18. selector tabs render without selection
r = c_a.get("/leaderboard?tab=course")
check("course selector renders", r.status_code == 200 and
      b"choose a course" in r.data, f"got {r.status_code}")
r = c_a.get("/leaderboard?tab=batch")
check("batch selector renders", r.status_code == 200 and
      b"choose a batch" in r.data, f"got {r.status_code}")

# 19. privacy toggle endpoint
r = c_c.post("/leaderboard/privacy", data={"opt_out": "1"})
check("privacy toggle 302", r.status_code == 302, f"got {r.status_code}")
def _pref_c():
    pref = PrivacyPrefs13.query.filter_by(user_id=STU_C).first()
    return pref is not None and pref.leaderboard_opt_out is True
check("opt-out persisted", in_ctx(_pref_c))
r = c_a.get("/leaderboard")
check("opted-out C gone from platform tab", "Chetan Student" not in r.data.decode())

print(f"\nRESULT: {passed} passed, {failed} failed")
if notes:
    print("FAILED:", notes)
sys.exit(1 if failed else 0)
