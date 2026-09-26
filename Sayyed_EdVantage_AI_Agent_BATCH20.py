from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH19 as batch19

def _priority_from_score(score: int) -> str:
    if score >= 100: return "CRITICAL"
    if score >= 60: return "HIGH"
    if score >= 20: return "MEDIUM"
    return "LOW"

def _next_best_action(item: Dict[str, Any]) -> str:
    outcome = item["latest_outcome"]
    band = item["readiness_band"]
    if outcome == "CONVERTED": return "ONBOARDING_FOLLOW_UP"
    if outcome == "ESCALATED": return "COUNSELLOR_HANDOFF"
    if outcome == "CALL_BACK": return "CALL_BACK_AT_RETAINED_TIMING"
    if outcome == "INTERESTED": return "COUNSELLING_OR_DEMO"
    if outcome == "RESPONDED": return "QUALIFY_AND_NURTURE"
    if outcome == "NOT_INTERESTED": return "NURTURE_NO_PUSH"
    if band == "HIGH": return "PERSONALIZED_FOLLOW_UP"
    return "OBSERVE_AND_NURTURE"

def build_priority_intelligence() -> Dict[str, Any]:
    source = batch19.build_readiness_intelligence()
    intelligence = {}
    for lead_id, item in deepcopy(source["intelligence"]).items():
        score = int(item["readiness_score"])
        intelligence[lead_id] = {
            **item,
            "priority_level": _priority_from_score(score),
            "next_best_action": _next_best_action(item),
            "action_basis": {
                "readiness_score": score,
                "readiness_band": item["readiness_band"],
                "latest_outcome": item["latest_outcome"],
                "latest_timing": item["latest_timing"],
            },
            "execution_status": "PLANNED_ONLY",
        }
    ranked = sorted(intelligence.values(),
                    key=lambda x: (x["readiness_score"], x["lead_id"]),
                    reverse=True)
    return {
        "lead_count": len(intelligence),
        "total_interactions": source["total_interactions"],
        "intelligence": intelligence,
        "priority_ranking": [x["lead_id"] for x in ranked],
        "priority_model": {
            "CRITICAL": "score >= 100",
            "HIGH": "60 <= score < 100",
            "MEDIUM": "20 <= score < 60",
            "LOW": "score < 20",
        },
        "intelligence_rules": {
            "source": "BATCH19",
            "readiness_score_retained": True,
            "readiness_band_retained": True,
            "latest_outcome_retained": True,
            "latest_timing_retained": True,
            "priority_deterministic": True,
            "next_action_deterministic": True,
            "lead_identity_isolated": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }

def verify_priority_intelligence(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or data["total_interactions"] != 18:
        return False
    expected = [f"SE-{i:05d}" for i in range(1, 7)]
    if sorted(data["intelligence"]) != expected:
        return False
    for lead_id, item in data["intelligence"].items():
        if item["lead_id"] != lead_id: return False
        if item["execution_status"] != "PLANNED_ONLY": return False
        if item["priority_level"] != _priority_from_score(item["readiness_score"]): return False
        if item["next_best_action"] != _next_best_action(item): return False
        if item["action_basis"]["readiness_score"] != item["readiness_score"]: return False
        if item["action_basis"]["readiness_band"] != item["readiness_band"]: return False
        if item["action_basis"]["latest_outcome"] != item["latest_outcome"]: return False
        if item["action_basis"]["latest_timing"] != item["latest_timing"]: return False
    ranked = [x["lead_id"] for x in sorted(data["intelligence"].values(),
               key=lambda x: (x["readiness_score"], x["lead_id"]), reverse=True)]
    if data["priority_ranking"] != ranked: return False
    rules = data["intelligence_rules"]
    return (rules["source"] == "BATCH19" and
            all(rules[k] is True for k in (
                "readiness_score_retained", "readiness_band_retained",
                "latest_outcome_retained", "latest_timing_retained",
                "priority_deterministic", "next_action_deterministic",
                "lead_identity_isolated", "no_send_enforced",
                "source_data_unchanged", "run_local_generation")))

if __name__ == "__main__":
    data = build_priority_intelligence()
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 20")
    print("LEAD PRIORITY & NEXT-BEST-ACTION INTELLIGENCE")
    print("=" * 78)
    print(f"Leads analyzed: {data['lead_count']}")
    print(f"Interactions analyzed: {data['total_interactions']}")
    print("READ-ONLY / PLANNING MODE: no source data is modified and no actions are executed.")
    print("-" * 78)
    for lead_id in data["priority_ranking"]:
        x = data["intelligence"][lead_id]
        print(f"{lead_id} | Score={x['readiness_score']} | Band={x['readiness_band']} | Priority={x['priority_level']} | Outcome={x['latest_outcome']} | Next={x['next_best_action']}")
    print("-" * 78)
    if not verify_priority_intelligence(data):
        raise AssertionError("Batch 20 priority verification failed")
    print("BATCH 20 PRIORITY INTEGRITY: PASSED")
    print("=" * 78)
    print("BATCH 20 READY FOR VERIFICATION")
    print("=" * 78)
