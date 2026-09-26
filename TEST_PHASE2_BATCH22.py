from __future__ import annotations

import py_compile
from copy import deepcopy
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH22 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH22.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 22 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_followup_action_plans"))

data = agent.build_followup_action_plans()

check("Six leads planned", data["lead_count"] == 6)
check("Eighteen interactions retained", data["total_interactions"] == 18)
check("Six action plans generated", len(data["plans"]) == 6)

expected_leads = [f"SE-{i:05d}" for i in range(1, 7)]
check("Six-lead identity mapping", sorted(data["plans"]) == expected_leads)

for lead_id, plan in data["plans"].items():
    check(f"Lead identity retained / {lead_id}", plan["lead_id"] == lead_id)
    check(f"Priority retained / {lead_id}", bool(plan["priority_level"]))
    check(f"Urgency retained / {lead_id}", plan["urgency_level"] >= 1)
    check(f"Strategy retained / {lead_id}", bool(plan["followup_strategy"]))
    check(f"Outcome retained / {lead_id}", bool(plan["latest_outcome"]))
    check(f"Timing retained / {lead_id}", bool(plan["latest_timing"]))
    check(f"Decision basis retained / {lead_id}", bool(plan["decision_basis"]))
    check(f"Three-step plan / {lead_id}", len(plan["plan_steps"]) == 3)
    check(
        f"Authorization gate / {lead_id}",
        plan["execution_gate"].startswith("HUMAN_AUTHORIZATION_REQUIRED"),
    )
    check(
        f"Planned-only execution / {lead_id}",
        plan["execution_status"] == "PLANNED_ONLY",
    )
    check(
        f"No execution step / {lead_id}",
        plan["plan_steps"][-1] == "Hold for authorized human execution",
    )

expected_rank = [
    x["lead_id"]
    for x in sorted(
        data["plans"].values(),
        key=lambda x: (x["urgency_level"], x["priority_level"], x["lead_id"]),
        reverse=True,
    )
]
check("Plan ranking deterministic", data["plan_ranking"] == expected_rank)
check(
    "Cross-lead identity isolation",
    sorted(x["lead_id"] for x in data["plans"].values()) == expected_leads,
)

rules = data["planning_rules"]
check("Batch-21 source rule", rules["source"] == "BATCH21")

for label, key in [
    ("Identity retention rule", "identity_retained"),
    ("Priority retention rule", "priority_retained"),
    ("Urgency retention rule", "urgency_retained"),
    ("Strategy retention rule", "strategy_retained"),
    ("Outcome retention rule", "outcome_retained"),
    ("Timing retention rule", "timing_retained"),
    ("Decision-basis retention rule", "decision_basis_retained"),
    ("Three-step plan generation rule", "three_step_plan_generated"),
    ("Execution-gate deterministic rule", "execution_gate_deterministic"),
    ("Human authorization rule", "human_authorization_required"),
    ("No-send enforcement rule", "no_send_enforced"),
    ("Source-data immutability rule", "source_data_unchanged"),
    ("Run-local generation rule", "run_local_generation"),
]:
    check(label, rules[key])

check(
    "Deterministic action-plan generation",
    deepcopy(agent.build_followup_action_plans())
    == deepcopy(agent.build_followup_action_plans()),
)

check(
    "Batch 22 verification function",
    agent.verify_followup_action_plans(data),
)

print()
print("=" * 78)
print("BATCH 22 VERIFICATION PASSED")
print("=" * 78)
