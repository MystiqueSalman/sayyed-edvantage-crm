"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 24
Validated Action Plan Execution-Readiness Gate.

Builds on verified Batch 23.
Planning/simulation only:
- no messages are sent
- no external action is executed
- source leads.json is never modified
- generated readiness records are run-local

Purpose:
Convert validated Batch-23 action plans into deterministic execution-readiness
records while keeping human authorization mandatory. Batch 24 does not execute
the plans; it establishes exactly what is ready, what is blocked, and why.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH23 as batch23


EXECUTION_READY = "READY_FOR_AUTHORIZATION"
EXECUTION_BLOCKED = "BLOCKED_PENDING_AUTHORIZATION"


def _steps(plan: Dict[str, Any]) -> List[Any]:
    value = plan.get("steps")
    if isinstance(value, list):
        return value
    value = plan.get("plan_steps")
    if isinstance(value, list):
        return value
    value = plan.get("action_plan")
    return value if isinstance(value, list) else []


def _build_source() -> Dict[str, Any]:
    return deepcopy(batch23.build_validated_action_plans())


def _readiness_for(plan: Dict[str, Any]) -> str:
    if plan.get("validation_status") != "VALIDATED":
        return EXECUTION_BLOCKED
    if plan.get("execution_authorized") is not False:
        return EXECUTION_BLOCKED
    if len(_steps(plan)) != 3:
        return EXECUTION_BLOCKED
    if plan.get("confidence") not in {"HIGH", "NORMAL"}:
        return EXECUTION_BLOCKED
    return EXECUTION_READY


def build_execution_readiness() -> Dict[str, Any]:
    source = _build_source()
    readiness: Dict[str, Dict[str, Any]] = {}

    for lead_id, original in source["plans"].items():
        plan = deepcopy(original)
        status = _readiness_for(plan)

        readiness[lead_id] = {
            "lead_id": lead_id,
            "name": plan.get("name", ""),
            "confidence": plan["confidence"],
            "validation_status": plan["validation_status"],
            "execution_authorized": False,
            "execution_readiness": status,
            "steps": deepcopy(_steps(plan)),
            "authorization_gate": "HUMAN_AUTHORIZATION_REQUIRED",
            "send_status": "NOT_SENT",
            "source_batch": 23,
        }

    return {
        "lead_count": len(readiness),
        "readiness": readiness,
        "execution_rules": {
            "validated_plan_required": True,
            "human_authorization_required": True,
            "execution_authorized_by_default": False,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def verify_execution_readiness(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or len(data["readiness"]) != 6:
        return False

    expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["readiness"]) != expected_ids:
        return False

    for lead_id, item in data["readiness"].items():
        if item["lead_id"] != lead_id:
            return False
        if item["validation_status"] != "VALIDATED":
            return False
        if item["execution_authorized"] is not False:
            return False
        if item["execution_readiness"] != EXECUTION_READY:
            return False
        if len(item["steps"]) != 3:
            return False
        if item["authorization_gate"] != "HUMAN_AUTHORIZATION_REQUIRED":
            return False
        if item["send_status"] != "NOT_SENT":
            return False
        if item["source_batch"] != 23:
            return False
        if item["confidence"] not in {"HIGH", "NORMAL"}:
            return False

    rules = data["execution_rules"]
    return (
        rules["validated_plan_required"]
        and rules["human_authorization_required"]
        and rules["execution_authorized_by_default"] is False
        and rules["no_send_enforced"]
        and rules["source_data_unchanged"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_execution_readiness()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 24")
    print("VALIDATED ACTION PLAN EXECUTION-READINESS GATE")
    print("=" * 78)
    print(f"Leads assessed: {data['lead_count']}")
    print("PLANNING / SIMULATION MODE")
    print("EXECUTION AUTHORIZED: FALSE")
    print("NO-SEND: ENFORCED")
    print("-" * 78)

    for lead_id, item in data["readiness"].items():
        print(
            f"{lead_id} | Confidence={item['confidence']} | "
            f"Readiness={item['execution_readiness']} | "
            f"Gate={item['authorization_gate']}"
        )

    print("-" * 78)
    if not verify_execution_readiness(data):
        raise AssertionError("Batch 24 execution-readiness verification failed")

    print("BATCH 24 EXECUTION-READINESS INTEGRITY: PASSED")
    print("=" * 78)
