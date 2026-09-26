"""
Sayyed EdVantage AI Agent — Master KB Batch 27
Finalized Answer Delivery Contract & Read-Only Handoff

Purpose:
- Define the stable output contract between the Master KB finalization layer
  and the downstream AI Agent.
- Allow only FINALIZED, validated answers to enter the normal delivery path.
- Preserve PARTIAL answers and required human handoff without inventing data.
- Convert BLOCKED answers into a safe handoff-only delivery state.
- Keep provenance, completeness, warnings, and safety metadata intact.
- Never execute actions, send messages, call external systems, or write CRM data.

This batch is an interface/contract layer. It does not add or alter knowledge.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH26 import (
    FINALIZED,
    BLOCKED,
    FinalizedAnswer,
    finalize_query,
    validate_finalized_answer,
    build_master_kb_with_finalization_gate,
)


DELIVERABLE = "DELIVERABLE"
HANDOFF_ONLY = "HANDOFF_ONLY"


@dataclass
class DeliveryEnvelope:
    query: str
    answer: str
    delivery_status: str
    finalization_status: str
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


def _safe_safety(safety: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(safety)


def _safety_errors(safety: Dict[str, Any]) -> List[str]:
    errors = []
    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if safety.get(key) is not False:
            errors.append(f"{key} must be False.")
    if safety.get("no_invention") is not True:
        errors.append("no_invention must be True.")
    return errors


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def create_delivery_envelope(
    finalized: FinalizedAnswer,
) -> DeliveryEnvelope:
    """
    Convert a Batch-26 result into a downstream delivery contract.

    FINALIZED results may be delivered when their underlying response is
    valid. BLOCKED results never expose answer text and become HANDOFF_ONLY.
    """
    validation = validate_finalized_answer(finalized)

    errors = list(validation["errors"])

    # A Batch-26 BLOCKED result already contains the authoritative reason
    # in gate_errors. Preserve those diagnostics in the handoff envelope.
    if finalized.finalization_status == BLOCKED:
        errors.extend(finalized.gate_errors)

    errors.extend(_safety_errors(finalized.safety))
    errors = _unique(errors)

    if finalized.finalization_status == FINALIZED and not errors:
        if finalized.response_status == "NO_MATCH":
            # Defensive boundary: NO_MATCH must never become a deliverable.
            errors.append("NO_MATCH cannot enter normal delivery.")

        if finalized.completeness_status == "INCOMPLETE":
            errors.append("INCOMPLETE answers cannot enter normal delivery.")

    if errors or finalized.finalization_status == BLOCKED:
        # HANDOFF_ONLY is a safe downstream state. Never propagate an
        # unsafe action flag into the delivery contract. The original
        # violation remains auditable through gate_errors.
        handoff_safety = _safe_safety(finalized.safety)
        for key in (
            "execution_enabled",
            "messaging_enabled",
            "external_actions_enabled",
            "crm_writes_enabled",
        ):
            handoff_safety[key] = False
        handoff_safety["no_invention"] = True

        return DeliveryEnvelope(
            query=finalized.query,
            answer="",
            delivery_status=HANDOFF_ONLY,
            finalization_status=finalized.finalization_status,
            response_status=finalized.response_status,
            completeness_status=finalized.completeness_status,
            intent=finalized.intent,
            course_ids=list(finalized.course_ids),
            source_ids=list(finalized.source_ids),
            supported_points=list(finalized.supported_points),
            missing_points=list(finalized.missing_points),
            warnings=list(finalized.warnings),
            grounded=False,
            human_handoff_required=True,
            safety=handoff_safety,
            gate_errors=errors,
        )

    return DeliveryEnvelope(
        query=finalized.query,
        answer=finalized.answer,
        delivery_status=DELIVERABLE,
        finalization_status=finalized.finalization_status,
        response_status=finalized.response_status,
        completeness_status=finalized.completeness_status,
        intent=finalized.intent,
        course_ids=list(finalized.course_ids),
        source_ids=list(finalized.source_ids),
        supported_points=list(finalized.supported_points),
        missing_points=list(finalized.missing_points),
        warnings=list(finalized.warnings),
        grounded=finalized.grounded,
        human_handoff_required=finalized.human_handoff_required,
        safety=_safe_safety(finalized.safety),
        gate_errors=[],
    )


def deliver_query(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> DeliveryEnvelope:
    finalized = finalize_query(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return create_delivery_envelope(finalized)


def build_delivery_envelope(
    finalized: FinalizedAnswer,
) -> DeliveryEnvelope:
    return create_delivery_envelope(finalized)


def delivery_envelope_to_dict(
    envelope: DeliveryEnvelope,
) -> Dict[str, Any]:
    return {
        "query": envelope.query,
        "answer": envelope.answer,
        "delivery_status": envelope.delivery_status,
        "finalization_status": envelope.finalization_status,
        "response_status": envelope.response_status,
        "completeness_status": envelope.completeness_status,
        "intent": envelope.intent,
        "course_ids": list(envelope.course_ids),
        "source_ids": list(envelope.source_ids),
        "supported_points": list(envelope.supported_points),
        "missing_points": list(envelope.missing_points),
        "warnings": list(envelope.warnings),
        "grounded": envelope.grounded,
        "human_handoff_required": envelope.human_handoff_required,
        "safety": copy.deepcopy(envelope.safety),
        "gate_errors": list(envelope.gate_errors),
    }


def validate_delivery_envelope(
    envelope: DeliveryEnvelope,
) -> Dict[str, Any]:
    errors = []

    if envelope.delivery_status not in {DELIVERABLE, HANDOFF_ONLY}:
        errors.append("Invalid delivery status.")

    if envelope.delivery_status == DELIVERABLE:
        if envelope.finalization_status != FINALIZED:
            errors.append("DELIVERABLE requires FINALIZED status.")
        if envelope.response_status != "READY":
            errors.append("DELIVERABLE requires READY response status.")
        if envelope.completeness_status == "INCOMPLETE":
            errors.append("DELIVERABLE cannot be INCOMPLETE.")
        if not envelope.answer.strip():
            errors.append("DELIVERABLE answer cannot be empty.")
        if not envelope.grounded:
            errors.append("DELIVERABLE must be grounded.")
        if not envelope.source_ids:
            errors.append("DELIVERABLE requires provenance source IDs.")
        if envelope.gate_errors:
            errors.append("DELIVERABLE cannot contain gate errors.")

    if envelope.delivery_status == HANDOFF_ONLY:
        if envelope.answer.strip():
            errors.append("HANDOFF_ONLY must not expose final answer text.")
        if not envelope.human_handoff_required:
            errors.append("HANDOFF_ONLY must require human handoff.")
        if not envelope.gate_errors and envelope.finalization_status == BLOCKED:
            errors.append("BLOCKED HANDOFF_ONLY should expose gate errors.")

    errors.extend(_safety_errors(envelope.safety))

    return {"valid": not errors, "errors": _unique(errors)}


def build_master_kb_with_delivery_contract() -> Any:
    return build_master_kb_with_finalization_gate()


# Explicit downstream aliases.
create_delivery_contract = create_delivery_envelope
answer_for_delivery = deliver_query


if __name__ == "__main__":
    kb = build_master_kb_with_delivery_contract()
    result = deliver_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    print("Batch 27 validation:", validate_delivery_envelope(result))
    print(result.delivery_status)
    print(result.answer)
