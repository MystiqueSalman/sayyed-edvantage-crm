from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH26 as batch26

PENDING = batch26.PENDING
APPROVED = batch26.APPROVED
REJECTED = batch26.REJECTED


def build_authorization_audit_trail() -> Dict[str, Any]:
    """Build a run-local, immutable-source authorization audit representation."""
    source = batch26.build_authorization_state_machine()
    audit: Dict[str, list[Dict[str, Any]]] = {}

    for lead_id, record in source["authorization_states"].items():
        audit[lead_id] = [{
            "event_number": 1,
            "lead_id": lead_id,
            "from_state": None,
            "to_state": PENDING,
            "actor": None,
            "timestamp": None,
            "reason": "Initial authorization state",
            "execution_authorized": False,
            "send_status": "NOT_SENT",
        }]

    return {
        "lead_count": len(audit),
        "audit_trails": audit,
        "source_batch": 26,
        "audit_rules": {
            "lead_identity_retained": True,
            "initial_pending_recorded": True,
            "state_transitions_ordered": True,
            "human_decision_required": True,
            "approval_does_not_authorize_execution": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def append_decision_event(
    trail: list[Dict[str, Any]],
    lead_id: str,
    decision: str,
    actor: str,
    timestamp: str,
    reason: str | None = None,
) -> list[Dict[str, Any]]:
    """Return a new audit trail containing one explicit human decision event."""
    if decision not in {APPROVED, REJECTED}:
        raise ValueError("decision must be APPROVED or REJECTED")
    if not actor or not timestamp:
        raise ValueError("actor and timestamp are required")
    if not trail:
        raise ValueError("audit trail must begin with the PENDING event")

    previous = trail[-1]
    if previous["lead_id"] != lead_id:
        raise ValueError("lead identity mismatch")

    updated = deepcopy(trail)
    updated.append({
        "event_number": len(updated) + 1,
        "lead_id": lead_id,
        "from_state": previous["to_state"],
        "to_state": decision,
        "actor": actor,
        "timestamp": timestamp,
        "reason": reason,
        "execution_authorized": False,
        "send_status": "NOT_SENT",
    })
    return updated


def verify_authorization_audit_trail(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6:
        return False
    if len(data["audit_trails"]) != 6:
        return False

    expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["audit_trails"]) != expected_ids:
        return False

    for lead_id, trail in data["audit_trails"].items():
        if len(trail) != 1:
            return False

        event = trail[0]
        if event["event_number"] != 1:
            return False
        if event["lead_id"] != lead_id:
            return False
        if event["from_state"] is not None:
            return False
        if event["to_state"] != PENDING:
            return False
        if event["actor"] is not None or event["timestamp"] is not None:
            return False
        if event["execution_authorized"] is not False:
            return False
        if event["send_status"] != "NOT_SENT":
            return False

    # Verify that explicit decisions create ordered, attributable events
    # without opening execution or sending.
    sample_id = expected_ids[0]
    initial = data["audit_trails"][sample_id]

    approved = append_decision_event(
        initial,
        sample_id,
        APPROVED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST",
        "Approved by reviewer.",
    )
    if len(approved) != 2:
        return False
    if approved[1]["event_number"] != 2:
        return False
    if approved[1]["from_state"] != PENDING:
        return False
    if approved[1]["to_state"] != APPROVED:
        return False
    if approved[1]["actor"] != "HUMAN_REVIEWER":
        return False
    if approved[1]["execution_authorized"] is not False:
        return False
    if approved[1]["send_status"] != "NOT_SENT":
        return False

    rejected = append_decision_event(
        initial,
        sample_id,
        REJECTED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST",
        "Rejected by reviewer.",
    )
    if rejected[1]["to_state"] != REJECTED:
        return False

    rules = data["audit_rules"]
    return (
        data["source_batch"] == 26
        and rules["lead_identity_retained"]
        and rules["initial_pending_recorded"]
        and rules["state_transitions_ordered"]
        and rules["human_decision_required"]
        and rules["approval_does_not_authorize_execution"]
        and rules["no_send_enforced"]
        and rules["source_data_unchanged"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_authorization_audit_trail()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 27")
    print("AUTHORIZATION AUDIT TRAIL")
    print("=" * 78)
    print(f"Leads tracked: {data['lead_count']}")
    print("INITIAL AUTHORIZATION STATE: PENDING")
    print("HUMAN DECISION: REQUIRED")
    print("AUDIT TRAIL: RUN-LOCAL")
    print("EXECUTION AUTHORIZED: FALSE")
    print("NO-SEND: ENFORCED")
    print("-" * 78)

    for lead_id, trail in data["audit_trails"].items():
        event = trail[-1]
        print(
            f"{lead_id} | Event #{event['event_number']} | "
            f"{event['to_state']} | Execution={event['execution_authorized']} | "
            f"Send={event['send_status']}"
        )

    print("-" * 78)
    if not verify_authorization_audit_trail(data):
        raise AssertionError("Batch 27 authorization audit-trail verification failed")
    print("BATCH 27 AUTHORIZATION AUDIT-TRAIL INTEGRITY: PASSED")
    print("=" * 78)
