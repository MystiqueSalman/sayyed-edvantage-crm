from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH20 as batch20


def _strategy_for_action(item: Dict[str, Any]) -> str:
    action = item["next_best_action"]
    if action == "ONBOARDING_FOLLOW_UP":
        return "ONBOARDING"
    if action == "COUNSELLOR_HANDOFF":
        return "COUNSELLOR_ESCALATION"
    if action == "CALL_BACK_AT_RETAINED_TIMING":
        return "TIMING_PRESERVED_CALLBACK"
    if action == "COUNSELLING_OR_DEMO":
        return "COUNSELLING_DEMO"
    if action == "QUALIFY_AND_NURTURE":
        return "QUALIFICATION_NURTURE"
    if action == "NURTURE_NO_PUSH":
        return "LOW_PRESSURE_NURTURE"
    if action == "PERSONALIZED_FOLLOW_UP":
        return "PERSONALIZED_FOLLOW_UP"
    return "OBSERVE_AND_NURTURE"


def _urgency_for_priority(priority: str) -> int:
    return {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }[priority]


def build_adaptive_followup_intelligence() -> Dict[str, Any]:
    source = batch20.build_priority_intelligence()
    profiles = deepcopy(source["intelligence"])
    intelligence: Dict[str, Dict[str, Any]] = {}

    for lead_id, item in profiles.items():
        strategy = _strategy_for_action(item)
        urgency = _urgency_for_priority(item["priority_level"])

        intelligence[lead_id] = {
            **item,
            "followup_strategy": strategy,
            "urgency_level": urgency,
            "decision_basis": {
                "priority_level": item["priority_level"],
                "next_best_action": item["next_best_action"],
                "latest_outcome": item["latest_outcome"],
                "latest_timing": item["latest_timing"],
                "readiness_band": item["readiness_band"],
            },
            "execution_status": "PLANNED_ONLY",
        }

    ranked = sorted(
        intelligence.values(),
        key=lambda x: (x["urgency_level"], x["readiness_score"], x["lead_id"]),
        reverse=True,
    )

    return {
        "lead_count": len(intelligence),
        "total_interactions": source["total_interactions"],
        "intelligence": intelligence,
        "followup_ranking": [x["lead_id"] for x in ranked],
        "strategy_model": {
            "ONBOARDING": "Converted lead follow-up",
            "COUNSELLOR_ESCALATION": "Escalated lead handoff planning",
            "TIMING_PRESERVED_CALLBACK": "Callback using retained timing",
            "COUNSELLING_DEMO": "Interested lead counselling/demo path",
            "QUALIFICATION_NURTURE": "Responded lead qualification/nurture",
            "LOW_PRESSURE_NURTURE": "Not-interested low-pressure nurture",
            "PERSONALIZED_FOLLOW_UP": "High-readiness personalized follow-up",
            "OBSERVE_AND_NURTURE": "Default observation/nurture",
        },
        "intelligence_rules": {
            "source": "BATCH20",
            "priority_retained": True,
            "next_best_action_retained": True,
            "latest_outcome_retained": True,
            "latest_timing_retained": True,
            "readiness_band_retained": True,
            "strategy_deterministic": True,
            "urgency_deterministic": True,
            "lead_identity_isolated": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def verify_adaptive_followup_intelligence(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or data["total_interactions"] != 18:
        return False

    expected_leads = [f"SE-{i:05d}" for i in range(1, 7)]
    intelligence = data["intelligence"]

    if sorted(intelligence) != expected_leads:
        return False

    for lead_id, item in intelligence.items():
        if item["lead_id"] != lead_id:
            return False
        if item["execution_status"] != "PLANNED_ONLY":
            return False
        if item["followup_strategy"] != _strategy_for_action(item):
            return False
        if item["urgency_level"] != _urgency_for_priority(item["priority_level"]):
            return False

        basis = item["decision_basis"]
        if basis["priority_level"] != item["priority_level"]:
            return False
        if basis["next_best_action"] != item["next_best_action"]:
            return False
        if basis["latest_outcome"] != item["latest_outcome"]:
            return False
        if basis["latest_timing"] != item["latest_timing"]:
            return False
        if basis["readiness_band"] != item["readiness_band"]:
            return False

    expected_rank = [
        x["lead_id"]
        for x in sorted(
            intelligence.values(),
            key=lambda x: (x["urgency_level"], x["readiness_score"], x["lead_id"]),
            reverse=True,
        )
    ]
    if data["followup_ranking"] != expected_rank:
        return False

    rules = data["intelligence_rules"]
    if rules["source"] != "BATCH20":
        return False

    required_true = [
        "priority_retained",
        "next_best_action_retained",
        "latest_outcome_retained",
        "latest_timing_retained",
        "readiness_band_retained",
        "strategy_deterministic",
        "urgency_deterministic",
        "lead_identity_isolated",
        "no_send_enforced",
        "source_data_unchanged",
        "run_local_generation",
    ]
    return all(rules[key] is True for key in required_true)


if __name__ == "__main__":
    data = build_adaptive_followup_intelligence()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 21")
    print("ADAPTIVE FOLLOW-UP STRATEGY INTELLIGENCE")
    print("=" * 78)
    print(f"Leads analyzed: {data['lead_count']}")
    print(f"Interactions retained: {data['total_interactions']}")
    print("READ-ONLY / PLANNING MODE: no source data is modified.")
    print("NO-SEND MODE: no external message or action is executed.")
    print("-" * 78)

    for lead_id in data["followup_ranking"]:
        x = data["intelligence"][lead_id]
        print(
            f"{lead_id} | Priority={x['priority_level']} | "
            f"Urgency={x['urgency_level']} | "
            f"Outcome={x['latest_outcome']} | "
            f"Strategy={x['followup_strategy']} | "
            f"Action={x['next_best_action']}"
        )

    print("-" * 78)
    if not verify_adaptive_followup_intelligence(data):
        raise AssertionError("Batch 21 adaptive follow-up verification failed")

    print("BATCH 21 ADAPTIVE FOLLOW-UP INTEGRITY: PASSED")
    print("=" * 78)
    print("BATCH 21 READY FOR VERIFICATION")
    print("=" * 78)
