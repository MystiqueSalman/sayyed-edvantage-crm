from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH28 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH28.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<64}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 28 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_authorization_lifecycle"))

data = agent.build_authorization_lifecycle()

check("Six leads tracked", data["lead_count"] == 6)
check("Six authorization lifecycles generated", len(data["lifecycles"]) == 6)

for lead_id, record in data["lifecycles"].items():
    check(f"Lead identity retained / {lead_id}", record["lead_id"] == lead_id)
    check(f"Initial PENDING state / {lead_id}", record["current_state"] == "PENDING")
    check(f"Authorization not granted / {lead_id}",
          record["authorization_granted"] is False)
    check(f"Execution disabled / {lead_id}",
          record["execution_authorized"] is False)
    check(f"No-send guard / {lead_id}",
          record["send_status"] == "NOT_SENT")
    check(f"Batch-27 source retained / {lead_id}",
          record["source_batch"] == 27)
    check(f"Initial audit event / {lead_id}",
          len(record["audit_trail"]) == 1)

rules = data["lifecycle_rules"]
check("Human decision rule", rules["human_decision_required"])
check("Approved state rule", rules["approved_state"] == "APPROVED")
check("Rejected state rule", rules["rejected_state"] == "REJECTED")
check("Revoked state rule", rules["revoked_state"] == "REVOKED")
check("Rejection terminal rule", rules["rejection_is_terminal"])
check("Approval revocation rule", rules["approval_can_be_revoked"])
check("Revocation terminal rule", rules["revocation_is_terminal"])
check("Approval does not authorize execution",
      rules["approval_does_not_authorize_execution"])
check("No-send enforcement rule", rules["no_send_enforced"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("Run-local generation rule", rules["run_local_generation"])

sample = data["lifecycles"]["SE-00001"]

approved = agent.transition_authorization(
    sample, "APPROVED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Approved."
)
check("PENDING -> APPROVED transition",
      approved["current_state"] == "APPROVED")
check("APPROVED authorization state granted",
      approved["authorization_granted"] is True)
check("APPROVED remains execution-disabled",
      approved["execution_authorized"] is False)
check("APPROVED remains no-send",
      approved["send_status"] == "NOT_SENT")
check("Approval audit event ordered",
      approved["audit_trail"][-1]["event_number"] == 2)
check("Approval records prior PENDING",
      approved["audit_trail"][-1]["from_state"] == "PENDING")

revoked = agent.transition_authorization(
    approved, "REVOKED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST_2", "Revoked."
)
check("APPROVED -> REVOKED transition",
      revoked["current_state"] == "REVOKED")
check("Revoked event ordered",
      revoked["audit_trail"][-1]["event_number"] == 3)
check("Revocation records prior APPROVED",
      revoked["audit_trail"][-1]["from_state"] == "APPROVED")
check("REVOKED remains execution-disabled",
      revoked["execution_authorized"] is False)
check("REVOKED remains no-send",
      revoked["send_status"] == "NOT_SENT")

rejected = agent.transition_authorization(
    sample, "REJECTED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST_3", "Rejected."
)
check("PENDING -> REJECTED transition",
      rejected["current_state"] == "REJECTED")
check("REJECTED authorization not granted",
      rejected["authorization_granted"] is False)

check("Batch 28 verification function",
      agent.verify_authorization_lifecycle(data))

print()
print("=" * 78)
print("BATCH 28 VERIFICATION PASSED")
print("=" * 78)
