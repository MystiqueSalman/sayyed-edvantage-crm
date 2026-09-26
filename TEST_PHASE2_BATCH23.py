from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH23 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH23.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 23 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_validated_action_plans"))

data = agent.build_validated_action_plans()
check("Six leads validated", data["lead_count"] == 6)
check("Six plans retained", len(data["plans"]) == 6)

for lead_id, plan in data["plans"].items():
    check(f"Lead identity retained / {lead_id}", plan.get("lead_id") == lead_id)
    check(f"Three-step plan retained / {lead_id}", len(agent._steps(plan)) == 3)
    check(f"Validation status / {lead_id}", plan.get("validation_status") == "VALIDATED")
    check(f"Confidence deterministic / {lead_id}", plan.get("confidence") in {"HIGH", "NORMAL"})
    check(f"Execution gate / {lead_id}", plan.get("execution_authorized") is False)
    check(f"Batch-22 source / {lead_id}", plan.get("source_batch") == 22)

rules = data["validation_rules"]
check("Batch-22 source immutability rule", rules["source_batch_immutable"])
check("Plan structure validation rule", rules["plan_structure_validated"])
check("Confidence deterministic rule", rules["confidence_deterministic"])
check("Execution disabled by default", rules["execution_authorized_by_default"] is False)
check("No-send enforcement rule", rules["no_send_enforced"])
check("Run-local generation rule", rules["run_local"])
check("Batch 23 verification function", agent.verify_validated_action_plans(data))

print()
print("=" * 78)
print("BATCH 23 VERIFICATION PASSED")
print("=" * 78)
