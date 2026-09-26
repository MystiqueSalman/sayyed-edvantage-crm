"""Sayyed EdVantage Phase 4 Integration 08 — Live Session Manager.

Adds a production-oriented session manager around the Phase 4 Integration 07
gateway. One session remains bound to one lead; follow-up turns reuse the
same session_id; conflicting lead identities fail closed.

This layer is orchestration-only: no CRM writes, no message sending, and no
external execution.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from copy import deepcopy

from Sayyed_EdVantage_PHASE4_INTEGRATION07 import (
    ask_live_agent,
    gateway_snapshot,
    reset_live_session,
    validate_gateway_result,
    GATEWAY_READY,
    GATEWAY_REVIEW,
    GATEWAY_BLOCKED,
    GATEWAY_CLARIFICATION,
    GATEWAY_UNKNOWN,
    RESPOND,
)

SESSION_READY = "SESSION_READY"
SESSION_CLARIFICATION = "SESSION_CLARIFICATION"
SESSION_REVIEW = "SESSION_REVIEW"
SESSION_BLOCKED = "SESSION_BLOCKED"
SESSION_UNKNOWN = "SESSION_UNKNOWN"


@dataclass
class ManagedLiveSession:
    session_id: str
    lead_id: Optional[str] = None
    turn_count: int = 0
    last_response: str = ""
    last_status: str = ""
    active: bool = True

    def snapshot(self) -> Dict[str, Any]:
        return deepcopy({
            "session_id": self.session_id,
            "lead_id": self.lead_id,
            "turn_count": self.turn_count,
            "last_response": self.last_response,
            "last_status": self.last_status,
            "active": self.active,
        })


_SESSIONS: Dict[str, ManagedLiveSession] = {}


def start_session(session_id: str, lead_id: Optional[str] = None) -> ManagedLiveSession:
    sid = str(session_id or "").strip()
    lid = str(lead_id).strip() if lead_id else None

    if not sid:
        raise ValueError("session_id is required.")

    existing = _SESSIONS.get(sid)
    if existing:
        if lid and existing.lead_id and lid != existing.lead_id:
            raise ValueError("Session is already bound to a different lead_id.")
        if lid and not existing.lead_id:
            existing.lead_id = lid
        existing.active = True
        return deepcopy(existing)

    state = ManagedLiveSession(session_id=sid, lead_id=lid)
    _SESSIONS[sid] = state
    return deepcopy(state)


def get_session(session_id: str) -> Optional[ManagedLiveSession]:
    state = _SESSIONS.get(str(session_id or "").strip())
    return deepcopy(state) if state else None


def end_session(session_id: str) -> None:
    state = _SESSIONS.get(str(session_id or "").strip())
    if state:
        state.active = False


def clear_session(session_id: str) -> None:
    sid = str(session_id or "").strip()
    _SESSIONS.pop(sid, None)
    reset_live_session(sid)


def send_turn(message: str, session_id: str, lead_id: Optional[str] = None):
    sid = str(session_id or "").strip()
    lid = str(lead_id).strip() if lead_id else None

    try:
        state = _SESSIONS.get(sid)
        if state is None:
            state = start_session(sid, lid)
        elif not state.active:
            return None, ["session is not active"]
        elif lid and state.lead_id and lid != state.lead_id:
            return None, ["session lead_id conflict"]
        elif lid and not state.lead_id:
            state.lead_id = lid

        result = ask_live_agent(message, sid, state.lead_id)
        state.turn_count += 1
        state.last_response = result.response_text
        state.last_status = result.status
        return result, validate_gateway_result(result)

    except Exception as exc:
        return None, [f"session_error: {exc}"]


def session_snapshot(session_id: str) -> Dict[str, Any]:
    state = get_session(session_id)
    return state.snapshot() if state else {}


__all__ = [
    "ManagedLiveSession", "start_session", "get_session", "end_session",
    "clear_session", "send_turn", "session_snapshot",
    "SESSION_READY", "SESSION_CLARIFICATION", "SESSION_REVIEW",
    "SESSION_BLOCKED", "SESSION_UNKNOWN",
]
