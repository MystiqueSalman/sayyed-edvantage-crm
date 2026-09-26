"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 25
Controlled Authorization Request Layer.

Builds on verified Batch 24.
Planning/simulation only:
- no authorization is granted automatically
- no messages are sent
- no external action is executed
- source data remains unchanged
- authorization records are run-local

Purpose:
Transform Batch-24 execution-readiness records into explicit, deterministic
authorization-request envelopes. A plan may be READY_FOR_AUTHORIZATION, but
Batch 25 never treats readiness as permission. Human authorization remains a
separate gate.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH24 as batch24


REQUEST_PENDING = "AUTHORIZATION_PENDING"
REQUEST_BLOCKED = "AUTHORIZATION_BLOCKED"


def _build_source() -> Dict[str, Any]:
    return deepcopy(batch24.build_execution_readiness())


def _request_status(item: Dict[str, Any]) -> str:
    if item.get("execution_readiness") != batch24.EXECUTION_READY:
        return REQUEST_BLOCKED
    if item.get("execution_authorized") is not False:
        return REQUEST_BLOCKED
    if item.get("send_status") != "NOT_SENT":
        return REQUEST_BLOCKED
    return REQUEST_PENDING


def build_authorization_requests() -> Dict[str, Any]:
    source = _build_source()
    requests: Dict[str, Dict[str, Any]] = {}

    for lead_id, item in source["readiness"].items():
        record = deepcopy(item)

        requests[lead_id] = {
            "lead_id": lead_id,
            "name": record.get("name", ""),
            "confidence": record["confidence"],
            "validation_status": record["validation_status"],
            "execution_readiness": record["execution_readiness"],
            "authorization_request": _request_status(record),
            "authorization_granted": False,
            "authorization_required": True,
            "authorization_actor": None,
            "authorization_timestamp": None,
            "steps": deepcopy(record["steps"]),
            "send_status": "NOT_SENT",
            "source_batch": 24,
        }

    return {
        "lead_count": len(requests),
        "authorization_requests": requests,
        "authorization_rules": {
            "readiness_required": True,
            "human_authorization_required": True,
            "authorization_granted_by_default": False,
            "no_automatic_approval": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def verify_authorization_requests(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6:
        return False
    if len(data["authorization_requests"]) != 6:
        return False

    expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["authorization_requests"]) != expected_ids:
        return False

    for lead_id, item in data["authorization_requests"].items():
        if item["lead_id"] != lead_id:
            return False
        if item["validation_status"] != "VALIDATED":
            return False
        if item["execution_readiness"] != batch24.EXECUTION_READY:
            return False
        if item["authorization_request"] != REQUEST_PENDING:
            return False
        if item["authorization_granted"] is not False:
            return False
        if item["authorization_required"] is not True:
            return False
        if item["authorization_actor"] is not None:
            return False
        if item["authorization_timestamp"] is not None:
            return False
        if len(item["steps"]) != 3:
            return False
        if item["send_status"] != "NOT_SENT":
            return False
        if item["source_batch"] != 24:
            return False

    rules = data["authorization_rules"]
    return (
        rules["readiness_required"]
        and rules["human_authorization_required"]
        and rules["authorization_granted_by_default"] is False
        and rules["no_automatic_approval"]
        and rules["no_send_enforced"]
        and rules["source_data_unchanged"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_authorization_requests()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 25")
    print("CONTROLLED AUTHORIZATION REQUEST LAYER")
    print("=" * 78)
    print(f"Leads assessed: {data['lead_count']}")
    print("PLANNING / SIMULATION MODE")
    print("AUTHORIZATION GRANTED: FALSE")
    print("NO AUTOMATIC APPROVAL: ENFORCED")
    print("NO-SEND: ENFORCED")
    print("-" * 78)

    for lead_id, item in data["authorization_requests"].items():
        print(
            f"{lead_id} | Readiness={item['execution_readiness']} | "
            f"Request={item['authorization_request']} | "
            f"Granted={item['authorization_granted']}"
        )

    print("-" * 78)
    if not verify_authorization_requests(data):
        raise AssertionError("Batch 25 authorization-request verification failed")

    print("BATCH 25 AUTHORIZATION-REQUEST INTEGRITY: PASSED")
    print("=" * 78)
