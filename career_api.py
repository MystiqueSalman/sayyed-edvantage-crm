"""Career & Placement API for the Study Portal.

Self-contained module called from public_website_api.handle_public_post via
dispatch(). Own data file (data/career.json), own lock, own rate limits.

AI features (interview scoring, resume enhancement) use OpenAI when the
SE_OPENAI_API_KEY env var is set; otherwise an honest keyword-rubric fallback
is used and the response is labelled ai=false.
"""

from __future__ import annotations

import json
import os
import random
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from career_content import (
    SUBJECTS,
    QUESTIONS,
    GENERAL_CHECKLIST,
    SUBJECT_CHECKLISTS,
    JOB_PLATFORMS,
    JOB_STATUSES,
)

OPENAI_API_KEY = os.environ.get("SE_OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("SE_OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

_CAREER_FILE = Path(__file__).resolve().parent / "data" / "career.json"
_lock = threading.Lock()
_rate: dict[str, list] = {}

LEVELS = ("beginner", "intermediate", "advanced", "mixed")
_SUBJECT_IDS = {s["id"] for s in SUBJECTS}


def ai_enabled() -> bool:
    return bool(OPENAI_API_KEY)


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------

def _blank_profile() -> dict:
    return {
        "interviews": [],      # completed interviews (open one stored separately)
        "active_interview": None,
        "resume": {},
        "checklist": {},       # subject_id -> [checked item ids]
        "portfolio": [],
        "jobs": [],
    }


def _load() -> dict:
    try:
        _CAREER_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _CAREER_FILE.exists():
            data = json.loads(_CAREER_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("students", {})
                return data
    except Exception as exc:
        print(f"[career] store read failed: {exc}")
    return {"students": {}}


def _save(data: dict) -> None:
    try:
        tmp = _CAREER_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(_CAREER_FILE)
    except Exception as exc:
        print(f"[career] store write failed: {exc}")


def _profile(store: dict, student_id: str) -> dict:
    prof = store["students"].get(student_id)
    if not isinstance(prof, dict):
        prof = _blank_profile()
        store["students"][student_id] = prof
    for k, v in _blank_profile().items():
        prof.setdefault(k, v)
    return prof


# --------------------------------------------------------------------------
# Rate limiting (per student)
# --------------------------------------------------------------------------

def _rate_ok(key: str, limit: int, window: int) -> bool:
    now = time.time()
    with _lock:
        start, count = _rate.get(key, (now, 0))
        if now - start > window:
            start, count = now, 0
        count += 1
        _rate[key] = [start, count]
        return count <= limit


# --------------------------------------------------------------------------
# OpenAI helper (None on any failure -> caller uses fallback)
# --------------------------------------------------------------------------

def _ai_chat(system: str, user: str, max_tokens: int = 1200, timeout: int = 60) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        payload = json.dumps({
            "model": OPENAI_MODEL,
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return text.strip() if isinstance(text, str) else None
    except Exception as exc:
        print(f"[career] AI call failed: {exc}")
        return None


def _parse_json(text: str) -> dict | None:
    try:
        t = text.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
            t = re.sub(r"\n?```$", "", t)
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Fallback (no-AI) scoring
# --------------------------------------------------------------------------

def _fallback_score(question: dict, answer: str) -> tuple[int, str]:
    a = answer.strip().lower()
    n = len(answer.strip())
    if n < 20:
        base = 2.0
    elif n < 60:
        base = 4.0
    elif n < 150:
        base = 6.0
    elif n < 400:
        base = 7.5
    else:
        base = 8.0
    kws = [k for k in question.get("keywords", []) if k.lower() in a]
    missing = [k for k in question.get("keywords", []) if k.lower() not in a]
    score = base + min(len(kws), 4) * 0.75
    if any(w in a for w in ("example", "for instance", "because", "e.g.", "such as")):
        score += 0.5
    score = max(1, min(10, round(score)))
    if score >= 8:
        fb = "Strong answer — covers the key concepts clearly."
    elif score >= 6:
        fb = ("Good attempt. Strengthen it with a concrete example"
              + (f" and mention: {', '.join(missing[:3])}." if missing else "."))
    elif score >= 4:
        fb = ("Partial answer. Structure it as definition → example → why it matters"
              + (f". Key points missing: {', '.join(missing[:4])}." if missing else "."))
    else:
        fb = ("Too brief — aim for 3–5 sentences covering: "
              + ", ".join(question.get("keywords", [])[:5]) + ".")
    return score, fb


_ENHANCE_TIPS = {
    "summary": ("AI tips for your summary:\n"
                "• Keep it to 2–3 lines: who you are, your strongest skills, what you're looking for.\n"
                "• Start with your identity (e.g. 'Python developer fresher').\n"
                "• Mention 2–3 concrete skills, not generic traits.\n"
                "• Never invent experience you don't have."),
    "skills": ("AI tips for skills:\n"
               "• List tools & technologies by category (Languages, Tools, Databases).\n"
               "• Only list skills you can answer questions on.\n"
               "• Match keywords from the job description (ATS scans for these)."),
    "experience": ("AI tips for experience/projects:\n"
                   "• Start every bullet with an action verb: Built, Developed, Automated…\n"
                   "• Add numbers: users, % improvement, lines of code, team size.\n"
                   "• Format: What you did → how → result."),
    "education": ("AI tips:\n• Degree, institute, year, percentage/CGPA.\n"
                  "• Add relevant coursework for fresher roles."),
    "projects": ("AI tips:\n• Project name + one-line purpose.\n"
                 "• Tech stack used, your specific contribution, and outcome.\n"
                 "• Link to GitHub or live demo if available."),
}


# --------------------------------------------------------------------------
# Interview scoring
# --------------------------------------------------------------------------

_AI_SCORE_SYSTEM = (
    "You are a senior technical interviewer at an Indian IT training institute "
    "(Sayyed EdVantage). Evaluate the candidate's interview answers fairly but "
    "strictly, like a real hiring manager. Respond ONLY with valid JSON, no markdown."
)


def _ai_score_interview(subject_name: str, level: str, qa: list[dict]) -> dict | None:
    lines = []
    for i, item in enumerate(qa, 1):
        lines.append(f"Q{i}: {item['q']}\nA{i}: {item['answer']}")
    user = (
        f"Subject: {subject_name}\nLevel: {level}\n\n"
        + "\n\n".join(lines)
        + "\n\nScore each answer 0–10. Return JSON exactly like:\n"
        '{"scores": [{"score": 7, "feedback": "..."}], '
        '"overall": 6.5, "strengths": "...", "improvements": "..."}\n'
        "Feedback must be specific (2–3 sentences per answer). "
        "Strengths and improvements: 2–3 sentences each, with concrete advice."
    )
    text = _ai_chat(_AI_SCORE_SYSTEM, user, max_tokens=1500, timeout=75)
    if not text:
        return None
    obj = _parse_json(text)
    if not obj or not isinstance(obj.get("scores"), list):
        return None
    if len(obj["scores"]) != len(qa):
        return None
    try:
        scores = []
        for s in obj["scores"]:
            sc = max(0, min(10, int(s["score"])))
            fb = str(s.get("feedback", ""))[:600]
            scores.append({"score": sc, "feedback": fb})
        overall = round(max(0.0, min(10.0, float(obj.get("overall", 0)))), 1)
        return {
            "scores": scores,
            "overall": overall,
            "strengths": str(obj.get("strengths", ""))[:800],
            "improvements": str(obj.get("improvements", ""))[:800],
        }
    except Exception:
        return None


def _score_interview(subject_name: str, level: str, questions: list[dict],
                     answers: list[str]) -> tuple[list[dict], float, str, str, bool]:
    qa = [{"q": q["q"], "answer": a} for q, a in zip(questions, answers)]
    ai_result = _ai_score_interview(subject_name, level, qa)
    if ai_result:
        return (ai_result["scores"], ai_result["overall"],
                ai_result["strengths"], ai_result["improvements"], True)
    scored = []
    for q, a in zip(questions, answers):
        s, fb = _fallback_score(q, a)
        scored.append({"score": s, "feedback": fb})
    overall = round(sum(s["score"] for s in scored) / max(len(scored), 1), 1)
    if overall >= 8:
        strengths, improvements = (
            "Solid conceptual clarity and well-structured answers.",
            "Push for depth: add real-world examples and edge cases to stand out.")
    elif overall >= 6:
        strengths, improvements = (
            "Good foundation — most core concepts are in place.",
            "Add concrete examples and cover the missing keywords flagged per question.")
    else:
        strengths, improvements = (
            "Willingness to attempt every question is a good start.",
            "Study the fundamentals topic by topic, then re-attempt. Aim for 3–5 sentence answers with examples.")
    return scored, overall, strengths, improvements, False


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def dispatch(subpath: str, student: dict, data: dict, ip: str) -> tuple[dict, int]:
    sid = student.get("student_id") or student.get("username", "")
    rl_key = f"career:{sid}:{subpath}"

    def need_rl(limit: int, window: int = 3600):
        if not _rate_ok(rl_key, limit, window):
            return {"ok": False, "error": "too_many_requests"}, 429
        return None

    if subpath == "subjects":
        return {"ok": True, "subjects": SUBJECTS, "ai": ai_enabled()}, 200

    # ---------------- Mock interviews ----------------
    if subpath == "interview-start":
        r = need_rl(10)
        if r:
            return r
        subject = (data.get("subject") or "").strip()
        level = (data.get("level") or "mixed").strip()
        try:
            count = int(data.get("count", 5))
        except Exception:
            count = 5
        count = max(3, min(10, count))
        if subject not in _SUBJECT_IDS:
            return {"ok": False, "error": "invalid_subject"}, 400
        if level not in LEVELS:
            level = "mixed"
        pool = [q for q in QUESTIONS[subject]
                if level == "mixed" or q["level"] == level]
        if not pool:
            pool = QUESTIONS[subject]
        picked = random.sample(pool, min(count, len(pool)))
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            if prof["active_interview"]:
                prof["active_interview"]["status"] = "abandoned"
            iv = {
                "id": secrets.token_hex(4),
                "subject": subject,
                "level": level,
                "questions": [{"q": q["q"], "keywords": q["keywords"]} for q in picked],
                "answers": [],
                "status": "open",
                "created_at": _now_iso(),
            }
            prof["active_interview"] = iv
            _save(store)
        return {"ok": True, "interview_id": iv["id"], "total": len(iv["questions"]),
                "question": iv["questions"][0]["q"], "n": 1,
                "ai": ai_enabled()}, 200

    if subpath == "interview-answer":
        r = need_rl(100)
        if r:
            return r
        iid = (data.get("interview_id") or "").strip()
        answer = (data.get("answer") or "").strip()
        if not (1 <= len(answer) <= 2000):
            return {"ok": False, "error": "invalid_answer"}, 400
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            iv = prof["active_interview"]
            if not iv or iv.get("id") != iid or iv.get("status") != "open":
                return {"ok": False, "error": "no_active_interview"}, 400
            if len(iv["answers"]) >= len(iv["questions"]):
                return {"ok": True, "done": True}, 200
            iv["answers"].append({"answer": answer, "at": _now_iso()})
            _save(store)
            done = len(iv["answers"]) >= len(iv["questions"])
            if done:
                return {"ok": True, "done": True}, 200
            n = len(iv["answers"]) + 1
            return {"ok": True, "done": False, "n": n,
                    "total": len(iv["questions"]),
                    "question": iv["questions"][n - 1]["q"]}, 200

    if subpath == "interview-finish":
        r = need_rl(10)
        if r:
            return r
        iid = (data.get("interview_id") or "").strip()
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            iv = prof["active_interview"]
            if not iv or iv.get("id") != iid or iv.get("status") != "open":
                return {"ok": False, "error": "no_active_interview"}, 400
            if len(iv["answers"]) < len(iv["questions"]):
                return {"ok": False, "error": "incomplete"}, 400
            subject_name = next(s["name"] for s in SUBJECTS if s["id"] == iv["subject"])
            answers = [a["answer"] for a in iv["answers"]]
            scored, overall, strengths, improvements, used_ai = _score_interview(
                subject_name, iv["level"], iv["questions"], answers)
            record = {
                "id": iv["id"],
                "subject": iv["subject"],
                "subject_name": subject_name,
                "level": iv["level"],
                "at": _now_iso(),
                "overall": overall,
                "ai": used_ai,
                "items": [
                    {"q": q["q"], "answer": a,
                     "score": s["score"], "feedback": s["feedback"]}
                    for q, a, s in zip(iv["questions"], answers, scored)
                ],
                "strengths": strengths,
                "improvements": improvements,
            }
            prof["interviews"].insert(0, record)
            prof["interviews"] = prof["interviews"][:20]
            prof["active_interview"] = None
            _save(store)
        return {"ok": True, "result": record}, 200

    if subpath == "interview-history":
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            hist = [{
                "id": h["id"], "subject_name": h.get("subject_name", h["subject"]),
                "at": h["at"], "overall": h["overall"], "ai": h.get("ai", False),
                "count": len(h.get("items", [])),
            } for h in prof["interviews"]]
        return {"ok": True, "history": hist}, 200

    if subpath == "interview-detail":
        iid = (data.get("interview_id") or "").strip()
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            rec = next((h for h in prof["interviews"] if h["id"] == iid), None)
        if not rec:
            return {"ok": False, "error": "not_found"}, 404
        return {"ok": True, "result": rec}, 200

    # ---------------- Resume ----------------
    if subpath == "resume-get":
        with _lock:
            store = _load()
            resume = _profile(store, sid)["resume"]
        return {"ok": True, "resume": resume, "ai": ai_enabled()}, 200

    if subpath == "resume-save":
        r = need_rl(60)
        if r:
            return r
        resume = data.get("resume")
        if not isinstance(resume, dict) or len(json.dumps(resume)) > 50000:
            return {"ok": False, "error": "invalid_resume"}, 400
        clean = {k: str(resume.get(k, ""))[:5000]
                 for k in ("name", "email", "phone", "city", "summary",
                           "skills", "experience", "education", "projects")}
        clean["updated_at"] = _now_iso()
        with _lock:
            store = _load()
            _profile(store, sid)["resume"] = clean
            _save(store)
        return {"ok": True}, 200

    if subpath == "resume-enhance":
        r = need_rl(30)
        if r:
            return r
        kind = (data.get("kind") or "").strip()
        text = (data.get("text") or "").strip()
        if kind not in ("summary", "skills", "experience", "education", "projects"):
            return {"ok": False, "error": "invalid_kind"}, 400
        if not (3 <= len(text) <= 4000):
            return {"ok": False, "error": "invalid_text"}, 400
        prompts = {
            "summary": "Rewrite this resume professional summary into 2–3 crisp, confident lines suitable for an IT fresher in India. Keep every fact truthful — do not invent experience. Return ONLY the rewritten summary.",
            "skills": "Convert these into a clean, comma-separated ATS-friendly skills list, grouped logically if helpful (e.g. Languages, Tools). Return ONLY the list.",
            "experience": "Rewrite these into strong resume bullet points, each starting with an action verb (Built, Developed, Automated…). Keep every fact truthful — do not invent anything. Return ONLY the bullets, one per line.",
            "education": "Format this education information cleanly for a resume: degree, institute, year, score. Return ONLY the formatted text.",
            "projects": "Rewrite these project descriptions as crisp resume entries: project name, one-line purpose, tech stack, and outcome. Keep facts truthful. Return ONLY the rewritten text.",
        }
        enhanced = _ai_chat(
            "You are an expert resume writer for Indian IT freshers. "
            "Never invent experience, degrees or achievements.",
            f"{prompts[kind]}\n\nInput:\n{text}",
            max_tokens=600, timeout=45)
        if enhanced:
            return {"ok": True, "enhanced": enhanced, "ai": True}, 200
        return {"ok": True, "enhanced": _ENHANCE_TIPS[kind], "ai": False}, 200

    # ---------------- Readiness checklist ----------------
    if subpath == "checklist-get":
        subject = (data.get("subject") or "").strip()
        if subject not in _SUBJECT_IDS:
            return {"ok": False, "error": "invalid_subject"}, 400
        items = ([{"id": f"g{i}", "label": l} for i, l in enumerate(GENERAL_CHECKLIST)]
                 + [{"id": f"s{i}", "label": l} for i, l in enumerate(SUBJECT_CHECKLISTS[subject])])
        with _lock:
            store = _load()
            checked = _profile(store, sid)["checklist"].get(subject, [])
        return {"ok": True, "items": items, "checked": checked}, 200

    if subpath == "checklist-save":
        r = need_rl(60)
        if r:
            return r
        subject = (data.get("subject") or "").strip()
        checked = data.get("checked")
        if subject not in _SUBJECT_IDS or not isinstance(checked, list):
            return {"ok": False, "error": "invalid_request"}, 400
        valid = {f"g{i}" for i in range(len(GENERAL_CHECKLIST))} | \
                {f"s{i}" for i in range(len(SUBJECT_CHECKLISTS[subject]))}
        checked = [c for c in checked if c in valid][:50]
        with _lock:
            store = _load()
            _profile(store, sid)["checklist"][subject] = checked
            _save(store)
        return {"ok": True, "progress": round(100 * len(checked) /
                (len(GENERAL_CHECKLIST) + len(SUBJECT_CHECKLISTS[subject])))}, 200

    # ---------------- Portfolio ----------------
    if subpath == "portfolio-list":
        with _lock:
            store = _load()
            items = _profile(store, sid)["portfolio"]
        return {"ok": True, "items": items}, 200

    if subpath == "portfolio-add":
        r = need_rl(60)
        if r:
            return r
        title = (data.get("title") or "").strip()
        desc = (data.get("description") or "").strip()
        tech = (data.get("tech") or "").strip()
        link = (data.get("link") or "").strip()
        if not (2 <= len(title) <= 120) or len(desc) > 2000 or len(link) > 500:
            return {"ok": False, "error": "invalid_request"}, 400
        if link and not re.match(r"^https?://", link):
            link = "https://" + link
        item = {"id": secrets.token_hex(4), "title": title, "description": desc,
                "tech": tech[:300], "link": link, "at": _now_iso()}
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            prof["portfolio"].insert(0, item)
            prof["portfolio"] = prof["portfolio"][:50]
            _save(store)
        return {"ok": True, "item": item}, 200

    if subpath == "portfolio-delete":
        pid = (data.get("id") or "").strip()
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            prof["portfolio"] = [p for p in prof["portfolio"] if p["id"] != pid]
            _save(store)
        return {"ok": True}, 200

    # ---------------- Job tracker (no invented listings) ----------------
    if subpath == "jobs-meta":
        return {"ok": True, "platforms": JOB_PLATFORMS,
                "statuses": JOB_STATUSES}, 200

    if subpath == "jobs-list":
        with _lock:
            store = _load()
            jobs = _profile(store, sid)["jobs"]
        return {"ok": True, "jobs": jobs}, 200

    if subpath == "jobs-add":
        r = need_rl(60)
        if r:
            return r
        company = (data.get("company") or "").strip()
        role = (data.get("role") or "").strip()
        platform = (data.get("platform") or "").strip()[:80]
        status = (data.get("status") or "Wishlist").strip()
        date = (data.get("date") or "").strip()[:20]
        notes = (data.get("notes") or "").strip()[:1000]
        if not (2 <= len(company) <= 120) or not (2 <= len(role) <= 120):
            return {"ok": False, "error": "invalid_request"}, 400
        if status not in JOB_STATUSES:
            status = "Wishlist"
        job = {"id": secrets.token_hex(4), "company": company, "role": role,
               "platform": platform, "status": status, "date": date,
               "notes": notes, "at": _now_iso()}
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            prof["jobs"].insert(0, job)
            prof["jobs"] = prof["jobs"][:200]
            _save(store)
        return {"ok": True, "job": job}, 200

    if subpath == "jobs-update":
        jid = (data.get("id") or "").strip()
        status = (data.get("status") or "").strip()
        if status not in JOB_STATUSES:
            return {"ok": False, "error": "invalid_status"}, 400
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            for j in prof["jobs"]:
                if j["id"] == jid:
                    j["status"] = status
            _save(store)
        return {"ok": True}, 200

    if subpath == "jobs-delete":
        jid = (data.get("id") or "").strip()
        with _lock:
            store = _load()
            prof = _profile(store, sid)
            prof["jobs"] = [j for j in prof["jobs"] if j["id"] != jid]
            _save(store)
        return {"ok": True}, 200

    return {"ok": False, "error": "not_found"}, 404
