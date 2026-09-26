"""Sayyed EdVantage Phase 4 Integration 09 — Live Conversation API.

Provides the clean application-facing API above the Phase 4 Integration 08
session manager. A caller supplies a session_id and message; the API keeps the
session/lead identity bound and returns a safe conversation result.

This layer does NOT send messages, write CRM data, invoke an executor, or take
external actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from copy import deepcopy

from Sayyed_EdVantage_PHASE4_INTEGRATION08 import (
    start_session,
    get_session,
    end_session,
    clear_session,
    send_turn,
    SESSION_READY,
    SESSION_CLARIFICATION,
    SESSION_REVIEW,
    SESSION_BLOCKED,
    SESSION_UNKNOWN,
)


LIVE_API_READY = "LIVE_API_READY"
LIVE_API_CLARIFICATION = "LIVE_API_CLARIFICATION"
LIVE_API_REVIEW = "LIVE_API_REVIEW"
LIVE_API_BLOCKED = "LIVE_API_BLOCKED"
LIVE_API_UNKNOWN = "LIVE_API_UNKNOWN"


@dataclass
class LiveConversationResult:
    status: str
    session_id: str
    lead_id: Optional[str] = None
    response_text: str = ""
    turn_count: int = 0
    errors: List[str] = None
    response_allowed: bool = False

    executor_invoked: bool = False
    execution_occurred: bool = False
    crm_write_occurred: bool = False
    message_sent: bool = False
    external_action_occurred: bool = False
    occurrence_claimed: bool = False

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def snapshot(self) -> Dict[str, Any]:
        return deepcopy({
            "status": self.status,
            "session_id": self.session_id,
            "lead_id": self.lead_id,
            "response_text": self.response_text,
            "turn_count": self.turn_count,
            "errors": list(self.errors),
            "response_allowed": self.response_allowed,
            "executor_invoked": self.executor_invoked,
            "execution_occurred": self.execution_occurred,
            "crm_write_occurred": self.crm_write_occurred,
            "message_sent": self.message_sent,
            "external_action_occurred": self.external_action_occurred,
            "occurrence_claimed": self.occurrence_claimed,
        })


def _map_status(gateway_status: str) -> str:
    return {
        SESSION_READY: LIVE_API_READY,
        SESSION_CLARIFICATION: LIVE_API_CLARIFICATION,
        SESSION_REVIEW: LIVE_API_REVIEW,
        SESSION_BLOCKED: LIVE_API_BLOCKED,
        SESSION_UNKNOWN: LIVE_API_UNKNOWN,
    }.get(gateway_status, LIVE_API_UNKNOWN)


def validate_live_conversation_result(result: LiveConversationResult) -> List[str]:
    errors = []
    if not isinstance(result, LiveConversationResult):
        return ["result must be LiveConversationResult"]
    if not result.session_id:
        errors.append("session_id is required")
    if result.response_allowed and not result.response_text:
        errors.append("response_allowed requires response_text")
    if result.status == LIVE_API_READY and not result.response_allowed:
        errors.append("ready result must allow response")
    if result.status != LIVE_API_READY and result.response_allowed:
        errors.append("non-ready result cannot allow response")

    if result.executor_invoked:
        errors.append("executor invocation is prohibited")
    if result.execution_occurred:
        errors.append("execution is prohibited")
    if result.crm_write_occurred:
        errors.append("CRM writes are prohibited")
    if result.message_sent:
        errors.append("message sending is prohibited")
    if result.external_action_occurred:
        errors.append("external actions are prohibited")
    if result.occurrence_claimed:
        errors.append("occurrence claims are prohibited")
    return errors


def start_live_conversation(
    session_id: str,
    lead_id: Optional[str] = None,
) -> LiveConversationResult:
    try:
        state = start_session(session_id, lead_id)
        return LiveConversationResult(
            status=LIVE_API_READY,
            session_id=state.session_id,
            lead_id=state.lead_id,
            response_allowed=True,
        )
    except Exception as exc:
        return LiveConversationResult(
            status=LIVE_API_BLOCKED,
            session_id=str(session_id or "").strip(),
            lead_id=lead_id,
            errors=[f"session_start_error: {exc}"],
        )


def ask_live(
    message: str,
    session_id: str,
    lead_id: Optional[str] = None,
) -> LiveConversationResult:
    sid = str(session_id or "").strip()
    if not sid:
        return LiveConversationResult(
            status=LIVE_API_BLOCKED,
            session_id="",
            lead_id=lead_id,
            errors=["session_id is required"],
        )

    if not str(message or "").strip():
        return LiveConversationResult(
            status=LIVE_API_CLARIFICATION,
            session_id=sid,
            lead_id=lead_id,
            errors=["message is required"],
        )

    result, errors = send_turn(message, sid, lead_id)
    state = get_session(sid)

    if result is None:
        return LiveConversationResult(
            status=LIVE_API_BLOCKED,
            session_id=sid,
            lead_id=state.lead_id if state else lead_id,
            turn_count=state.turn_count if state else 0,
            errors=list(errors or ["live turn failed"]),
        )

    status = _map_status(getattr(result, "status", ""))
    response_text = str(getattr(result, "response_text", "") or "")
    response_allowed = status == LIVE_API_READY and bool(response_text)

    return LiveConversationResult(
        status=status,
        session_id=sid,
        lead_id=state.lead_id if state else lead_id,
        response_text=response_text if response_allowed else "",
        turn_count=state.turn_count if state else 0,
        errors=list(errors or []),
        response_allowed=response_allowed,
    )


def continue_live_conversation(
    message: str,
    session_id: str,
) -> LiveConversationResult:
    state = get_session(session_id)
    if state is None:
        return LiveConversationResult(
            status=LIVE_API_UNKNOWN,
            session_id=str(session_id or "").strip(),
            errors=["session does not exist"],
        )
    if not state.active:
        return LiveConversationResult(
            status=LIVE_API_BLOCKED,
            session_id=state.session_id,
            lead_id=state.lead_id,
            turn_count=state.turn_count,
            errors=["session is not active"],
        )
    return ask_live(message, state.session_id, state.lead_id)


def end_live_conversation(session_id: str) -> Dict[str, Any]:
    state = get_session(session_id)
    if state is None:
        return {"session_id": str(session_id or "").strip(), "ended": False}
    end_session(state.session_id)
    return session_snapshot(state.session_id)


def session_snapshot(session_id: str) -> Dict[str, Any]:
    state = get_session(session_id)
    return state.snapshot() if state else {}


def clear_live_conversation(session_id: str) -> None:
    clear_session(session_id)


__all__ = [
    "LiveConversationResult",
    "LIVE_API_READY",
    "LIVE_API_CLARIFICATION",
    "LIVE_API_REVIEW",
    "LIVE_API_BLOCKED",
    "LIVE_API_UNKNOWN",
    "validate_live_conversation_result",
    "start_live_conversation",
    "ask_live",
    "continue_live_conversation",
    "end_live_conversation",
    "session_snapshot",
    "clear_live_conversation",
]
