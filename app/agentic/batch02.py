from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.ai import agent as existing_agent
from app.ai.memory import load_memory
from app.agentic.models import AgentContext, Task
from Sayyed_EdVantage_PHASE4_INTEGRATION06_V2 import get_master_kb_pricing
from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge


def _normal(value: Any) -> str:
    cleaned = re.sub(r"[^\w]+", " ", str(value or "").lower())
    return " ".join(cleaned.split())


def _course_candidates(request: str) -> list[dict[str, Any]]:
    bridge = build_authoritative_live_bridge(
        project_root=str(Path(__file__).resolve().parents[2]),
        require_offerings=True,
    )
    if bridge.status != "BRIDGE_READY":
        raise RuntimeError("AUTHORITATIVE_MASTER_KB_UNAVAILABLE")
    query = _normal(request)
    candidates = []
    for course in bridge.courses:
        if not isinstance(course, dict):
            continue
        values = [course.get("course_id"), course.get("official_name"), course.get("course_name")]
        aliases = course.get("aliases", [])
        if isinstance(aliases, list):
            values.extend(aliases)
        matched = False
        for value in values:
            normalized = _normal(value)
            if not normalized:
                continue
            meaningful_tokens = [
                token for token in normalized.split()
                if token not in {"professional", "program", "course"}
            ]
            if normalized in query or all(token in query for token in meaningful_tokens):
                matched = True
                break
        if matched:
            candidates.append({
                "course_id": course.get("course_id"),
                "course_name": course.get("official_name") or course.get("course_name"),
            })
    if candidates:
        return candidates

    detected = existing_agent._detect_course_from_text(request)
    if detected:
        return [{
            "course_id": None,
            "course_name": detected,
            "verified": False,
        }]
    return []


def _crm_context(task: Task, context: AgentContext) -> dict[str, Any]:
    if context.crm_state:
        return dict(context.crm_state)
    history = existing_agent._build_conversation_history(
        list(context.conversation_history) or load_memory(context.session_id or "default_student")
    )
    lead = existing_agent._find_existing_lead_from_text(history, task.user_request)
    return dict(lead) if isinstance(lead, dict) else {}


def _intent(request: str, agent_id: str) -> str:
    value = _normal(request)
    if re.search(r"\b(admission|admit|enroll|enrol|join|apply)\b", value):
        return "admission_intent"
    if re.search(r"\b(fee|fees|price|pricing|cost|how much)\b", value):
        return "pricing_question"
    if re.search(r"\b(eligible|eligibility|qualification|qualify)\b", value):
        return "eligibility_question"
    if re.search(r"\b(compare|which course|suitable|recommend|don't know|do not know)\b", value):
        return "course_recommendation"
    return "course_information" if agent_id == "SALES" else "counselling_question"


def _build_output(agent_id: str, task: Task, context: AgentContext, response: str, candidates: list[dict[str, Any]], intent: str) -> dict[str, Any]:
    crm = _crm_context(task, context)
    admission = intent == "admission_intent"
    handoff = admission or intent == "eligibility_question" or (not candidates and intent == "course_recommendation")
    evidence = ["existing_ai_core", "authoritative_master_kb", "existing_conversation_memory"]
    if any(candidate.get("verified") is False for candidate in candidates):
        evidence.append("course_interest_detected_existing_ai_unverified")
    if crm:
        evidence.append("existing_crm_read")
    course_name = candidates[0].get("course_name") if candidates else None
    if course_name and intent == "pricing_question":
        country = str(crm.get("country") or "India")
        international = country.strip().lower() not in {"", "india", "indian"}
        pricing = get_master_kb_pricing(course_name, international=international, region=country)
        if pricing is not None:
            evidence.append("existing_pricing_gateway")
        elif international:
            evidence.append("international_pricing_requires_admissions_confirmation")
    return {
        "agent_id": agent_id,
        "status": "completed",
        "response": response,
        "intent": intent,
        "course_candidates": candidates,
        "recommended_next_step": "human_counsellor_handoff" if handoff else "continue_guided_conversation",
        "admission_readiness": "ready_for_counselling" if admission else "exploring",
        "human_handoff_required": handoff,
        "evidence": evidence,
        "authorization_required": False,
        "actions_requested": [],
        "errors": [],
    }


def run_existing_ai(agent_id: str, task: Task, context: AgentContext) -> dict[str, Any]:
    try:
        candidates = _course_candidates(task.user_request)
        intent = _intent(task.user_request, agent_id)
        response = existing_agent.ask_agent(
            task.user_request,
            session_id=context.session_id or "default_student",
            allow_lead_creation=False,
        )
        return _build_output(agent_id, task, context, response, candidates, intent)
    except Exception as exc:
        return {
            "agent_id": agent_id,
            "status": "failed",
            "response": "",
            "intent": _intent(task.user_request, agent_id),
            "course_candidates": [],
            "recommended_next_step": "human_counsellor_handoff",
            "admission_readiness": "unknown",
            "human_handoff_required": True,
            "evidence": [],
            "authorization_required": False,
            "actions_requested": [],
            "errors": [str(exc)],
        }