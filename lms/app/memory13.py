"""Phase 13 Stream 3 — student memory profile logic (§13.3.4).

Pure functions + small DB helpers. Imported by app/ai13.py for the
/student/memory page and the memory_context_text() prompt helper.
"""
from datetime import datetime

from . import db
from .models import (Course, Enrollment, Lesson, LessonProgress, Module,
                     Quiz, QuizAttempt, User)
from .models13_ai import StudentMemory13


def get_memory(user_id):
    """Return the StudentMemory13 row, creating an empty one if missing."""
    mem = StudentMemory13.query.filter_by(user_id=user_id).first()
    if mem is None:
        mem = StudentMemory13(user_id=user_id)
        db.session.add(mem)
        db.session.commit()
    return mem


def _enrolled_courses(user_id):
    return (Course.query.join(Enrollment,
                             Enrollment.course_id == Course.id)
            .filter(Enrollment.user_id == user_id).all())


def _latest_attempt_percent_avg(user_id, course_id):
    """Average % of the student's latest submitted attempt per quiz."""
    quizzes = Quiz.query.join(Module, Quiz.module_id == Module.id).filter(
        Module.course_id == course_id).all()
    if not quizzes:
        return None
    qids = [q.id for q in quizzes]
    latest = {}
    rows = (QuizAttempt.query
            .filter(QuizAttempt.user_id == user_id,
                    QuizAttempt.quiz_id.in_(qids),
                    QuizAttempt.submitted_at.isnot(None),
                    QuizAttempt.total > 0)
            .order_by(QuizAttempt.taken_at.desc()).all())
    for att in rows:
        latest.setdefault(att.quiz_id, att)
    if not latest:
        return None
    return round(sum(a.percent for a in latest.values()) / len(latest), 1)


def refresh_memory(user_id):
    """Recompute the memory profile from live LMS data.

    Sources: completed lessons (LessonProgress), weak topics from the
    Phase 12 adaptive engine (adaptive.weak_modules — module-level) plus
    the AI-tutor miss analysis (ai_tutor.weak_topics_for_student —
    lesson-level), strengths (module avg >= 80), per-course quiz averages.
    Existing preferences are preserved.
    """
    from . import adaptive  # lazy: keep import graph light

    user = db.session.get(User, user_id)
    if not user:
        return None
    mem = get_memory(user_id)
    prefs = dict(mem.preferences or {})

    # -- completed topics ------------------------------------------------
    done = (db.session.query(Lesson.title, Course.title)
            .join(LessonProgress,
                  LessonProgress.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .join(Course, Module.course_id == Course.id)
            .filter(LessonProgress.user_id == user_id)
            .order_by(LessonProgress.completed_at.desc())
            .limit(200).all())
    completed = [f"{course} — {lesson}" for lesson, course in done]

    # -- weak topics + strengths + quiz averages -------------------------
    weak, strengths, quiz_avgs = [], [], {}
    seen_weak = set()
    for course in _enrolled_courses(user_id):
        # Phase 12 adaptive engine (module-level, rules-based)
        for m in adaptive.weak_modules(user_id, course.id):
            key = (course.id, m["module_id"])
            if key not in seen_weak:
                seen_weak.add(key)
                weak.append({"course": course.title,
                             "topic": m["module_title"],
                             "avg": m["avg"]})
        # Lesson-level miss analysis (also syncs Phase 5 AI memory)
        try:
            from .ai_tutor import weak_topics_for_student
            for t in weak_topics_for_student(user_id, course.id)[:10]:
                key = (course.id, t.get("lesson_id"))
                if key not in seen_weak:
                    seen_weak.add(key)
                    weak.append({"course": course.title,
                                 "topic": t.get("title", ""),
                                 "misses": t.get("misses", 0)})
        except Exception:
            pass
        # strengths: modules with avg >= 80
        for m in adaptive.module_scores(user_id, course.id):
            if m["avg"] is not None and m["avg"] >= 80:
                strengths.append(f"{course.title} — {m['module_title']}")
        avg = _latest_attempt_percent_avg(user_id, course.id)
        if avg is not None:
            quiz_avgs[course.title] = avg

    mem.completed_topics = completed
    mem.weak_topics = weak
    mem.strengths = strengths
    mem.preferences = prefs or {"pace": "", "language": ""}
    mem.updated_at = datetime.utcnow()
    db.session.commit()
    # stash quiz avgs on the instance (not persisted) for the page helper
    mem._quiz_avgs = quiz_avgs
    return mem


def memory_context_text(user_id):
    """Short text block for injection into an LLM system prompt."""
    mem = get_memory(user_id)
    done = mem.completed_topics or []
    weak = mem.weak_topics or []
    strong = mem.strengths or []
    prefs = mem.preferences or {}

    def _names(items):
        out = []
        for w in items[:8]:
            out.append(w.get("topic", "") if isinstance(w, dict) else str(w))
        return [x for x in out if x]

    lines = ["STUDENT MEMORY PROFILE (auto-computed, may be incomplete):"]
    lines.append(f"- Completed lessons ({len(done)}): "
                 + (", ".join(done[:8]) if done else "none yet"))
    lines.append("- Weak topics: " + (", ".join(_names(weak)) or "none identified"))
    lines.append("- Strengths: " + (", ".join(strong[:8]) or "none yet"))
    pace = prefs.get("pace") or "not set"
    lang = prefs.get("language") or "not set"
    lines.append(f"- Preferences: pace={pace}, language={lang}")
    return "\n".join(lines)
