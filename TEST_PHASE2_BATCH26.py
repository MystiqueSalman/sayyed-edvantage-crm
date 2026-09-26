from __future__ import annotations
import py_compile
from pathlib import Path
import Sayyed_EdVantage_AI_Agent_BATCH26 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH26.py"

def check(label: str, condition: bool) -> None:
    print(f"{label:<64}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)

print("=" * 78)
print("PHASE 2 / BATCH 26 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_authorization_state_machine"))

data = agent.build_authorization_state_machine()
check("Six leads assessed", data["lead_count"] == 6)
check("Six authorization states generated", len(data["authorization_states"]) == 6)

for lead_id, item in data["authorization_states"].items():
    check(f"Lead identity retained / {lead_id}", item["lead_id"] == lead_id)
    check(f"Validated source / {lead_id}", item["validation_status"] == "VALIDATED")
    check(f"Execution readiness retained / {lead_id}",
          item["execution_readiness"] == "READY_FOR_AUTHORIZATION")
    check(f"Authorization request retained / {lead_id}",
          item["authorization_request"] == "AUTHORIZATION_PENDING")
    check(f"Initial PENDING state / {lead_id}",
          item["authorization_state"] == "PENDING")
    check(f"Authorization not granted / {lead_id}",
          item["authorization_granted"] is False)
    check(f"No decision actor / {lead_id}", item["decision_actor"] is None)
    check(f"No decision timestamp / {lead_id}", item["decision_timestamp"] is None)
    check(f"No decision reason / {lead_id}", item["decision_reason"] is None)
    check(f"Execution remains disabled / {lead_id}",
          item["execution_authorized"] is False)
    check(f"No-send guard / {lead_id}", item["send_status"] == "NOT_SENT")
    check(f"Three-step plan retained / {lead_id}", len(item["steps"]) == 3)
    check(f"Batch-25 source retained / {lead_id}", item["source_batch"] == 25)

rules = data["state_machine"]
check("Initial PENDING state", rules["initial_state"] == "PENDING")
check("APPROVED state defined", rules["approved_state"] == "APPROVED")
check("REJECTED state defined", rules["rejected_state"] == "REJECTED")
check("Human decision rule", rules["human_decision_required"])
check("Approval is not execution", rules["approval_is_not_execution"])
check("Execution disabled by default",
      rules["execution_authorized_by_default"] is False)
check("No automatic approval rule", rules["no_automatic_approval"])
check("No-send enforcement rule", rules["no_send_enforced"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("Run-local generation rule", rules["run_local_generation"])

sample = next(iter(data["authorization_states"].values()))
approved = agent.apply_human_decision(
    sample, "APPROVED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Approved."
)
rejected = agent.apply_human_decision(
    sample, "REJECTED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Rejected."
)

check("Explicit APPROVED transition", approved["authorization_state"] == "APPROVED")
check("APPROVED grants authorization state",
      approved["authorization_granted"] is True)
check("APPROVED does not authorize execution",
      approved["execution_authorized"] is False)
check("APPROVED remains no-send", approved["send_status"] == "NOT_SENT")
check("Explicit REJECTED transition", rejected["authorization_state"] == "REJECTED")
check("REJECTED does not grant authorization",
      rejected["authorization_granted"] is False)
check("REJECTED remains execution-disabled",
      rejected["execution_authorized"] is False)
check("REJECTED remains no-send", rejected["send_status"] == "NOT_SENT")
check("Batch 26 verification function",
      agent.verify_authorization_state_machine(data))

print()
print("=" * 78)
print("BATCH 26 VERIFICATION PASSED")
print("=" * 78)
