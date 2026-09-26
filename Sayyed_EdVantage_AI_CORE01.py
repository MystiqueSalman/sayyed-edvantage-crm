"""
Sayyed EdVantage AI Agent — AI Core 01
Agent Runtime, State & Orchestration Contract
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy
import uuid

from Sayyed_EdVantage_Master_KB_BATCH28 import (
    agent_response_query,
    validate_agent_response_contract,
    build_master_kb_with_agent_integration,
)

RUNTIME_READY = "RUNTIME_READY"
RUNTIME_HANDOFF = "RUNTIME_HANDOFF"
RUNTIME_BLOCKED = "RUNTIME_BLOCKED"

SAFE_FLAGS = {
    "execution_enabled": False,
    "messaging_enabled": False,
    "external_actions_enabled": False,
    "crm_writes_enabled": False,
    "no_invention": True,
}

@dataclass
class AgentTurn:
    turn_id: str
    user_message: str
    response: str = ""
    integration_status: str = ""
    intent: str = ""
    course_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    human_handoff_required: bool = False

@dataclass
class AgentSessionState:
    session_id: str
    turn_count: int = 0
    turns: List[AgentTurn] = field(default_factory=list)
    active_course_ids: List[str] = field(default_factory=list)
    active_intent: str = ""
    handoff_required: bool = False
    runtime_status: str = RUNTIME_READY
    safety: Dict[str, Any] = field(default_factory=lambda: copy.deepcopy(SAFE_FLAGS))

@dataclass
class AgentRuntimeResult:
    session_id: str
    turn_id: str
    user_message: str
    response: str
    runtime_status: str
    integration_status: str
    intent: str
    course_ids: List[str]
    source_ids: List[str]
    human_handoff_required: bool
    safety: Dict[str, Any]
    errors: List[str] = field(default_factory=list)

def _unique(values):
    return list(dict.fromkeys(values))

def create_session(session_id: Optional[str] = None):
    return AgentSessionState(session_id=session_id or f"SESS-{uuid.uuid4().hex[:12].upper()}")

def validate_session_state(state):
    errors = []
    if not state.session_id.strip():
        errors.append("Session ID cannot be empty.")
    if state.turn_count != len(state.turns):
        errors.append("turn_count must equal the number of stored turns.")
    if state.turn_count < 0:
        errors.append("turn_count cannot be negative.")
    if state.runtime_status not in {RUNTIME_READY, RUNTIME_HANDOFF, RUNTIME_BLOCKED}:
        errors.append("Invalid runtime status.")
    for key, value in SAFE_FLAGS.items():
        if state.safety.get(key) is not value:
            errors.append(f"Session safety invariant failed: {key}.")
    return {"valid": not errors, "errors": _unique(errors)}

def run_agent_turn(kb, state, user_message, top_k=10, course_id=None, category=None):
    message = str(user_message).strip()
    turn_id = f"TURN-{uuid.uuid4().hex[:12].upper()}"

    if not message:
        result = AgentRuntimeResult(
            state.session_id, turn_id, "", "", RUNTIME_BLOCKED, "", "",
            [], [], True, copy.deepcopy(SAFE_FLAGS), ["User message cannot be empty."]
        )
        state.runtime_status = RUNTIME_BLOCKED
        state.handoff_required = True
        return result

    validation = validate_session_state(state)
    if not validation["valid"]:
        return AgentRuntimeResult(
            state.session_id, turn_id, message, "", RUNTIME_BLOCKED, "",
            state.active_intent, list(state.active_course_ids), [], True,
            copy.deepcopy(SAFE_FLAGS), list(validation["errors"])
        )

    answer = agent_response_query(
        kb, message, top_k=top_k, course_id=course_id, category=category
    )
    errors = list(validate_agent_response_contract(answer)["errors"])

    if errors:
        runtime_status = RUNTIME_BLOCKED
        response = ""
        handoff = True
    elif answer.integration_status == "INTEGRATION_HANDOFF":
        runtime_status = RUNTIME_HANDOFF
        response = ""
        handoff = True
        # Preserve the upstream handoff diagnostics so the Agent runtime
        # does not lose the reason normal delivery was blocked.
        errors.extend(answer.gate_errors)
    else:
        runtime_status = RUNTIME_READY
        response = answer.response
        handoff = answer.human_handoff_required

    turn = AgentTurn(
        turn_id=turn_id, user_message=message, response=response,
        integration_status=answer.integration_status, intent=answer.intent,
        course_ids=list(answer.course_ids), source_ids=list(answer.source_ids),
        human_handoff_required=handoff
    )
    state.turns.append(turn)
    state.turn_count += 1
    state.active_course_ids = _unique(state.active_course_ids + list(answer.course_ids))
    state.active_intent = answer.intent
    state.handoff_required = state.handoff_required or handoff
    state.runtime_status = runtime_status
    state.safety = copy.deepcopy(SAFE_FLAGS)

    return AgentRuntimeResult(
        state.session_id, turn_id, message, response, runtime_status,
        answer.integration_status, answer.intent, list(answer.course_ids),
        list(answer.source_ids), handoff, copy.deepcopy(SAFE_FLAGS), _unique(errors)
    )

def agent_runtime_query(kb, query, session_id=None, top_k=10):
    state = create_session(session_id)
    return run_agent_turn(kb, state, query, top_k=top_k)

def session_to_dict(state):
    return {
        "session_id": state.session_id, "turn_count": state.turn_count,
        "turns": [vars(t).copy() for t in state.turns],
        "active_course_ids": list(state.active_course_ids),
        "active_intent": state.active_intent,
        "handoff_required": state.handoff_required,
        "runtime_status": state.runtime_status,
        "safety": copy.deepcopy(state.safety),
    }

def runtime_result_to_dict(result):
    return {
        "session_id": result.session_id, "turn_id": result.turn_id,
        "user_message": result.user_message, "response": result.response,
        "runtime_status": result.runtime_status,
        "integration_status": result.integration_status,
        "intent": result.intent, "course_ids": list(result.course_ids),
        "source_ids": list(result.source_ids),
        "human_handoff_required": result.human_handoff_required,
        "safety": copy.deepcopy(result.safety), "errors": list(result.errors),
    }

def validate_runtime_result(result):
    errors = []
    if result.runtime_status not in {RUNTIME_READY, RUNTIME_HANDOFF, RUNTIME_BLOCKED}:
        errors.append("Invalid runtime result status.")
    if result.runtime_status == RUNTIME_READY:
        if not result.response.strip(): errors.append("RUNTIME_READY requires response text.")
        if not result.source_ids: errors.append("RUNTIME_READY requires provenance.")
    else:
        if result.response.strip(): errors.append("Handoff/blocked runtime must not expose response text.")
        if not result.human_handoff_required: errors.append("Handoff/blocked runtime must require handoff.")
    for key, value in SAFE_FLAGS.items():
        if result.safety.get(key) is not value:
            errors.append(f"Runtime safety invariant failed: {key}.")
    return {"valid": not errors, "errors": _unique(errors)}

def build_agent_runtime():
    return build_master_kb_with_agent_integration()
