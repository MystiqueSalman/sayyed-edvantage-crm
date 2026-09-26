"""Verification — Phase 2 / Batch 19
Longitudinal Lead Scoring & Readiness Intelligence.
"""
from __future__ import annotations
import py_compile
from copy import deepcopy
from pathlib import Path
import Sayyed_EdVantage_AI_Agent_BATCH19 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH19.py"

def check(label: str, condition: bool) -> None:
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)

print("=" * 78)
print("PHASE 2 / BATCH 19 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_readiness_intelligence"))

data = agent.build_readiness_intelligence()
check("Six leads analyzed", data["lead_count"] == 6)
check("Eighteen interactions analyzed", data["total_interactions"] == 18)
check("Six intelligence profiles generated", len(data["intelligence"]) == 6)

expected_leads = [f"SE-{i:05d}" for i in range(1, 7)]
check("Six-lead identity mapping", sorted(data["intelligence"]) == expected_leads)

for lead_id, item in data["intelligence"].items():
    check(f"Three interactions analyzed / {lead_id}", item["interaction_count"] == 3)
    check(f"Lead identity retained / {lead_id}", item["lead_id"] == lead_id)
    check(f"Sequence retained / {lead_id}", item["sequence"] in range(1, 7))
    check(f"Outcome trajectory retained / {lead_id}", len(item["outcome_trajectory"]) == 3)
    check(f"Current state retained / {lead_id}", bool(item["current_state"]))
    check(f"Latest outcome retained / {lead_id}", bool(item["latest_outcome"]))
    check(f"Latest action retained / {lead_id}", bool(item["latest_action"]))
    check(f"Priority retained / {lead_id}", bool(item["latest_priority"]))
    check(f"Channel retained / {lead_id}", bool(item["latest_channel"]))
    check(f"Timing retained / {lead_id}", bool(item["latest_timing"]))
    score = agent._calculate_score(item["outcome_trajectory"])
    check(f"Readiness score deterministic / {lead_id}", item["readiness_score"] == score)
    check(f"Readiness band deterministic / {lead_id}", item["readiness_band"] == agent._readiness_band(score))
    check(f"No-send guard / {lead_id}", item["send_status"] == "NOT_SENT")

check(
    "Deterministic outcome scoring model",
    data["scoring_model"] == {
        **agent.OUTCOME_WEIGHTS,
        "latest_interaction_has_greatest_influence": True,
        "unknown_outcomes_default_to_zero": True,
    },
)

for lead_id, item in data["intelligence"].items():
    reconstructed = {}
    for outcome in item["outcome_trajectory"]:
        reconstructed[outcome] = reconstructed.get(outcome, 0) + 1
    check(f"Outcome counts / {lead_id}", item["outcome_counts"] == reconstructed)

check(
    "Cross-lead identity isolation",
    [x["lead_id"] for x in data["intelligence"].values()] == expected_leads,
)

rules = data["intelligence_rules"]
check("Batch-18 source rule", rules["source"] == "BATCH18")
for label, key in [
    ("Lead identity retention rule", "lead_identity_retained"),
    ("Outcome history retention rule", "outcome_history_retained"),
    ("Latest state retention rule", "latest_state_retained"),
    ("Latest outcome retention rule", "latest_outcome_retained"),
    ("Latest action retention rule", "latest_action_retained"),
    ("Priority retention rule", "priority_retained"),
    ("Channel retention rule", "channel_retained"),
    ("Timing retention rule", "timing_retained"),
    ("No-send enforcement rule", "no_send_enforced"),
    ("Source-data immutability rule", "source_data_unchanged"),
    ("Run-local generation rule", "run_local_generation"),
]:
    check(label, rules[key])

check(
    "Deterministic intelligence generation",
    deepcopy(agent.build_readiness_intelligence()) == deepcopy(agent.build_readiness_intelligence()),
)

check(
    "Batch 19 verification function",
    agent.verify_readiness_intelligence(data),
)

print()
print("=" * 78)
print("BATCH 19 VERIFICATION PASSED")
print("=" * 78)
