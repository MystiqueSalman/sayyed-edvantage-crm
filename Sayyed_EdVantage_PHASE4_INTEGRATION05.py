
"""
Sayyed EdVantage AI Agent
PHASE 4 INTEGRATION 05
Unified Live-Turn Interface Contract

This is the final application-facing facade before live testing.
It prepares one deterministic agent-turn result from a delivery envelope.
It does NOT send messages, write CRM data, invoke executors, or perform
external actions.
"""

from dataclasses import dataclass, field, asdict
from copy import deepcopy
from typing import Any, Dict, List, Optional

try:
    from Sayyed_EdVantage_PHASE4_INTEGRATION04 import (
        DeliveryEnvelope,
        build_delivery_envelope,
        validate_delivery_envelope,
        DELIVERY_READY,
        DELIVERY_CLARIFICATION,
        DELIVERY_REVIEW,
        DELIVERY_BLOCKED,
        DELIVERY_UNKNOWN,
        DELIVER_RESPONSE,
        CLARIFY_BEFORE_DELIVERY,
        HUMAN_REVIEW_BEFORE_DELIVERY,
        BLOCK_DELIVERY,
        OBTAIN_VERIFIED_STATE,
    )
except ImportError:
    from phase4_integration04.Sayyed_EdVantage_PHASE4_INTEGRATION04 import (
        DeliveryEnvelope,
        build_delivery_envelope,
        validate_delivery_envelope,
        DELIVERY_READY,
        DELIVERY_CLARIFICATION,
        DELIVERY_REVIEW,
        DELIVERY_BLOCKED,
        DELIVERY_UNKNOWN,
        DELIVER_RESPONSE,
        CLARIFY_BEFORE_DELIVERY,
        HUMAN_REVIEW_BEFORE_DELIVERY,
        BLOCK_DELIVERY,
        OBTAIN_VERIFIED_STATE,
    )

LIVE_TURN_READY = "LIVE_TURN_READY"
LIVE_TURN_CLARIFICATION = "LIVE_TURN_CLARIFICATION"
LIVE_TURN_REVIEW = "LIVE_TURN_REVIEW"
LIVE_TURN_BLOCKED = "LIVE_TURN_BLOCKED"
LIVE_TURN_UNKNOWN = "LIVE_TURN_UNKNOWN"

LIVE_RESPOND = "RESPOND"
LIVE_CLARIFY = "CLARIFY"
LIVE_HUMAN_REVIEW = "HUMAN_REVIEW"
LIVE_BLOCK = "BLOCK"
LIVE_OBTAIN_STATE = "OBTAIN_STATE"

@dataclass
class LiveAgentTurn:
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

    # Absolute safety boundary for the live interface.
    message_send_authorized: bool = False
    message_sent: bool = False
    crm_write_authorized: bool = False
    crm_write_occurred: bool = False
    external_action_authorized: bool = False
    external_action_occurred: bool = False
    executor_invoked: bool = False

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _copy_list(v):
    return deepcopy(v) if isinstance(v, list) else []

def _map(envelope: DeliveryEnvelope) -> tuple[str, str, bool]:
    if envelope.status == DELIVERY_READY:
        return LIVE_TURN_READY, LIVE_RESPOND, True
    if envelope.status == DELIVERY_CLARIFICATION:
        return LIVE_TURN_CLARIFICATION, LIVE_CLARIFY, False
    if envelope.status == DELIVERY_REVIEW:
        return LIVE_TURN_REVIEW, LIVE_HUMAN_REVIEW, False
    if envelope.status == DELIVERY_BLOCKED:
        return LIVE_TURN_BLOCKED, LIVE_BLOCK, False
    return LIVE_TURN_UNKNOWN, LIVE_OBTAIN_STATE, False

def build_live_agent_turn(envelope: DeliveryEnvelope) -> LiveAgentTurn:
    envelope_errors = validate_delivery_envelope(envelope)
    if envelope_errors:
        return LiveAgentTurn(
            status=LIVE_TURN_BLOCKED,
            mode=LIVE_BLOCK,
            session_id=_get(envelope, "session_id"),
            lead_id=_get(envelope, "lead_id"),
            course_ids=_copy_list(_get(envelope, "course_ids", [])),
            intent=_get(envelope, "intent"),
            errors=list(envelope_errors),
        )

    status, mode, ready = _map(envelope)
    return LiveAgentTurn(
        status=status,
        mode=mode,
        session_id=envelope.session_id,
        lead_id=envelope.lead_id,
        course_ids=_copy_list(envelope.course_ids),
        intent=envelope.intent,
        response_text=envelope.response_text if ready else (
            envelope.response_text if status == LIVE_TURN_CLARIFICATION else ""
        ),
        response_ready=ready,
        evidence=_copy_list(envelope.evidence),
        provenance=_copy_list(envelope.provenance),
        prohibited_claims=_copy_list(envelope.prohibited_claims),
        conflicts=_copy_list(envelope.conflicts),
        errors=_copy_list(envelope.errors),
        human_handoff=envelope.human_handoff,
    )

def run_live_agent_turn(response_orchestration: Any) -> LiveAgentTurn:
    envelope = build_delivery_envelope(response_orchestration)
    return build_live_agent_turn(envelope)

def validate_live_agent_turn(turn: LiveAgentTurn) -> List[str]:
    errors = []
    valid_statuses = {
        LIVE_TURN_READY, LIVE_TURN_CLARIFICATION, LIVE_TURN_REVIEW,
        LIVE_TURN_BLOCKED, LIVE_TURN_UNKNOWN
    }
    valid_modes = {
        LIVE_RESPOND, LIVE_CLARIFY, LIVE_HUMAN_REVIEW,
        LIVE_BLOCK, LIVE_OBTAIN_STATE
    }

    if not isinstance(turn, LiveAgentTurn):
        return ["invalid live turn type"]
    if turn.status not in valid_statuses:
        errors.append("invalid status")
    if turn.mode not in valid_modes:
        errors.append("invalid mode")

    expected = {
        LIVE_TURN_READY: (LIVE_RESPOND, True),
        LIVE_TURN_CLARIFICATION: (LIVE_CLARIFY, False),
        LIVE_TURN_REVIEW: (LIVE_HUMAN_REVIEW, False),
        LIVE_TURN_BLOCKED: (LIVE_BLOCK, False),
        LIVE_TURN_UNKNOWN: (LIVE_OBTAIN_STATE, False),
    }
    if turn.status in expected:
        emode, eready = expected[turn.status]
        if turn.mode != emode:
            errors.append("status/mode mismatch")
        if turn.response_ready != eready:
            errors.append("response-ready mismatch")

    if turn.status == LIVE_TURN_READY and not turn.response_text:
        errors.append("ready live turn requires response text")
    if turn.status != LIVE_TURN_READY and turn.response_ready:
        errors.append("non-ready live turn cannot be response-ready")
    if turn.status == LIVE_TURN_REVIEW and not turn.human_handoff:
        errors.append("review turn requires human handoff")

    # Live interface never authorizes or reports side effects.
    if turn.message_send_authorized:
        errors.append("message sending must remain unauthorized")
    if turn.message_sent:
        errors.append("message must not be marked sent")
    if turn.crm_write_authorized:
        errors.append("CRM writing must remain unauthorized")
    if turn.crm_write_occurred:
        errors.append("CRM write must not be marked occurred")
    if turn.external_action_authorized:
        errors.append("external actions must remain unauthorized")
    if turn.external_action_occurred:
        errors.append("external action must not be marked occurred")
    if turn.executor_invoked:
        errors.append("executor must not be invoked")

    return errors

def live_agent_turn_to_dict(turn: LiveAgentTurn) -> Dict[str, Any]:
    return deepcopy(asdict(turn))

def validate_serialized_live_agent_turn(data: Dict[str, Any]) -> List[str]:
    if not isinstance(data, dict):
        return ["serialized live turn must be a dict"]
    try:
        turn = LiveAgentTurn(**deepcopy(data))
    except Exception as exc:
        return [f"invalid serialized live turn: {exc}"]
    return validate_live_agent_turn(turn)
