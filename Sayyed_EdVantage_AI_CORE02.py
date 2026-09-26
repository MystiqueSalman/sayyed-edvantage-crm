"""
Sayyed EdVantage AI Agent — AI Core 02
Conversation Context & Session Memory Contract

Purpose:
- Add structured, session-scoped conversation context above AI Core 01.
- Preserve prior turns without inventing facts.
- Track active course IDs and the latest intent from actual Agent Core results.
- Allow follow-up questions to reuse context when the user does not restate it.
- Keep session isolation, provenance, handoff, and read-only safety intact.
- This batch does not add CRM memory, long-term personal memory, messaging,
  external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_AI_CORE01 import (
    AgentSessionState,
    AgentRuntimeResult,
    AgentTurn,
    RUNTIME_READY,
    RUNTIME_HANDOFF,
    RUNTIME_BLOCKED,
    create_session,
    run_agent_turn,
    validate_session_state,
    build_agent_runtime,
)


CONTEXT_READY = "CONTEXT_READY"
CONTEXT_EMPTY = "CONTEXT_EMPTY"
CONTEXT_HANDOFF = "CONTEXT_HANDOFF"


@dataclass
class ConversationContext:
    session_id: str
    turn_count: int = 0
    active_course_ids: List[str] = field(default_factory=list)
    active_intent: str = ""
    recent_user_messages: List[str] = field(default_factory=list)
    recent_responses: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    handoff_required: bool = False
    context_status: str = CONTEXT_EMPTY


@dataclass
class ContextRuntimeResult:
    runtime_result: AgentRuntimeResult
    context: ConversationContext
    effective_query: str
    context_used: bool
    errors: List[str] = field(default_factory=list)


def _unique(values):
    return list(dict.fromkeys(values))


def _safe_copy(value):
    return copy.deepcopy(value)


def create_conversation_context(session_id: str) -> ConversationContext:
    return ConversationContext(session_id=session_id)


def context_from_session(state: AgentSessionState) -> ConversationContext:
    if state.turns:
        messages = [t.user_message for t in state.turns]
        responses = [t.response for t in state.turns]
        sources = []
        for t in state.turns:
            sources.extend(t.source_ids)
    else:
        messages, responses, sources = [], [], []

    return ConversationContext(
        session_id=state.session_id,
        turn_count=state.turn_count,
        active_course_ids=_unique(list(state.active_course_ids)),
        active_intent=state.active_intent,
        recent_user_messages=messages[-10:],
        recent_responses=responses[-10:],
        source_ids=_unique(sources),
        handoff_required=state.handoff_required,
        context_status=CONTEXT_READY if state.turn_count else CONTEXT_EMPTY,
    )


def _select_course_context(
    context: ConversationContext,
    result: AgentRuntimeResult,
) -> List[str]:
    """
    Keep only the most relevant course context rather than blindly storing
    every course returned by broad retrieval. This prevents unrelated
    retrieval candidates from leaking into a session's active course state.
    """
    if not result.course_ids:
        return list(context.active_course_ids)

    # If an active course already exists, preserve it. Follow-up turns should
    # not replace established session context with secondary retrieval hits.
    if context.active_course_ids:
        return list(context.active_course_ids)

    # On a cold-start turn, the first returned course is the primary course
    # selected by the upstream deterministic retrieval/ranking layer.
    return [result.course_ids[0]]


def update_conversation_context(
    context: ConversationContext,
    result: AgentRuntimeResult,
) -> ConversationContext:
    context.turn_count += 1

    context.active_course_ids = _unique(
        _select_course_context(context, result)
    )

    if result.intent:
        context.active_intent = result.intent

    if result.user_message:
        context.recent_user_messages = (
            context.recent_user_messages + [result.user_message]
        )[-10:]

    # Only store response text when it was actually delivered.
    if result.response:
        context.recent_responses = (
            context.recent_responses + [result.response]
        )[-10:]

    context.source_ids = _unique(
        context.source_ids + list(result.source_ids)
    )
    context.handoff_required = (
        context.handoff_required or result.human_handoff_required
    )
    context.context_status = CONTEXT_READY
    return context


def validate_conversation_context(
    context: ConversationContext,
) -> Dict[str, Any]:
    errors = []

    if not context.session_id.strip():
        errors.append("Context session ID cannot be empty.")

    if context.turn_count < 0:
        errors.append("Context turn count cannot be negative.")

    if len(context.recent_user_messages) > 10:
        errors.append("Recent user-message window cannot exceed 10.")

    if len(context.recent_responses) > 10:
        errors.append("Recent response window cannot exceed 10.")

    if context.context_status not in {
        CONTEXT_READY,
        CONTEXT_EMPTY,
        CONTEXT_HANDOFF,
    }:
        errors.append("Invalid context status.")

    if context.turn_count == 0 and context.context_status != CONTEXT_EMPTY:
        errors.append("Zero-turn context must be CONTEXT_EMPTY.")

    if context.turn_count > 0 and context.context_status == CONTEXT_EMPTY:
        errors.append("Non-empty context cannot be CONTEXT_EMPTY.")

    return {"valid": not errors, "errors": _unique(errors)}


def build_contextual_query(
    user_message: str,
    context: ConversationContext,
) -> str:
    """
    Build a deterministic query representation.

    The original user message always remains the primary query. Context is
    appended only as explicit prior context; no new facts are invented.
    """
    message = str(user_message).strip()
    if not message:
        return ""

    if context.context_status == CONTEXT_EMPTY:
        return message

    parts = [message]

    if context.active_course_ids:
        parts.append(
            "Prior active course context: "
            + ", ".join(context.active_course_ids)
        )

    if context.active_intent:
        parts.append(
            "Prior active intent: " + context.active_intent
        )

    if context.recent_user_messages:
        parts.append(
            "Recent user context: "
            + " | ".join(context.recent_user_messages[-3:])
        )

    return "\n".join(parts)


def run_contextual_turn(
    kb: Any,
    state: AgentSessionState,
    context: ConversationContext,
    user_message: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> ContextRuntimeResult:
    errors = []

    state_validation = validate_session_state(state)
    context_validation = validate_conversation_context(context)
    errors.extend(state_validation["errors"])
    errors.extend(context_validation["errors"])

    if context.session_id != state.session_id:
        errors.append("Context/session ID mismatch.")

    if errors:
        blocked = run_agent_turn(kb, state, " ")
        blocked.response = ""
        blocked.runtime_status = RUNTIME_BLOCKED
        blocked.human_handoff_required = True
        blocked.errors = _unique(errors)
        return ContextRuntimeResult(
            runtime_result=blocked,
            context=_safe_copy(context),
            effective_query="",
            context_used=False,
            errors=_unique(errors),
        )

    effective_query = build_contextual_query(user_message, context)
    context_used = context.context_status != CONTEXT_EMPTY

    result = run_agent_turn(
        kb,
        state,
        effective_query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )

    updated = update_conversation_context(context, result)

    if result.runtime_status == RUNTIME_HANDOFF:
        updated.context_status = CONTEXT_HANDOFF

    return ContextRuntimeResult(
        runtime_result=result,
        context=_safe_copy(updated),
        effective_query=effective_query,
        context_used=context_used,
        errors=_unique(result.errors),
    )


def contextual_query(
    kb: Any,
    query: str,
    session_id: Optional[str] = None,
    top_k: int = 10,
) -> ContextRuntimeResult:
    state = create_session(session_id)
    context = create_conversation_context(state.session_id)
    return run_contextual_turn(kb, state, context, query, top_k=top_k)


def context_to_dict(context: ConversationContext) -> Dict[str, Any]:
    return {
        "session_id": context.session_id,
        "turn_count": context.turn_count,
        "active_course_ids": list(context.active_course_ids),
        "active_intent": context.active_intent,
        "recent_user_messages": list(context.recent_user_messages),
        "recent_responses": list(context.recent_responses),
        "source_ids": list(context.source_ids),
        "handoff_required": context.handoff_required,
        "context_status": context.context_status,
    }


def contextual_result_to_dict(
    result: ContextRuntimeResult,
) -> Dict[str, Any]:
    return {
        "runtime_result": {
            "session_id": result.runtime_result.session_id,
            "turn_id": result.runtime_result.turn_id,
            "user_message": result.runtime_result.user_message,
            "response": result.runtime_result.response,
            "runtime_status": result.runtime_result.runtime_status,
            "integration_status": result.runtime_result.integration_status,
            "intent": result.runtime_result.intent,
            "course_ids": list(result.runtime_result.course_ids),
            "source_ids": list(result.runtime_result.source_ids),
            "human_handoff_required": result.runtime_result.human_handoff_required,
            "safety": copy.deepcopy(result.runtime_result.safety),
            "errors": list(result.runtime_result.errors),
        },
        "context": context_to_dict(result.context),
        "effective_query": result.effective_query,
        "context_used": result.context_used,
        "errors": list(result.errors),
    }


def validate_contextual_result(
    result: ContextRuntimeResult,
) -> Dict[str, Any]:
    errors = []

    errors.extend(validate_conversation_context(result.context)["errors"])

    runtime = result.runtime_result
    if runtime.session_id != result.context.session_id:
        errors.append("Result/context session mismatch.")

    if result.context_used and result.context.context_status == CONTEXT_EMPTY:
        errors.append("Context-used result cannot have empty context.")

    if runtime.runtime_status in {RUNTIME_HANDOFF, RUNTIME_BLOCKED}:
        if runtime.response.strip():
            errors.append("Handoff/blocked contextual result cannot expose text.")

    for key, expected in {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "no_invention": True,
    }.items():
        if runtime.safety.get(key) is not expected:
            errors.append(f"Safety invariant failed: {key}.")

    return {"valid": not errors, "errors": _unique(errors)}


def build_conversation_memory_layer() -> Any:
    return build_agent_runtime()


# Explicit aliases.
update_context = update_conversation_context
run_with_context = run_contextual_turn
