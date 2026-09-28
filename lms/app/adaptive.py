"""Phase 12 §21.5 — adaptive learning engine (rules-based, no ML libs).

Topic = course module. For each (student, module) we average the latest
quiz-attempt percentage; modules below the threshold with at least one
attempt are "weak". Recommendations point the student at the weakest
module's first lesson (re-watch) and its lowest-scoring quiz (retry).

Class aggregates power /admin/adaptive for faculty/admin.
"""
from sqlalchemy import func

from . import db
from .models import Lesson, Module, Quiz, QuizAttempt

WEAK_THRESHOLD = 60.0  # avg % below this => weak topic


def _latest_attempts(user_id, quiz_ids):
    """Latest submitted attempt per quiz for a student."""
    if not quiz_ids:
        return {}
    rows = (QuizAttempt.query
            .filter(QuizAttempt.user_id == user_id,
                    QuizAttempt.quiz_id.in_(quiz_ids),
                    QuizAttempt.submitted_at.isnot(None))
            .order_by(QuizAttempt.submitted_at.desc()).all())
    latest = {}
    for att in rows:
        latest.setdefault(att.quiz_id, att)
    return latest


def module_scores(user_id, course_id):
    """Per-module average quiz % for a student. Skips modules w/o attempts."""
    from .models import Course
    course = db.session.get(Course, course_id)
    if not course:
        return []
    out = []
    for mod in course.modules:
        quiz_ids = [q.id for q in mod.quizzes]
        latest = _latest_attempts(user_id, quiz_ids)
        if not latest:
            continue
        pcts = [a.percent for a in latest.values()]
        avg = round(sum(pcts) / len(pcts), 1)
        out.append({
            "module_id": mod.id,
            "module_title": mod.title,
            "avg": avg,
            "attempts": len(latest),
            "weak": avg < WEAK_THRESHOLD,
            "quizzes": [
                {"quiz_id": qid, "title": db.session.get(Quiz, qid).title,
                 "percent": latest[qid].percent}
                for qid in quiz_ids if qid in latest
            ],
        })
    return out


def weak_modules(user_id, course_id):
    return [m for m in module_scores(user_id, course_id) if m["weak"]]


def recommendations_for_student(user_id, course_ids=None, limit=6):
    """'Recommended next' items: re-watch lesson / retry quiz per weak module.

    Each item: {kind, course_id, course_title, module_title, avg,
                lesson_id, lesson_title, quiz_id, quiz_title, reason}.
    """
    from .models import Course, Enrollment
    if course_ids is None:
        course_ids = [e.course_id for e in
                      Enrollment.query.filter_by(user_id=user_id)
                      .filter(Enrollment.status.in_(["active", "completed"])).all()]
    elif isinstance(course_ids, int):
        course_ids = [course_ids]
    recs = []
    for cid in course_ids:
        course = db.session.get(Course, cid)
        if not course:
            continue
        for m in weak_modules(user_id, cid):
            mod = db.session.get(Module, m["module_id"])
            lesson = (Lesson.query.filter_by(module_id=mod.id)
                      .order_by(Lesson.position).first()) if mod else None
            worst = min(m["quizzes"], key=lambda q: q["percent"]) \
                if m["quizzes"] else None
            recs.append({
                "kind": "revise",
                "course_id": cid,
                "course_title": course.title,
                "module_id": m["module_id"],
                "module_title": m["module_title"],
                "avg": m["avg"],
                "lesson_id": lesson.id if lesson else None,
                "lesson_title": lesson.title if lesson else "",
                "quiz_id": worst["quiz_id"] if worst else None,
                "quiz_title": worst["title"] if worst else "",
                "reason": (f"Scoring {m['avg']}% in “{m['module_title']}” — "
                           f"re-watch the lesson and retry the quiz."),
            })
            if len(recs) >= limit:
                return recs
    return recs


def class_weak_topics(course_id):
    """Class-level aggregates: per-module avg % + weak-student count."""
    from .models import Course
    course = db.session.get(Course, course_id)
    if not course:
        return []
    out = []
    for mod in course.modules:
        quiz_ids = [q.id for q in mod.quizzes]
        if not quiz_ids:
            continue
        rows = (QuizAttempt.query
                .filter(QuizAttempt.quiz_id.in_(quiz_ids),
                        QuizAttempt.submitted_at.isnot(None)).all())
        latest = {}
        for att in rows:
            key = (att.quiz_id, att.user_id)
            if key not in latest or (att.submitted_at and latest[key].submitted_at
                                     and att.submitted_at > latest[key].submitted_at):
                latest[key] = att
        if not latest:
            continue
        by_student = {}
        for att in latest.values():
            by_student.setdefault(att.user_id, []).append(att.percent)
        avgs = [sum(v) / len(v) for v in by_student.values()]
        class_avg = round(sum(avgs) / len(avgs), 1)
        weak_n = sum(1 for a in avgs if a < WEAK_THRESHOLD)
        out.append({
            "module_id": mod.id,
            "module_title": mod.title,
            "students": len(avgs),
            "class_avg": class_avg,
            "weak_students": weak_n,
            "weak": class_avg < WEAK_THRESHOLD,
        })
    return sorted(out, key=lambda r: r["class_avg"])
