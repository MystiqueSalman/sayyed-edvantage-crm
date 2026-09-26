"""
Sayyed EdVantage AI Agent — Master KB Batch 28
Master KB → AI Agent Read-Only Integration Adapter

Purpose:
- Provide a narrow, deterministic adapter from the Master KB delivery contract
  into the downstream AI Agent.
- Expose only safe, validated delivery envelopes.
- Preserve answer text, provenance, completeness, warnings, and handoff state.
- Keep the integration explicitly read-only.
- Refuse to expose normal answer content from HANDOFF_ONLY states.
- Never execute actions, send messages, call external systems, or write CRM data.

This batch does NOT connect to the live CRM, messaging systems, external APIs,
or autonomous execution. It defines the integration boundary only.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH27 import (
    DELIVERABLE,
    HANDOFF_ONLY,
    DeliveryEnvelope,
    deliver_query,
    validate_delivery_envelope,
    build_master_kb_with_delivery_contract,
)


INTEGRATION_READY = "INTEGRATION_READY"
INTEGRATION_HANDOFF = "INTEGRATION_HANDOFF"


@dataclass
class AgentResponseContract:
    query: str
    response: str
    integration_status: str
    delivery_status: str
    response_status: str
    completeness_status: str
    intent: str
    course_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    supported_points: List[str] = field(default_factory=list)
    missing_points: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    grounded: bool = False
    human_handoff_required: bool = False
    safety: Dict[str, Any] = field(default_factory=dict)
    gate_errors: List[str] = field(default_factory=list)


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def _safe_safety(safety: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(safety)
    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        result[key] = False
    result["no_invention"] = True
    return result


def _integration_gate(envelope: DeliveryEnvelope) -> List[str]:
    errors = []

    validation = validate_delivery_envelope(envelope)
    errors.extend(validation["errors"])

    # The adapter is read-only regardless of upstream state.
    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if envelope.safety.get(key) is not False:
            errors.append(f"{key} must be False at integration boundary.")

    if envelope.safety.get("no_invention") is not True:
        errors.append("no_invention must be True at integration boundary.")

    if envelope.delivery_status == DELIVERABLE:
        if not envelope.answer.strip():
            errors.append("DELIVERABLE integration response cannot be empty.")
        if not envelope.grounded:
            errors.append("DELIVERABLE integration response must be grounded.")
        if not envelope.source_ids:
            errors.append("DELIVERABLE integration response requires provenance.")

    if envelope.delivery_status == HANDOFF_ONLY:
        if envelope.answer.strip():
            errors.append("HANDOFF_ONLY integration must not expose response text.")
        if not envelope.human_handoff_required:
            errors.append("HANDOFF_ONLY integration must require human handoff.")

    return _unique(errors)


def adapt_delivery_to_agent(
    envelope: DeliveryEnvelope,
) -> AgentResponseContract:
    """
    Convert the Batch-27 delivery envelope into a read-only AI Agent contract.

    A normal DELIVERABLE is exposed as response text.
    A HANDOFF_ONLY state is exposed without answer text.
    """
    errors = _integration_gate(envelope)

    if errors or envelope.delivery_status == HANDOFF_ONLY:
        combined = _unique(list(envelope.gate_errors) + errors)
        return AgentResponseContract(
            query=envelope.query,
            response="",
            integration_status=INTEGRATION_HANDOFF,
            delivery_status=envelope.delivery_status,
            response_status=envelope.response_status,
            completeness_status=envelope.completeness_status,
            intent=envelope.intent,
            course_ids=list(envelope.course_ids),
            source_ids=list(envelope.source_ids),
            supported_points=list(envelope.supported_points),
            missing_points=list(envelope.missing_points),
            warnings=list(envelope.warnings),
            grounded=False,
            human_handoff_required=True,
            safety=_safe_safety(envelope.safety),
            gate_errors=combined,
        )

    return AgentResponseContract(
        query=envelope.query,
        response=envelope.answer,
        integration_status=INTEGRATION_READY,
        delivery_status=envelope.delivery_status,
        response_status=envelope.response_status,
        completeness_status=envelope.completeness_status,
        intent=envelope.intent,
        course_ids=list(envelope.course_ids),
        source_ids=list(envelope.source_ids),
        supported_points=list(envelope.supported_points),
        missing_points=list(envelope.missing_points),
        warnings=list(envelope.warnings),
        grounded=envelope.grounded,
        human_handoff_required=envelope.human_handoff_required,
        safety=_safe_safety(envelope.safety),
        gate_errors=[],
    )


def agent_response_query(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> AgentResponseContract:
    envelope = deliver_query(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return adapt_delivery_to_agent(envelope)


def build_agent_response_contract(
    envelope: DeliveryEnvelope,
) -> AgentResponseContract:
    return adapt_delivery_to_agent(envelope)


def agent_response_to_dict(
    response: AgentResponseContract,
) -> Dict[str, Any]:
    return {
        "query": response.query,
        "response": response.response,
        "integration_status": response.integration_status,
        "delivery_status": response.delivery_status,
        "response_status": response.response_status,
        "completeness_status": response.completeness_status,
        "intent": response.intent,
        "course_ids": list(response.course_ids),
        "source_ids": list(response.source_ids),
        "supported_points": list(response.supported_points),
        "missing_points": list(response.missing_points),
        "warnings": list(response.warnings),
        "grounded": response.grounded,
        "human_handoff_required": response.human_handoff_required,
        "safety": copy.deepcopy(response.safety),
        "gate_errors": list(response.gate_errors),
    }


def validate_agent_response_contract(
    response: AgentResponseContract,
) -> Dict[str, Any]:
    errors = []

    if response.integration_status not in {
        INTEGRATION_READY,
        INTEGRATION_HANDOFF,
    }:
        errors.append("Invalid integration status.")

    if response.integration_status == INTEGRATION_READY:
        if response.delivery_status != DELIVERABLE:
            errors.append("INTEGRATION_READY requires DELIVERABLE.")
        if not response.response.strip():
            errors.append("INTEGRATION_READY response cannot be empty.")
        if not response.grounded:
            errors.append("INTEGRATION_READY response must be grounded.")
        if not response.source_ids:
            errors.append("INTEGRATION_READY response requires source IDs.")
        if response.gate_errors:
            errors.append("INTEGRATION_READY cannot contain gate errors.")

    if response.integration_status == INTEGRATION_HANDOFF:
        if response.response.strip():
            errors.append("INTEGRATION_HANDOFF must not expose response text.")
        if not response.human_handoff_required:
            errors.append("INTEGRATION_HANDOFF must require human handoff.")
        if not response.gate_errors:
            errors.append("INTEGRATION_HANDOFF requires a handoff reason.")

    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if response.safety.get(key) is not False:
            errors.append(f"{key} must be False.")

    if response.safety.get("no_invention") is not True:
        errors.append("no_invention must be True.")

    return {"valid": not errors, "errors": _unique(errors)}


def build_master_kb_with_agent_integration() -> Any:
    return build_master_kb_with_delivery_contract()


# Explicit downstream aliases.
integrate_delivery = adapt_delivery_to_agent
query_for_agent = agent_response_query


if __name__ == "__main__":
    kb = build_master_kb_with_agent_integration()
    result = agent_response_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    print("Batch 28 validation:", validate_agent_response_contract(result))
    print(result.integration_status)
    print(result.response)
