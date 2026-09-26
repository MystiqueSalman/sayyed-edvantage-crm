from __future__ import annotations

import py_compile
from copy import deepcopy
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH21 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH21.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 21 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_adaptive_followup_intelligence"))

data = agent.build_adaptive_followup_intelligence()

check("Six leads analyzed", data["lead_count"] == 6)
check("Eighteen interactions retained", data["total_interactions"] == 18)
check("Six adaptive profiles generated", len(data["intelligence"]) == 6)

expected_leads = [f"SE-{i:05d}" for i in range(1, 7)]
check("Six-lead identity mapping", sorted(data["intelligence"]) == expected_leads)

for lead_id, item in data["intelligence"].items():
    check(
        f"Priority retained / {lead_id}",
        bool(item["priority_level"]),
    )
    check(
        f"Next-best-action retained / {lead_id}",
        bool(item["next_best_action"]),
    )
    check(
        f"Latest outcome retained / {lead_id}",
        bool(item["latest_outcome"]),
    )
    check(
        f"Latest timing retained / {lead_id}",
        bool(item["latest_timing"]),
    )
    check(
        f"Strategy deterministic / {lead_id}",
        item["followup_strategy"] == agent._strategy_for_action(item),
    )
    check(
        f"Urgency deterministic / {lead_id}",
        item["urgency_level"] == agent._urgency_for_priority(item["priority_level"]),
    )
    check(
        f"Decision basis retained / {lead_id}",
        item["decision_basis"]["priority_level"] == item["priority_level"]
        and item["decision_basis"]["next_best_action"] == item["next_best_action"]
        and item["decision_basis"]["latest_outcome"] == item["latest_outcome"]
        and item["decision_basis"]["latest_timing"] == item["latest_timing"],
    )
    check(
        f"Planned-only execution / {lead_id}",
        item["execution_status"] == "PLANNED_ONLY",
    )

expected_rank = [
    x["lead_id"]
    for x in sorted(
        data["intelligence"].values(),
        key=lambda x: (x["urgency_level"], x["readiness_score"], x["lead_id"]),
        reverse=True,
    )
]
check("Adaptive follow-up ranking deterministic", data["followup_ranking"] == expected_rank)
check(
    "Cross-lead identity isolation",
    sorted(x["lead_id"] for x in data["intelligence"].values()) == expected_leads,
)

rules = data["intelligence_rules"]
check("Batch-20 source rule", rules["source"] == "BATCH20")

for label, key in [
    ("Priority retention rule", "priority_retained"),
    ("Next-best-action retention rule", "next_best_action_retained"),
    ("Latest outcome retention rule", "latest_outcome_retained"),
    ("Latest timing retention rule", "latest_timing_retained"),
    ("Readiness band retention rule", "readiness_band_retained"),
    ("Strategy deterministic rule", "strategy_deterministic"),
    ("Urgency deterministic rule", "urgency_deterministic"),
    ("Lead identity isolation rule", "lead_identity_isolated"),
    ("No-send enforcement rule", "no_send_enforced"),
    ("Source-data immutability rule", "source_data_unchanged"),
    ("Run-local generation rule", "run_local_generation"),
]:
    check(label, rules[key])

check(
    "Deterministic adaptive intelligence generation",
    deepcopy(agent.build_adaptive_followup_intelligence())
    == deepcopy(agent.build_adaptive_followup_intelligence()),
)

check(
    "Batch 21 verification function",
    agent.verify_adaptive_followup_intelligence(data),
)

print()
print("=" * 78)
print("BATCH 21 VERIFICATION PASSED")
print("=" * 78)
