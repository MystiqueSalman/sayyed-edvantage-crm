"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 30
"""

from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH30 as agent

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH30.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<68}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 30 - FINAL VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_phase2_certificate"))

data = agent.build_phase2_certificate()

check("Phase identifier", data["phase"] == 2)
check("Phase-2 certificate status",
      data["certificate_status"] == "PHASE2_CODE_VERIFICATION_COMPLETE")
check("CRM verification correctly pending",
      data["crm_verification_status"] == "CRM_PORTAL_VERIFICATION_PENDING")
check("Six leads certified", data["lead_count"] == 6)
check("Six gate records verified", data["verified_gate_count"] == 6)
check("Execution disabled", data["execution_enabled"] is False)
check("No messages sent", data["messages_sent"] is False)
check("No external actions executed", data["external_actions_executed"] is False)
check("Source data unchanged", data["source_data_modified"] is False)

expected_ids = [f"SE-{i:05d}" for i in range(1, 7)]
check("All expected lead IDs present",
      sorted(data["gate_records"]) == expected_ids)

for lead_id, record in data["gate_records"].items():
    check(f"Lead identity / {lead_id}", record["lead_id"] == lead_id)
    check(f"PENDING authorization / {lead_id}",
          record["authorization_state"] == "PENDING")
    check(f"Authorization not granted / {lead_id}",
          record["authorization_granted"] is False)
    check(f"Gate blocked / {lead_id}",
          record["execution_gate"] == "BLOCKED")
    check(f"Execution disabled / {lead_id}",
          record["execution_authorized"] is False)
    check(f"No-send / {lead_id}",
          record["send_status"] == "NOT_SENT")
    check(f"Batch-28 source retained / {lead_id}",
          record["source_batch"] == 28)

rules = data["certificate_rules"]
check("All-leads gate verification rule", rules["all_leads_gate_verified"])
check("Execution-disabled rule", rules["execution_disabled"])
check("No-send rule", rules["no_send"])
check("No-external-action rule", rules["no_external_action"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("CRM verification required next", rules["crm_verification_required_next"])
check("Run-local generation rule", rules["run_local_generation"])

check("Batch 30 certificate verification",
      agent.verify_phase2_certificate(data))

print()
print("=" * 78)
print("BATCH 30 VERIFICATION PASSED")
print("PHASE 2 CODE VERIFICATION COMPLETE")
print("NEXT: CRM PORTAL END-TO-END VERIFICATION")
print("=" * 78)
