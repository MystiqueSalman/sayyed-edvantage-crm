from __future__ import annotations
import py_compile
from copy import deepcopy
from pathlib import Path
import Sayyed_EdVantage_AI_Agent_BATCH20 as agent

SOURCE = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_Agent_BATCH20.py"

def check(label, condition):
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition: raise AssertionError(label)

print("=" * 78)
print("PHASE 2 / BATCH 20 - VERIFICATION")
print("=" * 78)
py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_priority_intelligence"))

data = agent.build_priority_intelligence()
check("Six leads analyzed", data["lead_count"] == 6)
check("Eighteen interactions retained", data["total_interactions"] == 18)
check("Six priority profiles generated", len(data["intelligence"]) == 6)

expected = [f"SE-{i:05d}" for i in range(1, 7)]
check("Six-lead identity mapping", sorted(data["intelligence"]) == expected)

for lead_id, item in data["intelligence"].items():
    check(f"Readiness score retained / {lead_id}", isinstance(item["readiness_score"], int))
    check(f"Priority deterministic / {lead_id}", item["priority_level"] == agent._priority_from_score(item["readiness_score"]))
    check(f"Next-best-action deterministic / {lead_id}", item["next_best_action"] == agent._next_best_action(item))
    check(f"Action basis retained / {lead_id}", item["action_basis"]["readiness_score"] == item["readiness_score"])
    check(f"Planned-only execution / {lead_id}", item["execution_status"] == "PLANNED_ONLY")

ranked = [x["lead_id"] for x in sorted(data["intelligence"].values(), key=lambda x: (x["readiness_score"], x["lead_id"]), reverse=True)]
check("Priority ranking deterministic", data["priority_ranking"] == ranked)
check("Cross-lead identity isolation", sorted(x["lead_id"] for x in data["intelligence"].values()) == expected)

rules = data["intelligence_rules"]
check("Batch-19 source rule", rules["source"] == "BATCH19")
for label, key in [
    ("Readiness score retention rule", "readiness_score_retained"),
    ("Readiness band retention rule", "readiness_band_retained"),
    ("Latest outcome retention rule", "latest_outcome_retained"),
    ("Latest timing retention rule", "latest_timing_retained"),
    ("Priority deterministic rule", "priority_deterministic"),
    ("Next-action deterministic rule", "next_action_deterministic"),
    ("Lead identity isolation rule", "lead_identity_isolated"),
    ("No-send enforcement rule", "no_send_enforced"),
    ("Source-data immutability rule", "source_data_unchanged"),
    ("Run-local generation rule", "run_local_generation"),
]:
    check(label, rules[key])

check("Deterministic intelligence generation",
      deepcopy(agent.build_priority_intelligence()) == deepcopy(agent.build_priority_intelligence()))
check("Batch 20 verification function", agent.verify_priority_intelligence(data))

print()
print("=" * 78)
print("BATCH 20 VERIFICATION PASSED")
print("=" * 78)
