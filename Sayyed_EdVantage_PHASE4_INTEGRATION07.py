"""Sayyed EdVantage Phase 4 Integration 07 — Live Agent Gateway."""
from dataclasses import dataclass
from copy import deepcopy
from typing import Optional, Dict, Any

from Sayyed_EdVantage_PHASE4_INTEGRATION06 import (
    run_live_turn, get_live_session, reset_live_session,
    LIVE_READY, LIVE_CLARIFICATION, LIVE_REVIEW, LIVE_BLOCKED, LIVE_UNKNOWN,
    RESPOND, CLARIFY, HUMAN_REVIEW, NO_RESPONSE,
)

GATEWAY_READY = "LIVE_GATEWAY_READY"
GATEWAY_CLARIFICATION = "LIVE_GATEWAY_CLARIFICATION"
GATEWAY_REVIEW = "LIVE_GATEWAY_REVIEW"
GATEWAY_BLOCKED = "LIVE_GATEWAY_BLOCKED"
GATEWAY_UNKNOWN = "LIVE_GATEWAY_UNKNOWN"

@dataclass
class LiveAgentGatewayResult:
    status: str
    mode: str
    session_id: str
    lead_id: Optional[str]
    response_text: str
    turn_count: int
    crm_profile: Optional[Dict[str, Any]]
    errors: list[str]
    executor_invoked: bool = False
    execution_authorized: bool = False
    crm_write: bool = False
    message_sent: bool = False
    external_action: bool = False

def _map_status(status):
    return {
        LIVE_READY: (GATEWAY_READY, RESPOND),
        LIVE_CLARIFICATION: (GATEWAY_CLARIFICATION, CLARIFY),
        LIVE_REVIEW: (GATEWAY_REVIEW, HUMAN_REVIEW),
        LIVE_BLOCKED: (GATEWAY_BLOCKED, NO_RESPONSE),
        LIVE_UNKNOWN: (GATEWAY_UNKNOWN, NO_RESPONSE),
    }.get(status, (GATEWAY_UNKNOWN, NO_RESPONSE))

def ask_live_agent(message: str, session_id: str, lead_id: Optional[str] = None):
    result = run_live_turn(message, session_id, lead_id)
    status, mode = _map_status(result.status)
    return LiveAgentGatewayResult(
        status, mode, result.session_id, result.lead_id,
        result.response_text, result.turn_count,
        deepcopy(result.crm_profile), list(result.errors)
    )

def live_agent_query(message: str, session_id: str, lead_id: Optional[str] = None) -> str:
    result = ask_live_agent(message, session_id, lead_id)
    return result.response_text if result.status == GATEWAY_READY else ""

def gateway_snapshot(session_id: str):
    state = get_live_session(session_id)
    return state.snapshot() if state else None

def validate_gateway_result(result):
    errors = []
    if result.status == GATEWAY_READY:
        if result.mode != RESPOND: errors.append("READY must use RESPOND.")
        if not result.response_text: errors.append("READY must contain response_text.")
    elif result.response_text:
        errors.append("Non-ready result must not contain response_text.")
    for field in ("executor_invoked","execution_authorized","crm_write","message_sent","external_action"):
        if getattr(result, field): errors.append(f"{field} must remain False.")
    return errors

__all__ = [
    "LiveAgentGatewayResult", "ask_live_agent", "live_agent_query",
    "gateway_snapshot", "reset_live_session", "validate_gateway_result",
    "GATEWAY_READY", "GATEWAY_CLARIFICATION", "GATEWAY_REVIEW",
    "GATEWAY_BLOCKED", "GATEWAY_UNKNOWN",
]
