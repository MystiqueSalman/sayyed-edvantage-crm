"""
Sayyed EdVantage AI Agent — AI Core 03
Intent & Conversation Understanding Contract

Purpose:
- Add a deterministic understanding layer above AI Core 02.
- Classify common admissions conversations without inventing facts.
- Detect course references using explicit course aliases/names.
- Detect broad user intent categories used by the existing Master KB answer layer.
- Preserve session context when the user uses follow-up language.
- Keep ambiguous cases explicit rather than guessing.
- This batch is analysis/orchestration only: no CRM writes, messaging,
  external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re
import copy

from Sayyed_EdVantage_AI_CORE02 import (
    ConversationContext,
    ContextRuntimeResult,
    create_conversation_context,
    run_contextual_turn,
    validate_conversation_context,
    build_conversation_memory_layer,
)


INTENT_UNKNOWN = "unknown"
INTENT_PROGRAM_INFORMATION = "program_information"
INTENT_COMMERCIAL = "commercial"
INTENT_ELIGIBILITY = "eligibility"
INTENT_CERTIFICATION = "certification"
INTENT_CAREER = "career"
INTENT_ASSESSMENT_PROJECTS = "assessment_projects"
INTENT_TOOLS = "tools"
INTENT_RECOMMENDATION = "course_recommendation"
INTENT_GENERAL = "general_information"


@dataclass
class UnderstandingResult:
    user_message: str
    normalized_message: str
    intent: str
    confidence: str
    explicit_course_ids: List[str] = field(default_factory=list)
    context_course_ids: List[str] = field(default_factory=list)
    effective_course_ids: List[str] = field(default_factory=list)
    context_used: bool = False
    ambiguous: bool = False
    ambiguity_reason: str = ""
    signals: List[str] = field(default_factory=list)


@dataclass
class UnderstoodTurnResult:
    understanding: UnderstandingResult
    contextual_result: ContextRuntimeResult
    errors: List[str] = field(default_factory=list)


COURSE_ALIASES = {
    "SE-DS-001": [
        "data science",
        "data scientist",
        "data science course",
    ],
    "SE-DA-001": [
        "data analytics",
        "data analyst",
        "data analytics course",
    ],
    "SE-AIGEN-001": [
        "ai + generative ai",
        "ai and generative ai",
        "generative ai",
        "gen ai",
        "genai",
    ],
    "SE-PY-001": [
        "python",
        "python programming",
        "python course",
    ],
    "SE-LINUX-001": [
        "linux",
        "linux administration",
        "linux admin",
        "linux course",
    ],
    "SE-DEVOPS-001": [
        "devops",
        "devops course",
    ],
    "SE-EHC-001": [
        "ethical hacking",
        "cybersecurity",
        "cyber security",
        "ethical hacking and cybersecurity",
        "ethical hacking & cybersecurity",
    ],
}


INTENT_PATTERNS = {
    INTENT_COMMERCIAL: [
        "fee", "fees", "price", "pricing", "cost", "how much",
        "payment", "emi", "installment", "discount", "gst", "tax",
    ],
    INTENT_ELIGIBILITY: [
        "eligib", "eligible", "qualification", "qualifications",
        "requirement", "requirements", "prerequisite", "prerequisites",
        "background", "fresher", "experience",
    ],
    INTENT_CERTIFICATION: [
        "certificate", "certification", "certified",
    ],
    INTENT_CAREER: [
        "career", "job", "jobs", "placement", "salary", "income",
        "role", "roles", "career path", "employment",
    ],
    INTENT_ASSESSMENT_PROJECTS: [
        "project", "projects", "assessment", "exam", "capstone",
        "assignment", "evaluation",
    ],
    INTENT_TOOLS: [
        "tools", "software", "technology", "technologies", "stack",
        "framework", "frameworks",
    ],
    INTENT_RECOMMENDATION: [
        "which course", "what course", "best course", "recommend",
        "recommendation", "should i choose", "which should i choose",
        "suitable course", "right course",
    ],
    INTENT_PROGRAM_INFORMATION: [
        "course", "curriculum", "syllabus", "module", "modules",
        "duration", "hours", "learn", "teaching", "training",
        "online", "live", "program",
    ],
}


def normalize_message(message: str) -> str:
    return re.sub(r"\s+", " ", str(message).strip().lower())


def detect_explicit_courses(message: str) -> List[str]:
    normalized = normalize_message(message)
    matches = []
    for course_id, aliases in COURSE_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                matches.append(course_id)
                break
    return matches


def detect_intent(message: str) -> Dict[str, Any]:
    normalized = normalize_message(message)
    scores = {intent: 0 for intent in INTENT_PATTERNS}
    signals = []

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized:
                scores[intent] += 1
                signals.append(f"{intent}:{pattern}")

    # Strong phrase matches take priority over generic program-information
    # words such as "course" or "program".
    priority = [
        INTENT_RECOMMENDATION,
        INTENT_COMMERCIAL,
        INTENT_ELIGIBILITY,
        INTENT_CERTIFICATION,
        INTENT_CAREER,
        INTENT_ASSESSMENT_PROJECTS,
        INTENT_TOOLS,
        INTENT_PROGRAM_INFORMATION,
    ]

    best = max(scores.values()) if scores else 0
    if best == 0:
        return {
            "intent": INTENT_UNKNOWN,
            "confidence": "LOW",
            "signals": [],
        }

    candidates = [intent for intent, score in scores.items() if score == best]

    if len(candidates) > 1:
        for intent in priority:
            if intent in candidates:
                return {
                    "intent": intent,
                    "confidence": "MEDIUM",
                    "signals": signals,
                }

    confidence = "HIGH" if best >= 2 else "MEDIUM"
    return {
        "intent": candidates[0],
        "confidence": confidence,
        "signals": signals,
    }


def understand_message(
    message: str,
    context: Optional[ConversationContext] = None,
) -> UnderstandingResult:
    normalized = normalize_message(message)
    explicit = detect_explicit_courses(normalized)
    intent_info = detect_intent(normalized)

    context_courses = (
        list(context.active_course_ids)
        if context is not None
        else []
    )

    effective = list(explicit)

    context_used = False
    ambiguous = False
    ambiguity_reason = ""

    if explicit:
        if len(explicit) > 1:
            ambiguous = True
            ambiguity_reason = "Multiple courses were explicitly referenced."
    elif context_courses:
        # Follow-up questions can reuse a previously established course.
        effective = list(context_courses)
        context_used = True

    if not explicit and not context_courses:
        if intent_info["intent"] in {
            INTENT_COMMERCIAL,
            INTENT_CERTIFICATION,
            INTENT_CAREER,
            INTENT_TOOLS,
            INTENT_ASSESSMENT_PROJECTS,
        }:
            ambiguous = True
            ambiguity_reason = (
                "The message has a specific intent but no explicit course "
                "or established course context."
            )

    return UnderstandingResult(
        user_message=str(message).strip(),
        normalized_message=normalized,
        intent=intent_info["intent"],
        confidence=intent_info["confidence"],
        explicit_course_ids=explicit,
        context_course_ids=context_courses,
        effective_course_ids=effective,
        context_used=context_used,
        ambiguous=ambiguous,
        ambiguity_reason=ambiguity_reason,
        signals=intent_info["signals"],
    )


def validate_understanding(
    result: UnderstandingResult,
) -> Dict[str, Any]:
    errors = []

    if not result.user_message.strip():
        errors.append("User message cannot be empty.")

    if result.intent not in {
        INTENT_UNKNOWN,
        INTENT_PROGRAM_INFORMATION,
        INTENT_COMMERCIAL,
        INTENT_ELIGIBILITY,
        INTENT_CERTIFICATION,
        INTENT_CAREER,
        INTENT_ASSESSMENT_PROJECTS,
        INTENT_TOOLS,
        INTENT_RECOMMENDATION,
        INTENT_GENERAL,
    }:
        errors.append("Invalid intent.")

    if result.confidence not in {"LOW", "MEDIUM", "HIGH"}:
        errors.append("Invalid confidence.")

    if result.ambiguous and not result.ambiguity_reason:
        errors.append("Ambiguous result requires a reason.")

    if result.context_used and not result.context_course_ids:
        errors.append("Context-used result requires context course IDs.")

    if result.effective_course_ids:
        allowed = set(result.explicit_course_ids + result.context_course_ids)
        if not set(result.effective_course_ids).issubset(allowed):
            errors.append("Effective course IDs contain unsupported values.")

    return {"valid": not errors, "errors": list(dict.fromkeys(errors))}


def run_understood_turn(
    kb: Any,
    state: Any,
    context: ConversationContext,
    user_message: str,
    top_k: int = 10,
) -> UnderstoodTurnResult:
    understanding = understand_message(user_message, context)

    errors = list(validate_understanding(understanding)["errors"])
    errors.extend(validate_conversation_context(context)["errors"])

    if context.session_id != state.session_id:
        errors.append("Context/session ID mismatch.")

    if errors:
        # Do not manufacture an answer. The contextual runtime itself is
        # invoked with an empty message solely to create a controlled blocked
        # runtime result; the returned answer remains empty.
        contextual = run_contextual_turn(kb, state, context, " ")
        contextual.runtime_result.response = ""
        contextual.runtime_result.errors = list(
            dict.fromkeys(errors)
        )
        return UnderstoodTurnResult(
            understanding=understanding,
            contextual_result=contextual,
            errors=list(dict.fromkeys(errors)),
        )

    # When a course is explicitly identified, pass it as a course filter.
    # When the message is a follow-up, preserve established context by using
    # the first active course as the deterministic filter.
    selected_course = (
        understanding.effective_course_ids[0]
        if len(understanding.effective_course_ids) == 1
        else None
    )

    contextual = run_contextual_turn(
        kb,
        state,
        context,
        user_message,
        top_k=top_k,
        course_id=selected_course,
    )

    errors.extend(contextual.errors)

    # Multiple explicit courses remain visible as an ambiguity signal, while
    # the underlying KB layer is allowed to handle multi-course evidence.
    if len(understanding.explicit_course_ids) > 1:
        understanding.ambiguous = True
        understanding.ambiguity_reason = (
            "Multiple courses were explicitly referenced; preserve them "
            "as separate evidence rather than selecting one silently."
        )

    return UnderstoodTurnResult(
        understanding=understanding,
        contextual_result=contextual,
        errors=list(dict.fromkeys(errors)),
    )


def understanding_to_dict(
    result: UnderstandingResult,
) -> Dict[str, Any]:
    return {
        "user_message": result.user_message,
        "normalized_message": result.normalized_message,
        "intent": result.intent,
        "confidence": result.confidence,
        "explicit_course_ids": list(result.explicit_course_ids),
        "context_course_ids": list(result.context_course_ids),
        "effective_course_ids": list(result.effective_course_ids),
        "context_used": result.context_used,
        "ambiguous": result.ambiguous,
        "ambiguity_reason": result.ambiguity_reason,
        "signals": list(result.signals),
    }


def understood_result_to_dict(
    result: UnderstoodTurnResult,
) -> Dict[str, Any]:
    return {
        "understanding": understanding_to_dict(result.understanding),
        "effective_query": result.contextual_result.effective_query,
        "context_used": result.contextual_result.context_used,
        "runtime_status": result.contextual_result.runtime_result.runtime_status,
        "response": result.contextual_result.runtime_result.response,
        "source_ids": list(
            result.contextual_result.runtime_result.source_ids
        ),
        "errors": list(result.errors),
    }


def validate_understood_turn(
    result: UnderstoodTurnResult,
) -> Dict[str, Any]:
    errors = list(validate_understanding(result.understanding)["errors"])
    errors.extend(
        validate_conversation_context(
            result.contextual_result.context
        )["errors"]
    )
    return {"valid": not errors, "errors": list(dict.fromkeys(errors))}


def build_understanding_layer() -> Any:
    return build_conversation_memory_layer()


def understanding_query(
    kb: Any,
    query: str,
    session_id: Optional[str] = None,
) -> UnderstoodTurnResult:
    state = __import__(
        "Sayyed_EdVantage_AI_CORE01",
        fromlist=["create_session"],
    ).create_session(session_id)
    context = create_conversation_context(state.session_id)
    return run_understood_turn(kb, state, context, query)
