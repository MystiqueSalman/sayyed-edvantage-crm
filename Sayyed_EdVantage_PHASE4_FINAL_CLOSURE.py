"""
Sayyed EdVantage — Phase 4 Final Integration Closure

This is the final controlled closure gate before live-agent testing.
It does not execute admissions actions, send messages, or write CRM data.
It validates that the live-agent boundary is structurally ready for the
planned live test sequence.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PHASE4_CLOSURE_READY = "PHASE4_CLOSURE_READY"
PHASE4_CLOSURE_CLARIFICATION = "PHASE4_CLOSURE_CLARIFICATION"
PHASE4_CLOSURE_REVIEW = "PHASE4_CLOSURE_REVIEW"
PHASE4_CLOSURE_BLOCKED = "PHASE4_CLOSURE_BLOCKED"
PHASE4_CLOSURE_UNKNOWN = "PHASE4_CLOSURE_UNKNOWN"

LIVE_TEST_READY = "LIVE_TEST_READY"
LIVE_TEST_BLOCKED = "LIVE_TEST_BLOCKED"

@dataclass
class Phase4ClosureResult:
    status: str
    live_test_status: str
    integration_count: int
    session_id: Optional[str] = None
    lead_id: Optional[str] = None
    verified_components: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    human_handoff: bool = False

    # Hard boundary: all remain false.
    crm_write_occurred: bool = False
    message_sent: bool = False
    external_action_occurred: bool = False
    executor_invoked: bool = False
    execution_occurred: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "live_test_status": self.live_test_status,
            "integration_count": self.integration_count,
            "session_id": self.session_id,
            "lead_id": self.lead_id,
            "verified_components": list(self.verified_components),
            "evidence": [dict(x) for x in self.evidence],
            "provenance": list(self.provenance),
            "errors": list(self.errors),
            "human_handoff": self.human_handoff,
            "crm_write_occurred": self.crm_write_occurred,
            "message_sent": self.message_sent,
            "external_action_occurred": self.external_action_occurred,
            "executor_invoked": self.executor_invoked,
            "execution_occurred": self.execution_occurred,
        }

def validate_phase4_closure(result: Phase4ClosureResult) -> List[str]:
    errors: List[str] = []
    statuses = {
        PHASE4_CLOSURE_READY,
        PHASE4_CLOSURE_CLARIFICATION,
        PHASE4_CLOSURE_REVIEW,
        PHASE4_CLOSURE_BLOCKED,
        PHASE4_CLOSURE_UNKNOWN,
    }
    live_statuses = {LIVE_TEST_READY, LIVE_TEST_BLOCKED}

    if result.status not in statuses:
        errors.append("invalid Phase 4 closure status")
    if result.live_test_status not in live_statuses:
        errors.append("invalid live test status")
    if result.integration_count < 1:
        errors.append("integration_count must be positive")

    if result.status == PHASE4_CLOSURE_READY:
        if result.live_test_status != LIVE_TEST_READY:
            errors.append("ready closure requires LIVE_TEST_READY")
        if result.errors:
            errors.append("ready closure cannot contain errors")

    if result.status in {
        PHASE4_CLOSURE_REVIEW,
        PHASE4_CLOSURE_BLOCKED,
        PHASE4_CLOSURE_UNKNOWN,
    } and result.live_test_status == LIVE_TEST_READY:
        errors.append("non-ready closure cannot expose LIVE_TEST_READY")

    if result.status == PHASE4_CLOSURE_REVIEW and not result.human_handoff:
        errors.append("review closure requires human handoff")

    if result.crm_write_occurred:
        errors.append("CRM writes are prohibited at Phase 4 closure")
    if result.message_sent:
        errors.append("message sending is prohibited at Phase 4 closure")
    if result.external_action_occurred:
        errors.append("external actions are prohibited at Phase 4 closure")
    if result.executor_invoked:
        errors.append("executor invocation is prohibited at Phase 4 closure")
    if result.execution_occurred:
        errors.append("execution is prohibited at Phase 4 closure")

    return errors

def build_phase4_closure(
    *,
    integration_count: int = 10,
    session_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    component_results: Optional[Dict[str, Any]] = None,
) -> Phase4ClosureResult:
    if integration_count < 10:
        return Phase4ClosureResult(
            status=PHASE4_CLOSURE_BLOCKED,
            live_test_status=LIVE_TEST_BLOCKED,
            integration_count=integration_count,
            session_id=session_id,
            lead_id=lead_id,
            errors=["Phase 4 integrations 01-10 are required before live testing"],
        )

    components = [
        "MASTER_KB",
        "AI_CORE_01_30",
        "CRM_READ_LAYER",
        "PHASE4_INTEGRATION_01",
        "PHASE4_INTEGRATION_02",
        "PHASE4_INTEGRATION_03",
        "PHASE4_INTEGRATION_04",
        "PHASE4_INTEGRATION_05",
        "PHASE4_INTEGRATION_06",
        "PHASE4_INTEGRATION_07",
        "PHASE4_INTEGRATION_08",
        "PHASE4_INTEGRATION_09",
        "PHASE4_INTEGRATION_10",
        "LIVE_AGENT_BOUNDARY",
    ]

    errors: List[str] = []
    if component_results:
        for name, value in component_results.items():
            if value is False:
                errors.append(f"component verification failed: {name}")

    if errors:
        return Phase4ClosureResult(
            status=PHASE4_CLOSURE_REVIEW,
            live_test_status=LIVE_TEST_BLOCKED,
            integration_count=integration_count,
            session_id=session_id,
            lead_id=lead_id,
            verified_components=components,
            errors=errors,
            human_handoff=True,
            provenance=["PHASE4_FINAL_CLOSURE"],
        )

    return Phase4ClosureResult(
        status=PHASE4_CLOSURE_READY,
        live_test_status=LIVE_TEST_READY,
        integration_count=integration_count,
        session_id=session_id,
        lead_id=lead_id,
        verified_components=components,
        evidence=[{
            "type": "boundary_gate",
            "status": "ready",
            "meaning": "ready to begin controlled live testing; not permission to execute actions",
        }],
        provenance=["MASTER_KB", "AI_CORE_01_30", "CRM_READ_LAYER", "PHASE4_INTEGRATION_01_10"],
    )

def phase4_closure_query(
    session_id: Optional[str] = None,
    lead_id: Optional[str] = None,
) -> Phase4ClosureResult:
    return build_phase4_closure(session_id=session_id, lead_id=lead_id)

def validate_serialized_phase4_closure(data: Dict[str, Any]) -> List[str]:
    if not isinstance(data, dict):
        return ["serialized closure must be a dict"]
    required = {"status", "live_test_status", "integration_count"}
    missing = sorted(required - set(data))
    if missing:
        return [f"missing serialized fields: {', '.join(missing)}"]
    result = Phase4ClosureResult(
        status=str(data.get("status", "")),
        live_test_status=str(data.get("live_test_status", "")),
        integration_count=int(data.get("integration_count", 0)),
        session_id=data.get("session_id"),
        lead_id=data.get("lead_id"),
        verified_components=list(data.get("verified_components", [])),
        evidence=list(data.get("evidence", [])),
        provenance=list(data.get("provenance", [])),
        errors=list(data.get("errors", [])),
        human_handoff=bool(data.get("human_handoff", False)),
        crm_write_occurred=bool(data.get("crm_write_occurred", False)),
        message_sent=bool(data.get("message_sent", False)),
        external_action_occurred=bool(data.get("external_action_occurred", False)),
        executor_invoked=bool(data.get("executor_invoked", False)),
        execution_occurred=bool(data.get("execution_occurred", False)),
    )
    return validate_phase4_closure(result)
