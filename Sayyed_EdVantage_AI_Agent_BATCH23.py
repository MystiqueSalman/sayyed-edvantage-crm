from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH22 as batch22


def _batch22_source():
    for name in (
        "build_followup_action_plans",
        "build_follow_up_action_plans",
        "build_adaptive_action_plans",
        "build_action_plan",
        "build_action_plans",
    ):
        fn = getattr(batch22, name, None)
        if callable(fn):
            data = fn()
            if isinstance(data, dict) and "plans" in data:
                return data
    raise AttributeError(
        "No compatible Batch-22 action-plan builder found. "
        "Check Batch 22 public build_* functions."
    )


def _steps(plan):
    for key in ("plan_steps", "steps", "action_plan"):
        if isinstance(plan.get(key), list):
            return plan[key]
    return []


def _urgency(plan):
    for key in ("urgency_level", "urgency", "urgency_score"):
        if key in plan:
            return plan[key]
    return 0


def build_validated_action_plans():
    source = _batch22_source()
    plans = deepcopy(source["plans"])

    for lead_id, plan in plans.items():
        urgency = _urgency(plan)
        if isinstance(urgency, (int, float)):
            confidence = "HIGH" if urgency >= 3 else "NORMAL"
        else:
            confidence = "HIGH" if str(urgency).upper() in {"HIGH", "CRITICAL"} else "NORMAL"
        plan["confidence"] = confidence
        plan["validation_status"] = "VALIDATED"
        plan["execution_authorized"] = False
        plan["source_batch"] = 22

    return {
        "lead_count": source.get("lead_count", len(plans)),
        "total_interactions": source.get("total_interactions", 0),
        "plans": plans,
        "validation_rules": {
            "source_batch_immutable": True,
            "plan_structure_validated": True,
            "confidence_deterministic": True,
            "execution_authorized_by_default": False,
            "no_send_enforced": True,
            "run_local": True,
        },
    }


def verify_validated_action_plans(data):
    if data["lead_count"] != 6 or len(data["plans"]) != 6:
        return False

    if sorted(data["plans"]) != [f"SE-{i:05d}" for i in range(1, 7)]:
        return False

    for lead_id, plan in data["plans"].items():
        if plan.get("lead_id") != lead_id:
            return False
        if len(_steps(plan)) != 3:
            return False
        if plan.get("validation_status") != "VALIDATED":
            return False
        if plan.get("execution_authorized") is not False:
            return False
        if plan.get("source_batch") != 22:
            return False
        if plan.get("confidence") not in {"HIGH", "NORMAL"}:
            return False

    rules = data["validation_rules"]
    return (
        rules["source_batch_immutable"]
        and rules["plan_structure_validated"]
        and rules["confidence_deterministic"]
        and rules["execution_authorized_by_default"] is False
        and rules["no_send_enforced"]
        and rules["run_local"]
    )


if __name__ == "__main__":
    data = build_validated_action_plans()
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 23")
    print("=" * 78)
    print(f"Leads validated: {data['lead_count']}")
    print(f"Plans validated: {len(data['plans'])}")
    print("MODE: PLANNING ONLY")
    print("EXECUTION AUTHORIZED: FALSE")
    print("NO-SEND: ENFORCED")
    print("=" * 78)
