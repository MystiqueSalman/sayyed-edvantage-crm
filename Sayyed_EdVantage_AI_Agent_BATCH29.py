"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 29
Authorization-Aware Execution Gate.

Builds on verified Batch 28.
Planning/simulation only:
- no messages are sent
- source data is never modified
- execution remains disabled
- authorization state is evaluated before any hypothetical execution

Purpose:
- Convert the authorization lifecycle into a deterministic execution gate.
- Distinguish authorization approval from actual execution permission.
- Preserve lead identity and authorization audit history.
- Ensure PENDING / REJECTED / REVOKED states cannot pass the gate.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH28 as batch28

PENDING = batch28.PENDING
APPROVED = batch28.APPROVED
REJECTED = batch28.REJECTED
REVOKED = batch28.REVOKED

GATE_BLOCKED = "BLOCKED"
GATE_READY = "READY_FOR_EXECUTION_REVIEW"


def build_execution_gate() -> Dict[str, Any]:
    """Build a run-local execution-gate representation from Batch 28."""
    source = batch28.build_authorization_lifecycle()
    gates: Dict[str, Dict[str, Any]] = {}

    for lead_id, lifecycle in source["lifecycles"].items():
        gates[lead_id] = {
            "lead_id": lead_id,
            "authorization_state": lifecycle["current_state"],
            "authorization_granted": lifecycle["authorization_granted"],
            "execution_gate": GATE_BLOCKED,
            "execution_authorized": False,
            "send_status": "NOT_SENT",
            "audit_trail": deepcopy(lifecycle["audit_trail"]),
            "source_batch": 28,
        }

    return {
        "lead_count": len(gates),
        "gates": gates,
        "gate_rules": {
            "source_batch": 28,
            "approval_required": True,
            "approval_is_not_execution": True,
            "approved_gate_requires_review": True,
            "pending_blocked": True,
            "rejected_blocked": True,
            "revoked_blocked": True,
            "execution_disabled_by_default": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def evaluate_execution_gate(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate whether an authorization record may enter execution review.

    This function never authorizes execution and never sends anything.
    """
    updated = deepcopy(record)
    state = updated["authorization_state"]

    if state == APPROVED and updated["authorization_granted"] is True:
        updated["execution_gate"] = GATE_READY
    else:
        updated["execution_gate"] = GATE_BLOCKED

    # Phase 2 remains planning/simulation only.
    updated["execution_authorized"] = False
    updated["send_status"] = "NOT_SENT"
    return updated


def verify_execution_gate(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or len(data["gates"]) != 6:
        return False

    expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["gates"]) != expected_ids:
        return False

    for lead_id, record in data["gates"].items():
        if record["lead_id"] != lead_id:
            return False
        if record["authorization_state"] != PENDING:
            return False
        if record["authorization_granted"] is not False:
            return False
        if record["execution_gate"] != GATE_BLOCKED:
            return False
        if record["execution_authorized"] is not False:
            return False
        if record["send_status"] != "NOT_SENT":
            return False
        if record["source_batch"] != 28:
            return False

    sample = data["gates"]["SE-00001"]

    pending = evaluate_execution_gate(sample)
    if pending["execution_gate"] != GATE_BLOCKED:
        return False

    approved = batch28.transition_authorization(
        {
            "lead_id": sample["lead_id"],
            "current_state": sample["authorization_state"],
            "authorization_granted": sample["authorization_granted"],
            "execution_authorized": False,
            "send_status": "NOT_SENT",
            "audit_trail": deepcopy(sample["audit_trail"]),
            "source_batch": sample["source_batch"],
        },
        APPROVED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST",
        "Approved for execution review.",
    )

    approved_gate = {
        "lead_id": approved["lead_id"],
        "authorization_state": approved["current_state"],
        "authorization_granted": approved["authorization_granted"],
        "execution_authorized": approved["execution_authorized"],
        "send_status": approved["send_status"],
        "audit_trail": approved["audit_trail"],
        "source_batch": approved["source_batch"],
    }

    approved_result = evaluate_execution_gate(approved_gate)
    if approved_result["execution_gate"] != GATE_READY:
        return False
    if approved_result["execution_authorized"] is not False:
        return False
    if approved_result["send_status"] != "NOT_SENT":
        return False

    rejected = batch28.transition_authorization(
        {
            "lead_id": sample["lead_id"],
            "current_state": sample["authorization_state"],
            "authorization_granted": sample["authorization_granted"],
            "execution_authorized": False,
            "send_status": "NOT_SENT",
            "audit_trail": deepcopy(sample["audit_trail"]),
            "source_batch": sample["source_batch"],
        },
        REJECTED,
        "HUMAN_REVIEWER",
        "RUN_LOCAL_TEST_REJECT",
        "Rejected for verification.",
    )

    rejected_result = evaluate_execution_gate({
        "lead_id": rejected["lead_id"],
        "authorization_state": rejected["current_state"],
        "authorization_granted": rejected["authorization_granted"],
        "execution_authorized": rejected["execution_authorized"],
        "send_status": rejected["send_status"],
        "audit_trail": rejected["audit_trail"],
        "source_batch": rejected["source_batch"],
    })
    if rejected_result["execution_gate"] != GATE_BLOCKED:
        return False

    rules = data["gate_rules"]
    return (
        rules["source_batch"] == 28
        and rules["approval_required"]
        and rules["approval_is_not_execution"]
        and rules["approved_gate_requires_review"]
        and rules["pending_blocked"]
        and rules["rejected_blocked"]
        and rules["revoked_blocked"]
        and rules["execution_disabled_by_default"]
        and rules["no_send_enforced"]
        and rules["source_data_unchanged"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_execution_gate()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 29")
    print("AUTHORIZATION-AWARE EXECUTION GATE")
    print("=" * 78)
    print(f"Leads assessed: {data['lead_count']}")
    print("APPROVAL REQUIRED: TRUE")
    print("APPROVAL IS NOT EXECUTION: TRUE")
    print("EXECUTION AUTHORIZED: FALSE")
    print("NO-SEND: ENFORCED")
    print("-" * 78)

    for lead_id, record in data["gates"].items():
        print(
            f"{lead_id} | State={record['authorization_state']} | "
            f"Gate={record['execution_gate']} | "
            f"Execution={record['execution_authorized']} | "
            f"Send={record['send_status']}"
        )

    print("-" * 78)
    if not verify_execution_gate(data):
        raise AssertionError("Batch 29 execution-gate verification failed")

    print("BATCH 29 EXECUTION-GATE INTEGRITY: PASSED")
    print("=" * 78)
