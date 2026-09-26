from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH27 as batch27

PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
REVOKED = "REVOKED"

DECISION_STATES = {APPROVED, REJECTED}
TERMINAL_STATES = {REJECTED, REVOKED}


def build_authorization_lifecycle() -> Dict[str, Any]:
    """Build a run-local authorization lifecycle on top of Batch 27."""
    source = batch27.build_authorization_audit_trail()
    lifecycles: Dict[str, Dict[str, Any]] = {}

    for lead_id, trail in source["audit_trails"].items():
        lifecycles[lead_id] = {
            "lead_id": lead_id,
            "current_state": PENDING,
            "authorization_granted": False,
            "execution_authorized": False,
            "send_status": "NOT_SENT",
            "audit_trail": deepcopy(trail),
            "source_batch": 27,
        }

    return {
        "lead_count": len(lifecycles),
        "lifecycles": lifecycles,
        "lifecycle_rules": {
            "initial_state": PENDING,
            "human_decision_required": True,
            "approved_state": APPROVED,
            "rejected_state": REJECTED,
            "revoked_state": REVOKED,
            "rejection_is_terminal": True,
            "revocation_is_terminal": True,
            "approval_can_be_revoked": True,
            "approval_does_not_authorize_execution": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def transition_authorization(
    record: Dict[str, Any],
    target_state: str,
    actor: str,
    timestamp: str,
    reason: str | None = None,
) -> Dict[str, Any]:
    """Apply one permitted human authorization lifecycle transition.

    This function never authorizes execution and never sends anything.
    """
    if target_state not in DECISION_STATES | {REVOKED}:
        raise ValueError("Unsupported target authorization state")
    if not actor or not timestamp:
        raise ValueError("actor and timestamp are required")

    current = record["current_state"]

    allowed = {
        PENDING: {APPROVED, REJECTED},
        APPROVED: {REVOKED},
        REJECTED: set(),
        REVOKED: set(),
    }

    if target_state not in allowed[current]:
        raise ValueError(
            f"Invalid authorization transition: {current} -> {target_state}"
        )

    updated = deepcopy(record)
    trail: List[Dict[str, Any]] = updated["audit_trail"]

    trail.append({
        "event_number": len(trail) + 1,
        "lead_id": updated["lead_id"],
        "from_state": current,
        "to_state": target_state,
        "actor": actor,
        "timestamp": timestamp,
        "reason": reason,
        "execution_authorized": False,
        "send_status": "NOT_SENT",
    })

    updated["current_state"] = target_state
    updated["authorization_granted"] = target_state == APPROVED
    updated["execution_authorized"] = False
    updated["send_status"] = "NOT_SENT"
    return updated


def verify_authorization_lifecycle(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or len(data["lifecycles"]) != 6:
        return False

    expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["lifecycles"]) != expected_ids:
        return False

    for lead_id, record in data["lifecycles"].items():
        if record["lead_id"] != lead_id:
            return False
        if record["current_state"] != PENDING:
            return False
        if record["authorization_granted"] is not False:
            return False
        if record["execution_authorized"] is not False:
            return False
        if record["send_status"] != "NOT_SENT":
            return False
        if record["source_batch"] != 27:
            return False

        trail = record["audit_trail"]
        if len(trail) != 1:
            return False
        if trail[0]["to_state"] != PENDING:
            return False
        if trail[0]["lead_id"] != lead_id:
            return False

    sample = data["lifecycles"]["SE-00001"]

    approved = transition_authorization(
        sample,
        APPROVED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST",
        "Approved.",
    )
    if approved["current_state"] != APPROVED:
        return False
    if approved["authorization_granted"] is not True:
        return False
    if approved["execution_authorized"] is not False:
        return False
    if approved["send_status"] != "NOT_SENT":
        return False
    if len(approved["audit_trail"]) != 2:
        return False

    revoked = transition_authorization(
        approved,
        REVOKED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST_2",
        "Authorization revoked for verification.",
    )
    if revoked["current_state"] != REVOKED:
        return False
    if revoked["authorization_granted"] is not False:
        return False
    if revoked["execution_authorized"] is not False:
        return False
    if revoked["send_status"] != "NOT_SENT":
        return False
    if len(revoked["audit_trail"]) != 3:
        return False

    rejected = transition_authorization(
        sample,
        REJECTED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST_3",
        "Rejected.",
    )
    if rejected["current_state"] != REJECTED:
        return False
    if rejected["authorization_granted"] is not False:
        return False

    rules = data["lifecycle_rules"]
    return (
        rules["initial_state"] == PENDING
        and rules["human_decision_required"]
        and rules["approved_state"] == APPROVED
        and rules["rejected_state"] == REJECTED
        and rules["revoked_state"] == REVOKED
        and rules["rejection_is_terminal"]
        and rules["revocation_is_terminal"]
        and rules["approval_can_be_revoked"]
        and rules["approval_does_not_authorize_execution"]
        and rules["no_send_enforced"]
        and rules["source_data_unchanged"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_authorization_lifecycle()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 28 FIXED")
    print("AUTHORIZATION LIFECYCLE CONTROL")
    print("=" * 78)
    print(f"Leads tracked: {data['lead_count']}")
    print("INITIAL STATE: PENDING")
    print("HUMAN DECISION: REQUIRED")
    print("APPROVAL: REVOCABLE")
    print("REJECTION: TERMINAL")
    print("EXECUTION AUTHORIZED: FALSE")
    print("NO-SEND: ENFORCED")
    print("-" * 78)

    for lead_id, record in data["lifecycles"].items():
        print(
            f"{lead_id} | State={record['current_state']} | "
            f"Granted={record['authorization_granted']} | "
            f"Execution={record['execution_authorized']} | "
            f"Send={record['send_status']}"
        )

    print("-" * 78)
    if not verify_authorization_lifecycle(data):
        raise AssertionError("Batch 28 authorization lifecycle verification failed")

    print("BATCH 28 AUTHORIZATION-LIFECYCLE INTEGRITY: PASSED")
    print("=" * 78)
