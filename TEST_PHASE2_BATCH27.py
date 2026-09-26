from __future__ import annotations
import py_compile
from pathlib import Path
import Sayyed_EdVantage_AI_Agent_BATCH27 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH27.py"

def check(label: str, condition: bool) -> None:
    print(f"{label:<64}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)

print("=" * 78)
print("PHASE 2 / BATCH 27 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_authorization_audit_trail"))

data = agent.build_authorization_audit_trail()
check("Six leads tracked", data["lead_count"] == 6)
check("Six audit trails generated", len(data["audit_trails"]) == 6)

for lead_id, trail in data["audit_trails"].items():
    check(f"One initial audit event / {lead_id}", len(trail) == 1)
    event = trail[0]
    check(f"Lead identity retained / {lead_id}", event["lead_id"] == lead_id)
    check(f"Initial event numbered / {lead_id}", event["event_number"] == 1)
    check(f"Initial state PENDING / {lead_id}", event["to_state"] == "PENDING")
    check(f"No prior state / {lead_id}", event["from_state"] is None)
    check(f"No decision actor / {lead_id}", event["actor"] is None)
    check(f"No decision timestamp / {lead_id}", event["timestamp"] is None)
    check(f"Execution disabled / {lead_id}", event["execution_authorized"] is False)
    check(f"No-send guard / {lead_id}", event["send_status"] == "NOT_SENT")

rules = data["audit_rules"]
check("Batch-26 source retained", data["source_batch"] == 26)
check("Lead identity retention rule", rules["lead_identity_retained"])
check("Initial PENDING event rule", rules["initial_pending_recorded"])
check("Ordered state-transition rule", rules["state_transitions_ordered"])
check("Human decision rule", rules["human_decision_required"])
check("Approval does not authorize execution", rules["approval_does_not_authorize_execution"])
check("No-send enforcement rule", rules["no_send_enforced"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("Run-local generation rule", rules["run_local_generation"])

sample_id = "SE-00001"
initial = data["audit_trails"][sample_id]

approved = agent.append_decision_event(
    initial, sample_id, "APPROVED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Approved."
)
check("Explicit APPROVED audit transition", approved[1]["to_state"] == "APPROVED")
check("APPROVED event ordered", approved[1]["event_number"] == 2)
check("APPROVED records prior PENDING", approved[1]["from_state"] == "PENDING")
check("APPROVED records human actor", approved[1]["actor"] == "HUMAN_REVIEWER")
check("APPROVED still execution-disabled", approved[1]["execution_authorized"] is False)
check("APPROVED still no-send", approved[1]["send_status"] == "NOT_SENT")

rejected = agent.append_decision_event(
    initial, sample_id, "REJECTED", "HUMAN_REVIEWER", "RUN_LOCAL_TEST", "Rejected."
)
check("Explicit REJECTED audit transition", rejected[1]["to_state"] == "REJECTED")
check("REJECTED records prior PENDING", rejected[1]["from_state"] == "PENDING")
check("REJECTED still execution-disabled", rejected[1]["execution_authorized"] is False)
check("REJECTED still no-send", rejected[1]["send_status"] == "NOT_SENT")

check("Batch 27 verification function",
      agent.verify_authorization_audit_trail(data))

print()
print("=" * 78)
print("BATCH 27 VERIFICATION PASSED")
print("=" * 78)
