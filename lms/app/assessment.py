"""Phase 6 — assessment grading engine (§5.1, §5.3).

Pure grading logic for every question type, kept separate from routes so it
is easy to unit-test:

  grade_question(question, raw) -> Grading(marks_awarded, is_correct, needs_review)

Negative marking is applied at the attempt level by grade_attempt(), because
it is a per-quiz exam setting, not a per-question property.
"""
import json
import random
from collections import namedtuple

Grading = namedtuple("Grading", ["marks_awarded", "is_correct", "needs_review"])


def _norm_text(s):
    return (s or "").strip().lower()


def _parse_answer_data(question):
    try:
        data = json.loads(question.answer_data or "")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ------------------------------------------------------------------ graders
def grade_mcq_single(question, raw):
    chosen = (raw or "").strip().upper()
    ok = bool(chosen) and chosen == (question.correct or "").upper()
    return Grading(question.marks if ok else 0.0, ok, False)


def grade_mcq_multiple(question, raw):
    """Partial credit: each correct pick earns marks/n_correct; each wrong
    pick costs marks/n_options. Floored at 0. is_correct only on full marks."""
    data = _parse_answer_data(question)
    correct = {c.upper() for c in data.get("correct", []) if c}
    if not correct:
        # fall back to legacy single-correct column
        legacy = (question.correct or "").upper()
        correct = {legacy} if legacy else set()
    picked = {p.strip().upper() for p in (raw or "").split(",") if p.strip()}
    picked = {p for p in picked if p in ("A", "B", "C", "D")}
    n_correct = max(1, len(correct))
    n_options = 4
    per_correct = (question.marks or 0.0) / n_correct
    per_wrong = (question.marks or 0.0) / n_options
    got = len(picked & correct) * per_correct - len(picked - correct) * per_wrong
    got = max(0.0, round(got, 2))
    full = round(question.marks or 0.0, 2)
    return Grading(got, got >= full and bool(picked), False)


def grade_true_false(question, raw):
    chosen = (raw or "").strip().upper()
    data = _parse_answer_data(question)
    expected = str(data.get("correct", "")).strip().lower()
    if not expected:  # legacy: correct column holds T/F
        expected = (question.correct or "").strip().lower()
    ok = bool(chosen) and chosen.lower() == expected
    return Grading(question.marks if ok else 0.0, ok, False)


def grade_fill_blank(question, raw):
    data = _parse_answer_data(question)
    accepted = {_norm_text(a) for a in data.get("accepted", []) if a}
    ok = bool(accepted) and _norm_text(raw) in accepted
    return Grading(question.marks if ok else 0.0, ok, False)


def grade_matching(question, raw):
    """raw: JSON mapping left-item -> right-item chosen by the student."""
    data = _parse_answer_data(question)
    pairs = data.get("pairs", [])
    if not pairs:
        return Grading(0.0, False, False)
    try:
        given = json.loads(raw or "")
        given = given if isinstance(given, dict) else {}
    except Exception:
        given = {}
    per = (question.marks or 0.0) / len(pairs)
    got = sum(per for left, right in pairs
              if _norm_text(given.get(left)) == _norm_text(right))
    got = round(got, 2)
    full = round(question.marks or 0.0, 2)
    return Grading(got, got >= full, False)


def grade_descriptive(question, raw):
    """Descriptive answers always need faculty review (§5.1)."""
    answered = bool((raw or "").strip())
    return Grading(0.0, False, answered)


GRADERS = {
    "mcq_single": grade_mcq_single,
    "mcq_multiple": grade_mcq_multiple,
    "true_false": grade_true_false,
    "fill_blank": grade_fill_blank,
    "matching": grade_matching,
    "descriptive": grade_descriptive,
}

# Question types where negative marking applies on a fully-wrong answer.
NEGATIVE_TYPES = {"mcq_single", "true_false"}


def grade_question(question, raw):
    """Grade one question. Never raises — unknown types score 0."""
    try:
        grader = GRADERS.get(question.qtype or "mcq_single", grade_mcq_single)
        return grader(question, raw)
    except Exception:
        return Grading(0.0, False, False)


# ------------------------------------------------------- attempt-level logic
def grade_attempt(quiz, questions, raw_answers):
    """Grade a whole attempt.

    raw_answers: {question_id: raw_answer}. Returns
    (per_question: [(question, raw, Grading)], score, total, pending_review).
    Applies the quiz's negative marking to fully-wrong NEGATIVE_TYPES
    answers; attempt score is clamped at 0.
    """
    per_q, score, total, pending = [], 0.0, 0.0, False
    neg = quiz.negative_marking or 0.0
    for q in questions:
        raw = raw_answers.get(q.id, "")
        g = grade_question(q, raw)
        awarded = g.marks_awarded
        if (neg and q.qtype in NEGATIVE_TYPES and not g.is_correct
                and str(raw or "").strip()):
            awarded = round(awarded - neg * (q.marks or 0.0), 2)
        per_q.append((q, raw, g._replace(marks_awarded=awarded)))
        score += awarded
        total += (q.marks or 0.0)
        pending = pending or g.needs_review
    score = max(0.0, round(score, 2))
    return per_q, score, round(total, 2), pending


def order_questions_for_attempt(quiz, questions, seed=None):
    """Return the question list in attempt order (shuffled when enabled)."""
    qs = list(questions)
    if quiz.shuffle_questions:
        rnd = random.Random(seed)
        rnd.shuffle(qs)
    return qs


def option_order_for_question(quiz, question, seed=None):
    """Return [(letter, text)] display order (shuffled when enabled)."""
    opts = question.options
    if quiz.shuffle_options and question.qtype in ("mcq_single", "mcq_multiple"):
        opts = [o for o in opts if (o[1] or "").strip()]
        rnd = random.Random(seed)
        rnd.shuffle(opts)
    return opts


def attempts_used(quiz, user_id):
    from .models import QuizAttempt
    return QuizAttempt.query.filter_by(quiz_id=quiz.id, user_id=user_id).count()


def can_attempt(quiz, user_id):
    """(allowed, reason). Enforces max_attempts."""
    if quiz.max_attempts and attempts_used(quiz, user_id) >= quiz.max_attempts:
        return False, (f"This exam allows a maximum of {quiz.max_attempts} "
                       f"attempt(s) — you've used them all.")
    return True, ""


def best_score(quiz, user_id):
    """Effective score for certificate/progress per the quiz score policy."""
    from .models import QuizAttempt
    q = (QuizAttempt.query.filter_by(quiz_id=quiz.id, user_id=user_id)
         .order_by(QuizAttempt.taken_at.desc()))
    if quiz.score_policy == "latest":
        latest = q.first()
        return latest.percent if latest else 0
    best = q.order_by(QuizAttempt.score.desc()).first()
    return best.percent if best else 0
