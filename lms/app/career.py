"""Phase 7 — Career & Placements business logic.

Resume data (verified records only), placement-readiness scoring with
admin-configurable weights, and AI mock interviews (OpenAI when available,
rules fallback otherwise — same pattern as the Phase 5 AI tutor).

HARD RULE (brief §27.6 + standing no-guarantee policy): the readiness score
is presented as GUIDANCE for placement support. Nothing here may promise a
job, salary, interview call or placement outcome.
"""
import json
import os
import re
from datetime import datetime

import requests

from . import db
from .models import (AISettings, Certificate, Course, Enrollment,
                     LessonProgress, MockInterview, MockInterviewQA, Project,
                     ProjectSubmission, Question, QuizAttempt, ReadinessWeights,
                     Resume, User)

RULES_ONLY = os.environ.get("LMS_TUTOR_RULES_ONLY", "").strip() == "1"

GUIDANCE_DISCLAIMER = (
    "This readiness score is guidance to help you prepare — it is not a job "
    "guarantee. Sayyed EdVantage provides placement support (resume help, "
    "mock interviews, job-board access), not assured placements or salaries."
)

_WORD_RE = re.compile(r"[a-z0-9+#.]{3,}")


# ------------------------------------------------------------- resume data
def resume_for(user):
    """Get-or-create the student's editable Resume row."""
    r = Resume.query.filter_by(user_id=user.id).first()
    if not r:
        r = Resume(user_id=user.id)
        db.session.add(r)
        db.session.commit()
    return r


def verified_courses(user):
    """Completed (or active) enrollments — real records only."""
    out = []
    for e in (Enrollment.query.filter_by(user_id=user.id)
              .filter(Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                                            Enrollment.STATUS_COMPLETED]))
              .all()):
        out.append({"title": e.course.title,
                    "status": e.status,
                    "progress": e.progress(),
                    "completed": e.status == Enrollment.STATUS_COMPLETED})
    return out


def verified_certificates(user):
    return [{"course": c.course.title, "code": c.code,
             "issued": (c.issued_at or datetime.utcnow()).strftime("%b %Y")}
            for c in Certificate.query.filter_by(user_id=user.id).all()]


def verified_projects(user):
    """Evaluated project submissions — real records only."""
    out = []
    subs = (ProjectSubmission.query.filter_by(user_id=user.id,
                                              status="evaluated").all())
    for s in subs:
        p = db.session.get(Project, s.project_id)
        if not p:
            continue
        out.append({"title": p.title,
                    "skills": [x.strip() for x in (p.skills or "").split(",")
                               if x.strip()],
                    "url": s.project_url or "",
                    "percent": getattr(s, "percent", None)})
    return out


def verified_skills(user):
    """Skills evidenced by real records (project skills). Sorted, deduped."""
    seen = []
    for proj in verified_projects(user):
        for s in proj["skills"]:
            if s.lower() not in [x.lower() for x in seen]:
                seen.append(s)
    return seen


def resume_sections(user):
    """Full resume content: editable fields + verified-only sections."""
    r = resume_for(user)
    self_skills = [x.strip() for x in (r.skills_text or "").split(",")
                   if x.strip()]
    return {
        "resume": r,
        "name": user.name, "email": user.email, "phone": user.phone or "",
        "headline": r.headline or "", "summary": r.summary or "",
        "links": r.links(),
        "self_skills": self_skills,
        "verified_skills": verified_skills(user),
        "courses": verified_courses(user),
        "certificates": verified_certificates(user),
        "projects": verified_projects(user),
        "experience": r.experience(),
        "education": r.education(),
    }


# ------------------------------------------------------- readiness scoring
def _quiz_average(user):
    """Average % across submitted, fully-graded quiz attempts (0-100)."""
    attempts = (QuizAttempt.query.filter_by(user_id=user.id)
                .filter(QuizAttempt.submitted_at.isnot(None),
                        QuizAttempt.pending_review.is_(False)).all())
    if not attempts:
        return None
    pcts = []
    for a in attempts:
        try:
            pcts.append(float(a.percent))
        except (TypeError, ValueError):
            continue
    return round(sum(pcts) / len(pcts), 1) if pcts else None


def _completion_average(user):
    ens = (Enrollment.query.filter_by(user_id=user.id)
           .filter(Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                                         Enrollment.STATUS_COMPLETED]))
           .all())
    if not ens:
        return None
    return round(sum(e.progress() for e in ens) / len(ens), 1)


def readiness_for(user):
    """Placement-readiness 0-100 with per-criterion breakdown.

    Each criterion scores 0-100; the final score is the weighted mean using
    admin-configured weights (normalized). Missing data scores 0 for that
    criterion but is flagged so the student knows what to do.
    """
    w = ReadinessWeights.get().as_dict()
    total_w = sum(w.values()) or 1.0

    completion = _completion_average(user)
    quiz = _quiz_average(user)
    proj_subs = (ProjectSubmission.query.filter_by(user_id=user.id,
                                                  status="evaluated").count())
    proj_total = Project.query.filter_by(is_active=True).count()
    proj_score = (min(100.0, 100.0 * proj_subs / max(proj_total, 1))
                  if proj_total else (100.0 if proj_subs else 0.0))
    r = resume_for(user)
    resume_score = 100.0 if r.is_complete() else (
        50.0 if ((r.summary or "").strip() or (r.skills_text or "").strip())
        else 0.0)
    interviews = MockInterview.query.filter_by(
        user_id=user.id, status=MockInterview.STATUS_DONE).count()
    interview_score = min(100.0, interviews * 34.0)  # 3+ sessions = full marks
    certs = Certificate.query.filter_by(user_id=user.id).count()
    courses_done = sum(1 for e in Enrollment.query.filter_by(
        user_id=user.id, status=Enrollment.STATUS_COMPLETED).all())
    cert_score = (min(100.0, 100.0 * certs / max(courses_done, 1))
                  if courses_done else 0.0)

    criteria = [
        ("completion", "Course completion", completion if completion is not None else 0.0,
         "Complete more lessons in your enrolled courses."),
        ("quiz", "Quiz average", quiz if quiz is not None else 0.0,
         "Attempt quizzes and revise weak topics."),
        ("projects", "Evaluated projects", round(proj_score, 1),
         "Submit course projects for faculty evaluation."),
        ("resume", "Resume completed", resume_score,
         "Finish your resume: headline, summary and skills."),
        ("interviews", "Mock interviews", round(interview_score, 1),
         "Attempt AI mock interviews to practice."),
        ("certificates", "Certificates earned", round(cert_score, 1),
         "Complete courses to earn certificates."),
    ]
    score = round(sum(w[k] / total_w * v for k, _label, v, _tip in criteria), 1)
    # clamp
    score = max(0.0, min(100.0, score))
    breakdown = [{"key": k, "label": label, "value": v, "weight": round(w[k], 1),
                  "tip": tip, "has_data": not (k in ("quiz", "completion") and v == 0.0
                                               and {"quiz": quiz, "completion": completion}[k] is None)}
                 for k, label, v, tip in criteria]
    return {"score": score, "breakdown": breakdown,
            "weights": {k: round(v, 1) for k, v in w.items()},
            "disclaimer": GUIDANCE_DISCLAIMER}


# ------------------------------------------------------- mock interviews
INTERVIEW_QUESTIONS = 5

_ROLE_QUESTIONS = {
    "data": [
        "Explain the difference between supervised and unsupervised learning with an example.",
        "How would you handle missing values in a dataset before training a model?",
        "What is overfitting and how do you prevent it?",
        "Explain the bias-variance tradeoff in simple terms.",
        "Walk me through the steps of a typical data science project lifecycle.",
    ],
    "python": [
        "Explain the difference between a list and a tuple in Python.",
        "What are Python decorators and when would you use one?",
        "How does exception handling work in Python? Give an example.",
        "Explain list comprehensions with an example.",
        "What is the difference between deep copy and shallow copy?",
    ],
    "devops": [
        "What is CI/CD and why is it important?",
        "Explain the difference between Docker images and containers.",
        "How would you troubleshoot a failing Kubernetes pod?",
        "What is infrastructure as code? Name a tool you know.",
        "Explain blue-green deployment vs rolling deployment.",
    ],
    "linux": [
        "How do you check running processes and system resource usage in Linux?",
        "Explain file permissions in Linux (rwx) with an example.",
        "What is the difference between a process and a thread?",
        "How would you find a file containing specific text across directories?",
        "Explain what happens when you run a command with sudo.",
    ],
    "security": [
        "What is the difference between symmetric and asymmetric encryption?",
        "Explain what SQL injection is and how to prevent it.",
        "What are the phases of ethical hacking?",
        "How does a firewall differ from an IDS/IPS?",
        "What is social engineering and how do organizations defend against it?",
    ],
    "ai": [
        "What is the difference between traditional ML and generative AI?",
        "Explain what prompt engineering means with an example.",
        "What are embeddings and why are they useful?",
        "What is fine-tuning of a language model?",
        "Discuss one ethical concern with generative AI systems.",
    ],
}

_GENERIC_QUESTIONS = [
    "Tell me about yourself and why you are interested in this role.",
    "Describe a challenging project you worked on and how you handled it.",
    "What are your greatest strengths relevant to this role?",
    "Where do you see yourself professionally in two years?",
    "Do you have any questions for us about the role or the team?",
]


def _role_key(target_role, course):
    text = f"{target_role or ''} {course.title if course else ''}".lower()
    for key in _ROLE_QUESTIONS:
        if key in text:
            return key
    return None


def rules_questions(target_role, course, n=INTERVIEW_QUESTIONS):
    """Fallback question set: role-matched bank + course topics + generic."""
    key = _role_key(target_role, course)
    pool = list(_ROLE_QUESTIONS.get(key, []))
    if course:
        topics = []
        for m in course.modules:
            topics.append(m.title)
            for q in Question.query.filter(
                    Question.quiz.has(module_id=m.id),
                    Question.is_active.is_(True)).limit(3).all():
                topics.append(q.text)
        for t in topics:
            if len(pool) >= n + 2:
                break
            pool.append(f"Explain the concept: {t}.")
    while len(pool) < n:
        pool.append(_GENERIC_QUESTIONS[len(pool) % len(_GENERIC_QUESTIONS)])
    return pool[:n]


def _openai_interview(system_prompt, messages):
    try:
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key or RULES_ONLY:
            return None
        model = AISettings.get().model or "gpt-4o-mini"
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "system", "content": system_prompt}] + messages,
                  "max_tokens": 400, "temperature": 0.6},
            timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip() or None
    except Exception:
        return None


def interview_ask_question(session):
    """Produce the next interview question (OpenAI or rules). Returns text."""
    n = session.answered_count()
    total = session.questions_total or INTERVIEW_QUESTIONS
    role = session.target_role or "this role"
    course = session.course
    system = (
        f"You are a friendly but professional interviewer conducting a mock "
        f"interview for the role '{role}'. "
        f"{'The candidate studied the course: ' + course.title + '.' if course else ''} "
        f"Ask ONE concise interview question at a time, appropriate for a fresher. "
        f"Do not answer it yourself. Never promise jobs or placements."
    )
    asked = [q.question for q in session.qas]
    ai = _openai_interview(system, [
        {"role": "user",
         "content": f"This is question {n + 1} of {total}. "
                    f"Avoid repeating these: {asked[-3:] if asked else 'none'}. "
                    f"Ask the next interview question only."}])
    if ai:
        return ai
    pool = rules_questions(session.target_role, course, total)
    return pool[n % len(pool)]


def interview_feedback(session, question, answer):
    """Score one answer 0-10 with feedback. Returns (score, feedback)."""
    answer = (answer or "").strip()
    if not answer:
        return 0.0, "No answer was provided. Try answering in 2-4 sentences."
    system = (
        f"You are an interview coach giving feedback on a mock interview answer "
        f"for the role '{session.target_role or 'the role'}'. Score the answer "
        f"0-10 and give 2-3 lines of constructive feedback. Reply in the exact "
        f"format:\nSCORE: <number>\nFEEDBACK: <text>\nNever promise jobs."
    )
    ai = _openai_interview(system, [
        {"role": "user",
         "content": f"Question: {question}\nCandidate answer: {answer[:1500]}"}])
    if ai:
        m = re.search(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", ai)
        score = max(0.0, min(10.0, float(m.group(1)))) if m else 5.0
        fb = re.sub(r"(?s)^.*?FEEDBACK:\s*", "", ai).strip() or ai[:500]
        return round(score, 1), fb
    # rules fallback: length + keyword relevance heuristic
    words = _WORD_RE.findall(answer.lower())
    qwords = set(_WORD_RE.findall(question.lower()))
    overlap = len(set(words) & qwords)
    length_score = min(10.0, len(words) / 12.0)
    relevance = min(4.0, overlap * 0.8)
    score = round(min(10.0, length_score * 0.6 + relevance + 2.0), 1)
    fb = ("Good effort — aim for 3-5 sentences with a concrete example. "
          if score < 6 else
          "Solid answer — add a specific example or metric to stand out. ")
    fb += "Mention key terms from the question to show relevance."
    return score, fb


def interview_finalize(session):
    """Complete the session: overall 0-100 score + weak areas."""
    qas = [q for q in session.qas if q.score is not None]
    if not qas:
        session.score, session.weak_areas = 0.0, "No answers were scored."
    else:
        avg10 = sum(q.score for q in qas) / len(qas)
        session.score = round(avg10 * 10.0, 1)
        weak = [q for q in qas if (q.score or 0) < 6.0]
        if weak:
            topics = "; ".join(q.question[:80] for q in weak[:3])
            session.weak_areas = f"Revise: {topics}"
        else:
            session.weak_areas = "Consistent performance — keep practicing."
    session.status = MockInterview.STATUS_DONE
    session.completed_at = datetime.utcnow()
    db.session.commit()
    return session.score
