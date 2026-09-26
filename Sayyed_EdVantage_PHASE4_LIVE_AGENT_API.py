
"""
Sayyed EdVantage AI Agent
PHASE 4 — LIVE AGENT API BOUNDARY
Live Agent Interface / API Boundary Contract

Application-facing boundary for the completed Phase 4 pipeline.
This layer accepts a prepared LiveAgentTurn (object or dict) and exposes a
strict JSON-safe interface result.

IMPORTANT:
- No message is sent.
- No CRM data is written.
- No external action occurs.
- No executor is invoked.
- This is the final boundary before real live-agent testing.
"""

from dataclasses import dataclass, field, asdict
from copy import deepcopy
from typing import Any, Dict, List, Optional

API_READY = "API_READY"
API_CLARIFICATION = "API_CLARIFICATION"
API_REVIEW = "API_REVIEW"
API_BLOCKED = "API_BLOCKED"
API_UNKNOWN = "API_UNKNOWN"

API_RESPOND = "RESPOND"
API_CLARIFY = "CLARIFY"
API_HUMAN_REVIEW = "HUMAN_REVIEW"
API_BLOCK = "BLOCK"
API_OBTAIN_STATE = "OBTAIN_STATE"

@dataclass
class LiveAgentAPIResult:
    status: str
    mode: str
    session_id: Optional[str] = None
    lead_id: Optional[str] = None
    course_ids: List[str] = field(default_factory=list)
    intent: Optional[str] = None
    response_text: str = ""
    response_ready: bool = False
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    human_handoff: bool = False

    # Permanent side-effect boundary.
    message_send_authorized: bool = False
    message_sent: bool = False
    crm_write_authorized: bool = False
    crm_write_occurred: bool = False
    external_action_authorized: bool = False
    external_action_occurred: bool = False
    executor_invoked: bool = False

def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _copy_list(value):
    return deepcopy(value) if isinstance(value, list) else []

def _map_status(status: Any, mode: Any):
    if status == "LIVE_TURN_READY" and mode == "RESPOND":
        return API_READY, API_RESPOND, True
    if status == "LIVE_TURN_CLARIFICATION" and mode == "CLARIFY":
        return API_CLARIFICATION, API_CLARIFY, False
    if status == "LIVE_TURN_REVIEW" and mode == "HUMAN_REVIEW":
        return API_REVIEW, API_HUMAN_REVIEW, False
    if status == "LIVE_TURN_BLOCKED" and mode == "BLOCK":
        return API_BLOCKED, API_BLOCK, False
    if status == "LIVE_TURN_UNKNOWN" and mode == "OBTAIN_STATE":
        return API_UNKNOWN, API_OBTAIN_STATE, False
    return API_BLOCKED, API_BLOCK, False

def build_live_agent_api_result(live_turn: Any) -> LiveAgentAPIResult:
    status = _get(live_turn, "status")
    mode = _get(live_turn, "mode")
    mapped_status, mapped_mode, ready = _map_status(status, mode)

    upstream_errors = _copy_list(_get(live_turn, "errors", []))

    # A malformed or unsafe upstream turn is fail-closed.
    if not status or not mode:
        upstream_errors.append("missing live-turn status or mode")

    if bool(_get(live_turn, "message_send_authorized", False)):
        upstream_errors.append("upstream message-send authorization is unsafe")
    if bool(_get(live_turn, "message_sent", False)):
        upstream_errors.append("upstream message-sent state is unsafe")
    if bool(_get(live_turn, "crm_write_authorized", False)):
        upstream_errors.append("upstream CRM-write authorization is unsafe")
    if bool(_get(live_turn, "crm_write_occurred", False)):
        upstream_errors.append("upstream CRM-write occurrence is unsafe")
    if bool(_get(live_turn, "external_action_authorized", False)):
        upstream_errors.append("upstream external-action authorization is unsafe")
    if bool(_get(live_turn, "external_action_occurred", False)):
        upstream_errors.append("upstream external-action occurrence is unsafe")
    if bool(_get(live_turn, "executor_invoked", False)):
        upstream_errors.append("upstream executor invocation is unsafe")

    if upstream_errors:
        mapped_status, mapped_mode, ready = API_BLOCKED, API_BLOCK, False

    return LiveAgentAPIResult(
        status=mapped_status,
        mode=mapped_mode,
        session_id=_get(live_turn, "session_id"),
        lead_id=_get(live_turn, "lead_id"),
        course_ids=_copy_list(_get(live_turn, "course_ids", [])),
        intent=_get(live_turn, "intent"),
        response_text=(
            _get(live_turn, "response_text", "") or ""
        ) if ready else (
            _get(live_turn, "response_text", "") or ""
        ) if mapped_status == API_CLARIFICATION else "",
        response_ready=ready,
        evidence=_copy_list(_get(live_turn, "evidence", [])),
        provenance=_copy_list(_get(live_turn, "provenance", [])),
        prohibited_claims=_copy_list(_get(live_turn, "prohibited_claims", [])),
        conflicts=_copy_list(_get(live_turn, "conflicts", [])),
        errors=upstream_errors,
        human_handoff=bool(_get(live_turn, "human_handoff", False)) or mapped_status == API_REVIEW,
    )

def run_live_agent_api(live_turn: Any) -> LiveAgentAPIResult:
    return build_live_agent_api_result(live_turn)

def validate_live_agent_api_result(result: LiveAgentAPIResult) -> List[str]:
    if not isinstance(result, LiveAgentAPIResult):
        return ["invalid API result type"]

    errors = []
    statuses = {
        API_READY, API_CLARIFICATION, API_REVIEW, API_BLOCKED, API_UNKNOWN
    }
    modes = {
        API_RESPOND, API_CLARIFY, API_HUMAN_REVIEW, API_BLOCK, API_OBTAIN_STATE
    }
    if result.status not in statuses:
        errors.append("invalid API status")
    if result.mode not in modes:
        errors.append("invalid API mode")

    expected = {
        API_READY: (API_RESPOND, True),
        API_CLARIFICATION: (API_CLARIFY, False),
        API_REVIEW: (API_HUMAN_REVIEW, False),
        API_BLOCKED: (API_BLOCK, False),
        API_UNKNOWN: (API_OBTAIN_STATE, False),
    }
    if result.status in expected:
        emode, eready = expected[result.status]
        if result.mode != emode:
            errors.append("API status/mode mismatch")
        if result.response_ready != eready:
            errors.append("API response-ready mismatch")

    if result.status == API_READY and not result.response_text:
        errors.append("API-ready result requires response text")
    if result.status != API_READY and result.response_ready:
        errors.append("non-ready API result cannot be response-ready")
    if result.status == API_REVIEW and not result.human_handoff:
        errors.append("review API result requires human handoff")

    # Hard invariants: this boundary never executes.
    if result.message_send_authorized:
        errors.append("message sending must remain unauthorized")
    if result.message_sent:
        errors.append("message must not be marked sent")
    if result.crm_write_authorized:
        errors.append("CRM writing must remain unauthorized")
    if result.crm_write_occurred:
        errors.append("CRM write must not be marked occurred")
    if result.external_action_authorized:
        errors.append("external actions must remain unauthorized")
    if result.external_action_occurred:
        errors.append("external action must not be marked occurred")
    if result.executor_invoked:
        errors.append("executor must not be invoked")

    return errors

def live_agent_api_result_to_dict(result: LiveAgentAPIResult) -> Dict[str, Any]:
    return deepcopy(asdict(result))

def validate_serialized_live_agent_api_result(data: Dict[str, Any]) -> List[str]:
    if not isinstance(data, dict):
        return ["serialized API result must be a dict"]
    try:
        result = LiveAgentAPIResult(**deepcopy(data))
    except Exception as exc:
        return [f"invalid serialized API result: {exc}"]
    return validate_live_agent_api_result(result)
