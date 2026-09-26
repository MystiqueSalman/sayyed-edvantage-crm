"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 29
"""

from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH29 as agent

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH29.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<64}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 29 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_execution_gate"))

data = agent.build_execution_gate()

check("Six leads tracked", data["lead_count"] == 6)
check("Six execution gates generated", len(data["gates"]) == 6)

for lead_id, record in data["gates"].items():
    check(f"Lead identity retained / {lead_id}", record["lead_id"] == lead_id)
    check(f"PENDING state retained / {lead_id}", record["authorization_state"] == "PENDING")
    check(f"Authorization not granted / {lead_id}",
          record["authorization_granted"] is False)
    check(f"Execution gate blocked / {lead_id}",
          record["execution_gate"] == "BLOCKED")
    check(f"Execution disabled / {lead_id}",
          record["execution_authorized"] is False)
    check(f"No-send guard / {lead_id}",
          record["send_status"] == "NOT_SENT")
    check(f"Batch-28 source retained / {lead_id}",
          record["source_batch"] == 28)

rules = data["gate_rules"]
check("Batch-28 source rule", rules["source_batch"] == 28)
check("Approval required rule", rules["approval_required"])
check("Approval is not execution rule", rules["approval_is_not_execution"])
check("Approved gate requires review", rules["approved_gate_requires_review"])
check("PENDING blocked rule", rules["pending_blocked"])
check("REJECTED blocked rule", rules["rejected_blocked"])
check("REVOKED blocked rule", rules["revoked_blocked"])
check("Execution disabled by default", rules["execution_disabled_by_default"])
check("No-send enforcement rule", rules["no_send_enforced"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("Run-local generation rule", rules["run_local_generation"])

sample = data["gates"]["SE-00001"]

pending = agent.evaluate_execution_gate(sample)
check("PENDING execution gate blocked",
      pending["execution_gate"] == "BLOCKED")
check("PENDING execution remains disabled",
      pending["execution_authorized"] is False)
check("PENDING remains no-send",
      pending["send_status"] == "NOT_SENT")

approved = agent.batch28.transition_authorization(
    {
        "lead_id": sample["lead_id"],
        "current_state": sample["authorization_state"],
        "authorization_granted": sample["authorization_granted"],
        "execution_authorized": False,
        "send_status": "NOT_SENT",
        "audit_trail": sample["audit_trail"],
        "source_batch": sample["source_batch"],
    },
    "APPROVED",
    "HUMAN_REVIEWER",
    "RUN_LOCAL_TEST",
    "Approved for execution review.",
)

approved_result = agent.evaluate_execution_gate({
    "lead_id": approved["lead_id"],
    "authorization_state": approved["current_state"],
    "authorization_granted": approved["authorization_granted"],
    "execution_authorized": approved["execution_authorized"],
    "send_status": approved["send_status"],
    "audit_trail": approved["audit_trail"],
    "source_batch": approved["source_batch"],
})

check("APPROVED enters execution-review gate",
      approved_result["execution_gate"] == "READY_FOR_EXECUTION_REVIEW")
check("APPROVED still does not authorize execution",
      approved_result["execution_authorized"] is False)
check("APPROVED remains no-send",
      approved_result["send_status"] == "NOT_SENT")

rejected = agent.batch28.transition_authorization(
    {
        "lead_id": sample["lead_id"],
        "current_state": sample["authorization_state"],
        "authorization_granted": sample["authorization_granted"],
        "execution_authorized": False,
        "send_status": "NOT_SENT",
        "audit_trail": sample["audit_trail"],
        "source_batch": sample["source_batch"],
    },
    "REJECTED",
    "HUMAN_REVIEWER",
    "RUN_LOCAL_TEST_REJECT",
    "Rejected for verification.",
)

rejected_result = agent.evaluate_execution_gate({
    "lead_id": rejected["lead_id"],
    "authorization_state": rejected["current_state"],
    "authorization_granted": rejected["authorization_granted"],
    "execution_authorized": rejected["execution_authorized"],
    "send_status": rejected["send_status"],
    "audit_trail": rejected["audit_trail"],
    "source_batch": rejected["source_batch"],
})

check("REJECTED execution gate blocked",
      rejected_result["execution_gate"] == "BLOCKED")
check("Batch 29 verification function",
      agent.verify_execution_gate(data))

print()
print("=" * 78)
print("BATCH 29 VERIFICATION PASSED")
print("=" * 78)
