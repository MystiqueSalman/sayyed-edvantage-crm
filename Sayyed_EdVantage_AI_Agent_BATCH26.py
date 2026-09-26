from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH25 as batch25

PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
VALID_DECISIONS = {PENDING, APPROVED, REJECTED}


def build_authorization_state_machine() -> Dict[str, Any]:
    source = deepcopy(batch25.build_authorization_requests())
    states = {}

    for lead_id, request in source["authorization_requests"].items():
        states[lead_id] = {
            "lead_id": lead_id,
            "name": request.get("name", ""),
            "validation_status": request["validation_status"],
            "execution_readiness": request["execution_readiness"],
            "authorization_request": request["authorization_request"],
            "authorization_state": PENDING,
            "authorization_granted": False,
            "decision_actor": None,
            "decision_timestamp": None,
            "decision_reason": None,
            "execution_authorized": False,
            "send_status": "NOT_SENT",
            "steps": deepcopy(request["steps"]),
            "source_batch": 25,
        }

    return {
        "lead_count": len(states),
        "authorization_states": states,
        "state_machine": {
            "initial_state": PENDING,
            "approved_state": APPROVED,
            "rejected_state": REJECTED,
            "valid_states": sorted(VALID_DECISIONS),
            "human_decision_required": True,
            "approval_is_not_execution": True,
            "execution_authorized_by_default": False,
            "no_automatic_approval": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def apply_human_decision(record: Dict[str, Any], decision: str,
                         actor: str, timestamp: str,
                         reason: str | None = None) -> Dict[str, Any]:
    if decision not in {APPROVED, REJECTED}:
        raise ValueError("decision must be APPROVED or REJECTED")
    if not actor or not timestamp:
        raise ValueError("actor and timestamp are required")

    updated = deepcopy(record)
    updated["authorization_state"] = decision
    updated["authorization_granted"] = decision == APPROVED
    updated["decision_actor"] = actor
    updated["decision_timestamp"] = timestamp
    updated["decision_reason"] = reason

    # Approval is deliberately NOT execution permission.
    updated["execution_authorized"] = False
    updated["send_status"] = "NOT_SENT"
    return updated


def verify_authorization_state_machine(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or len(data["authorization_states"]) != 6:
        return False

    expected = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["authorization_states"]) != expected:
        return False

    for lead_id, item in data["authorization_states"].items():
        if item["lead_id"] != lead_id:
            return False
        if item["validation_status"] != "VALIDATED":
            return False
        if item["execution_readiness"] != "READY_FOR_AUTHORIZATION":
            return False
        if item["authorization_request"] != "AUTHORIZATION_PENDING":
            return False
        if item["authorization_state"] != PENDING:
            return False
        if item["authorization_granted"] is not False:
            return False
        if item["decision_actor"] is not None:
            return False
        if item["decision_timestamp"] is not None:
            return False
        if item["decision_reason"] is not None:
            return False
        if item["execution_authorized"] is not False:
            return False
        if item["send_status"] != "NOT_SENT":
            return False
        if len(item["steps"]) != 3 or item["source_batch"] != 25:
            return False

    sample = next(iter(data["authorization_states"].values()))
    approved = apply_human_decision(
        sample, APPROVED, "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Approved."
    )
    rejected = apply_human_decision(
        sample, REJECTED, "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Rejected."
    )

    if approved["authorization_state"] != APPROVED:
        return False
    if approved["authorization_granted"] is not True:
        return False
    if approved["execution_authorized"] is not False:
        return False
    if approved["send_status"] != "NOT_SENT":
        return False

    if rejected["authorization_state"] != REJECTED:
        return False
    if rejected["authorization_granted"] is not False:
        return False
    if rejected["execution_authorized"] is not False:
        return False
    if rejected["send_status"] != "NOT_SENT":
        return False

    rules = data["state_machine"]
    return (
        rules["initial_state"] == PENDING
        and rules["approved_state"] == APPROVED
        and rules["rejected_state"] == REJECTED
        and rules["human_decision_required"]
        and rules["approval_is_not_execution"]
        and rules["execution_authorized_by_default"] is False
        and rules["no_automatic_approval"]
        and rules["no_send_enforced"]
        and rules["source_data_unchanged"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_authorization_state_machine()
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 26")
    print("AUTHORIZATION DECISION STATE MACHINE")
    print("=" * 78)
    print(f"Leads assessed: {data['lead_count']}")
    print("INITIAL STATE: PENDING")
    print("HUMAN DECISION: REQUIRED")
    print("EXECUTION AUTHORIZED: FALSE")
    print("NO AUTOMATIC APPROVAL: ENFORCED")
    print("NO-SEND: ENFORCED")
    print("-" * 78)
    for lead_id, item in data["authorization_states"].items():
        print(f"{lead_id} | State={item['authorization_state']} | "
              f"Granted={item['authorization_granted']} | "
              f"Execution={item['execution_authorized']}")
    print("-" * 78)
    if not verify_authorization_state_machine(data):
        raise AssertionError("Batch 26 verification failed")
    print("BATCH 26 AUTHORIZATION STATE-MACHINE INTEGRITY: PASSED")
    print("=" * 78)
