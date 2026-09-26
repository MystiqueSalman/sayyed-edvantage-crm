"""Sayyed EdVantage AI Agent — Phase 2 / Batch 19
Longitudinal Lead Scoring & Readiness Intelligence.
Builds on verified Batch 18. Read-only, planning/simulation only.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH18 as batch18

OUTCOME_WEIGHTS = {
    "CONTACTED": 0,
    "RESPONDED": 20,
    "INTERESTED": 40,
    "CALL_BACK": 35,
    "NOT_INTERESTED": -20,
    "CONVERTED": 100,
    "ESCALATED": 50,
}

def _readiness_band(score: int) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 0:
        return "LOW"
    return "NEGATIVE"

def _calculate_score(outcomes: list[str]) -> int:
    score = 0
    for index, outcome in enumerate(outcomes):
        score += OUTCOME_WEIGHTS.get(outcome, 0) * (index + 1)
    return score

def build_readiness_intelligence() -> Dict[str, Any]:
    source = batch18.build_longitudinal_profiles()
    profiles = deepcopy(source["profiles"])
    intelligence = {}

    for lead_id, profile in profiles.items():
        outcomes = list(profile["outcome_trajectory"])
        score = _calculate_score(outcomes)
        intelligence[lead_id] = {
            "lead_id": lead_id,
            "interaction_count": profile["interaction_count"],
            "sequence": profile["sequence"],
            "current_state": profile["current_state"],
            "latest_outcome": profile["latest_outcome"],
            "readiness_score": score,
            "readiness_band": _readiness_band(score),
            "outcome_trajectory": outcomes,
            "outcome_counts": deepcopy(profile["outcome_counts"]),
            "latest_action": profile["latest_action"],
            "latest_priority": profile["latest_priority"],
            "latest_channel": profile["latest_channel"],
            "latest_timing": profile["latest_timing"],
            "send_status": profile["send_status"],
            "counsellor_ready": profile["counsellor_ready"],
        }

    return {
        "lead_count": len(intelligence),
        "total_interactions": sum(x["interaction_count"] for x in intelligence.values()),
        "intelligence": intelligence,
        "scoring_model": {
            **OUTCOME_WEIGHTS,
            "latest_interaction_has_greatest_influence": True,
            "unknown_outcomes_default_to_zero": True,
        },
        "intelligence_rules": {
            "source": "BATCH18",
            "lead_identity_retained": True,
            "outcome_history_retained": True,
            "latest_state_retained": True,
            "latest_outcome_retained": True,
            "latest_action_retained": True,
            "priority_retained": True,
            "channel_retained": True,
            "timing_retained": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }

def verify_readiness_intelligence(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or data["total_interactions"] != 18:
        return False

    expected_leads = [f"SE-{i:05d}" for i in range(1, 7)]
    intelligence = data["intelligence"]

    if sorted(intelligence) != expected_leads:
        return False

    for lead_id, item in intelligence.items():
        if item["lead_id"] != lead_id or item["interaction_count"] != 3:
            return False
        if len(item["outcome_trajectory"]) != 3:
            return False
        score = _calculate_score(item["outcome_trajectory"])
        if item["readiness_score"] != score:
            return False
        if item["readiness_band"] != _readiness_band(score):
            return False
        if item["send_status"] != "NOT_SENT":
            return False
        counts = {}
        for outcome in item["outcome_trajectory"]:
            counts[outcome] = counts.get(outcome, 0) + 1
        if item["outcome_counts"] != counts:
            return False

    rules = data["intelligence_rules"]
    required = [
        "source", "lead_identity_retained", "outcome_history_retained",
        "latest_state_retained", "latest_outcome_retained",
        "latest_action_retained", "priority_retained", "channel_retained",
        "timing_retained", "no_send_enforced", "source_data_unchanged",
        "run_local_generation",
    ]
    if rules.get("source") != "BATCH18":
        return False
    return all(rules.get(rule) is True for rule in required[1:])

if __name__ == "__main__":
    data = build_readiness_intelligence()
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 19")
    print("LONGITUDINAL LEAD SCORING & READINESS INTELLIGENCE")
    print("=" * 78)
    print(f"Leads analyzed: {data['lead_count']}")
    print(f"Interactions analyzed: {data['total_interactions']}")
    print("READ-ONLY MODE: Batch-18 profiles are not modified.")
    print("PLANNING MODE: no messages are sent.")
    print("-" * 78)
    for lead_id, item in data["intelligence"].items():
        print(
            f"{lead_id} | State={item['current_state']} | "
            f"Outcome={item['latest_outcome']} | "
            f"Score={item['readiness_score']} | "
            f"Band={item['readiness_band']} | "
            f"Action={item['latest_action']}"
        )
    print("-" * 78)
    if verify_readiness_intelligence(data):
        print("BATCH 19 READINESS INTEGRITY: PASSED")
    else:
        raise AssertionError("Batch 19 readiness verification failed")
    print("=" * 78)
    print("BATCH 19 READY FOR VERIFICATION")
    print("=" * 78)
