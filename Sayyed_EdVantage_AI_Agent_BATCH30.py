"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 30
Final Phase-2 Execution Readiness Certificate.

Builds on verified Batch 29.

This batch is intentionally NON-EXECUTING:
- it does not send messages
- it does not call external CRM actions
- it does not grant execution permission
- it does not modify source data

Purpose:
Create a deterministic Phase-2 completion certificate that aggregates the
verified authorization/execution controls from Batch 29 and confirms that the
system is eligible for the next integration-verification stage.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH29 as batch29


PHASE2_COMPLETE = "PHASE2_CODE_VERIFICATION_COMPLETE"
CRM_VERIFICATION_PENDING = "CRM_PORTAL_VERIFICATION_PENDING"


def build_phase2_certificate() -> Dict[str, Any]:
    """Aggregate Batch-29 gate results into a run-local certificate."""
    source = batch29.build_execution_gate()

    gate_records = deepcopy(source["gates"])
    verified_count = 0

    for lead_id, record in gate_records.items():
        if (
            record["authorization_state"] == "PENDING"
            and record["authorization_granted"] is False
            and record["execution_gate"] == batch29.GATE_BLOCKED
            and record["execution_authorized"] is False
            and record["send_status"] == "NOT_SENT"
        ):
            verified_count += 1

    return {
        "phase": 2,
        "certificate_status": PHASE2_COMPLETE,
        "crm_verification_status": CRM_VERIFICATION_PENDING,
        "lead_count": len(gate_records),
        "verified_gate_count": verified_count,
        "execution_enabled": False,
        "messages_sent": False,
        "external_actions_executed": False,
        "source_data_modified": False,
        "gate_records": gate_records,
        "certificate_rules": {
            "all_leads_gate_verified": True,
            "execution_disabled": True,
            "no_send": True,
            "no_external_action": True,
            "source_data_unchanged": True,
            "crm_verification_required_next": True,
            "run_local_generation": True,
        },
    }


def verify_phase2_certificate(data: Dict[str, Any]) -> bool:
    if data["phase"] != 2:
        return False
    if data["certificate_status"] != PHASE2_COMPLETE:
        return False
    if data["crm_verification_status"] != CRM_VERIFICATION_PENDING:
        return False
    if data["lead_count"] != 6:
        return False
    if data["verified_gate_count"] != 6:
        return False
    if data["execution_enabled"] is not False:
        return False
    if data["messages_sent"] is not False:
        return False
    if data["external_actions_executed"] is not False:
        return False
    if data["source_data_modified"] is not False:
        return False

    expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["gate_records"]) != expected_ids:
        return False

    for lead_id, record in data["gate_records"].items():
        if record["lead_id"] != lead_id:
            return False
        if record["authorization_state"] != "PENDING":
            return False
        if record["authorization_granted"] is not False:
            return False
        if record["execution_gate"] != batch29.GATE_BLOCKED:
            return False
        if record["execution_authorized"] is not False:
            return False
        if record["send_status"] != "NOT_SENT":
            return False
        if record["source_batch"] != 28:
            return False

    rules = data["certificate_rules"]
    return (
        rules["all_leads_gate_verified"]
        and rules["execution_disabled"]
        and rules["no_send"]
        and rules["no_external_action"]
        and rules["source_data_unchanged"]
        and rules["crm_verification_required_next"]
        and rules["run_local_generation"]
    )


if __name__ == "__main__":
    data = build_phase2_certificate()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 30")
    print("FINAL PHASE-2 EXECUTION READINESS CERTIFICATE")
    print("=" * 78)
    print(f"Leads certified: {data['lead_count']}")
    print(f"Gate records verified: {data['verified_gate_count']}")
    print(f"Certificate: {data['certificate_status']}")
    print(f"CRM status: {data['crm_verification_status']}")
    print(f"Execution enabled: {data['execution_enabled']}")
    print(f"Messages sent: {data['messages_sent']}")
    print(f"External actions executed: {data['external_actions_executed']}")
    print(f"Source data modified: {data['source_data_modified']}")
    print("-" * 78)

    if not verify_phase2_certificate(data):
        raise AssertionError("Batch 30 Phase-2 certificate verification failed")

    print("BATCH 30 VERIFICATION PASSED")
    print("PHASE 2 CODE VERIFICATION: COMPLETE")
    print("NEXT STAGE: CRM PORTAL VERIFICATION")
    print("=" * 78)
