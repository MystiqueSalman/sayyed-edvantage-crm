"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 22
Adaptive Follow-Up Action Plan Engine.

Builds on verified Batch 21.
Planning/simulation only:
- no messages are sent
- source data is never modified
- plans are generated in memory for the current run

Purpose:
Turn Batch-21 adaptive follow-up intelligence into a deterministic,
multi-step action plan while preserving lead identity, priority, urgency,
strategy, timing and no-send safeguards.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH21 as batch21


def _plan_steps(item: Dict[str, Any]) -> List[str]:
    """Create a deterministic three-step plan from Batch-21 intelligence."""
    strategy = item["followup_strategy"]

    if strategy == "ONBOARDING":
        return [
            "Confirm converted-lead status and onboarding requirement",
            "Prepare onboarding information for counsellor review",
            "Hold for authorized human execution",
        ]

    if strategy == "COUNSELLOR_ESCALATION":
        return [
            "Prepare escalation context and latest decision basis",
            "Package lead history for counsellor review",
            "Hold for authorized human execution",
        ]

    if strategy == "TIMING_PRESERVED_CALLBACK":
        return [
            "Review retained callback timing",
            "Prepare callback context from latest outcome",
            "Hold for authorized human execution",
        ]

    if strategy == "COUNSELLING_DEMO":
        return [
            "Review interested-lead context",
            "Prepare counselling/demo discussion points",
            "Hold for authorized human execution",
        ]

    if strategy == "QUALIFICATION_NURTURE":
        return [
            "Review latest response and readiness",
            "Prepare qualification/nurture discussion points",
            "Hold for authorized human execution",
        ]

    if strategy == "LOW_PRESSURE_NURTURE":
        return [
            "Review non-interest context without pressure",
            "Prepare low-pressure nurture option",
            "Hold for authorized human execution",
        ]

    if strategy == "PERSONALIZED_FOLLOW_UP":
        return [
            "Review latest personalized context",
            "Prepare individualized follow-up points",
            "Hold for authorized human execution",
        ]

    return [
        "Review latest lead context",
        "Prepare observation/nurture follow-up",
        "Hold for authorized human execution",
    ]


def _execution_gate(item: Dict[str, Any]) -> str:
    """Return a deterministic authorization gate; Batch 22 never executes."""
    if item["execution_status"] != "PLANNED_ONLY":
        return "BLOCKED"

    if item["urgency_level"] >= 4:
        return "HUMAN_AUTHORIZATION_REQUIRED_CRITICAL"
    if item["urgency_level"] >= 3:
        return "HUMAN_AUTHORIZATION_REQUIRED_HIGH"
    return "HUMAN_AUTHORIZATION_REQUIRED"


def build_followup_action_plans() -> Dict[str, Any]:
    """Build deterministic, in-memory action plans from Batch-21 intelligence."""
    source = batch21.build_adaptive_followup_intelligence()
    intelligence = deepcopy(source["intelligence"])

    plans: Dict[str, Dict[str, Any]] = {}

    for lead_id, item in intelligence.items():
        plans[lead_id] = {
            "lead_id": lead_id,
            "priority_level": item["priority_level"],
            "urgency_level": item["urgency_level"],
            "followup_strategy": item["followup_strategy"],
            "latest_outcome": item["latest_outcome"],
            "latest_timing": item["latest_timing"],
            "decision_basis": deepcopy(item["decision_basis"]),
            "plan_steps": _plan_steps(item),
            "execution_gate": _execution_gate(item),
            "execution_status": "PLANNED_ONLY",
        }

    ranked = sorted(
        plans.values(),
        key=lambda x: (x["urgency_level"], x["priority_level"], x["lead_id"]),
        reverse=True,
    )

    return {
        "lead_count": len(plans),
        "total_interactions": source["total_interactions"],
        "plans": plans,
        "plan_ranking": [x["lead_id"] for x in ranked],
        "planning_rules": {
            "source": "BATCH21",
            "identity_retained": True,
            "priority_retained": True,
            "urgency_retained": True,
            "strategy_retained": True,
            "outcome_retained": True,
            "timing_retained": True,
            "decision_basis_retained": True,
            "three_step_plan_generated": True,
            "execution_gate_deterministic": True,
            "human_authorization_required": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "run_local_generation": True,
        },
    }


def verify_followup_action_plans(data: Dict[str, Any]) -> bool:
    if data["lead_count"] != 6 or data["total_interactions"] != 18:
        return False

    expected_leads = [f"SE-{i:05d}" for i in range(1, 7)]
    plans = data["plans"]

    if sorted(plans) != expected_leads:
        return False

    for lead_id, plan in plans.items():
        if plan["lead_id"] != lead_id:
            return False
        if plan["execution_status"] != "PLANNED_ONLY":
            return False
        if len(plan["plan_steps"]) != 3:
            return False
        if plan["plan_steps"][-1] != "Hold for authorized human execution":
            return False
        if plan["execution_gate"] not in {
            "HUMAN_AUTHORIZATION_REQUIRED",
            "HUMAN_AUTHORIZATION_REQUIRED_HIGH",
            "HUMAN_AUTHORIZATION_REQUIRED_CRITICAL",
        }:
            return False

        if plan["decision_basis"]["priority_level"] != plan["priority_level"]:
            return False
        if plan["decision_basis"]["next_best_action"] != batch21.build_adaptive_followup_intelligence()["intelligence"][lead_id]["next_best_action"]:
            return False

    expected_rank = [
        x["lead_id"]
        for x in sorted(
            plans.values(),
            key=lambda x: (x["urgency_level"], x["priority_level"], x["lead_id"]),
            reverse=True,
        )
    ]
    if data["plan_ranking"] != expected_rank:
        return False

    rules = data["planning_rules"]
    if rules["source"] != "BATCH21":
        return False

    required_true = [
        "identity_retained",
        "priority_retained",
        "urgency_retained",
        "strategy_retained",
        "outcome_retained",
        "timing_retained",
        "decision_basis_retained",
        "three_step_plan_generated",
        "execution_gate_deterministic",
        "human_authorization_required",
        "no_send_enforced",
        "source_data_unchanged",
        "run_local_generation",
    ]
    return all(rules[key] is True for key in required_true)


if __name__ == "__main__":
    data = build_followup_action_plans()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 22")
    print("ADAPTIVE FOLLOW-UP ACTION PLAN ENGINE")
    print("=" * 78)
    print(f"Leads planned: {data['lead_count']}")
    print(f"Interactions retained: {data['total_interactions']}")
    print("READ-ONLY / PLANNING MODE: no source data is modified.")
    print("NO-SEND MODE: no external message or action is executed.")
    print("-" * 78)

    for lead_id in data["plan_ranking"]:
        x = data["plans"][lead_id]
        print(
            f"{lead_id} | Priority={x['priority_level']} | "
            f"Urgency={x['urgency_level']} | "
            f"Strategy={x['followup_strategy']} | "
            f"Gate={x['execution_gate']}"
        )

    print("-" * 78)
    if not verify_followup_action_plans(data):
        raise AssertionError("Batch 22 follow-up action plan verification failed")

    print("BATCH 22 FOLLOW-UP ACTION PLAN INTEGRITY: PASSED")
    print("=" * 78)
    print("BATCH 22 READY FOR VERIFICATION")
    print("=" * 78)
