"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 18
Longitudinal Lead Intelligence Profile Engine.

Builds on verified Batch 17.

Purpose:
Convert longitudinal interaction history into deterministic,
read-only intelligence profiles for each lead.

Planning/simulation only:
- no messages are sent
- source data is never modified
- Batch-17 history remains unchanged
- profiles are generated in memory
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH17 as batch17


def build_longitudinal_profiles() -> Dict[str, Any]:
    """Build one deterministic intelligence profile for each lead."""
    source = batch17.build_longitudinal_history()
    history = deepcopy(source["history"])
    profiles: Dict[str, Dict[str, Any]] = {}

    for lead_id, records in history.items():
        if not records:
            raise RuntimeError(
                f"Cannot build profile for {lead_id}: empty history"
            )

        ordered = sorted(
            records,
            key=lambda record: record["interaction_number"],
        )

        first = ordered[0]
        latest = ordered[-1]

        outcomes: List[str] = [
            record["outcome"] for record in ordered
        ]
        states: List[str] = [
            record["next_state"] for record in ordered
        ]
        actions: List[str] = [
            record["next_action"] for record in ordered
        ]

        outcome_counts: Dict[str, int] = {}
        for outcome in outcomes:
            outcome_counts[outcome] = (
                outcome_counts.get(outcome, 0) + 1
            )

        profiles[lead_id] = {
            "lead_id": lead_id,
            "interaction_count": len(ordered),
            "first_state": first["previous_state"],
            "current_state": latest["next_state"],
            "outcome_trajectory": outcomes,
            "state_trajectory": states,
            "action_trajectory": actions,
            "outcome_counts": outcome_counts,
            "latest_outcome": latest["outcome"],
            "latest_action": latest["next_action"],
            "latest_priority": latest["priority"],
            "latest_channel": latest["channel"],
            "latest_timing": latest["timing"],
            "send_status": latest["send_status"],
            "counsellor_ready": latest["counsellor_ready"],
            "sequence": latest["sequence"],
            "history_complete": len(ordered) == 3,
        }

    return {
        "lead_count": len(profiles),
        "total_interactions": sum(
            profile["interaction_count"]
            for profile in profiles.values()
        ),
        "profiles": profiles,
        "profile_rules": {
            "history_source": "BATCH17",
            "lead_identity_retained": True,
            "interaction_order_retained": True,
            "outcome_trajectory_retained": True,
            "state_trajectory_retained": True,
            "latest_outcome_retained": True,
            "latest_action_retained": True,
            "priority_retained": True,
            "channel_retained": True,
            "timing_retained": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "profile_generation_run_local": True,
        },
    }


def verify_longitudinal_profiles(data: Dict[str, Any]) -> bool:
    """Verify Batch-18 profile integrity."""
    if data["lead_count"] != 6:
        return False

    if data["total_interactions"] != 18:
        return False

    profiles = data["profiles"]

    if len(profiles) != 6:
        return False

    expected_leads = [
        "SE-00001",
        "SE-00002",
        "SE-00003",
        "SE-00004",
        "SE-00005",
        "SE-00006",
    ]

    if sorted(profiles.keys()) != expected_leads:
        return False

    source_history = batch17.build_longitudinal_history()["history"]

    for lead_id, profile in profiles.items():
        if profile["lead_id"] != lead_id:
            return False

        if profile["interaction_count"] != 3:
            return False

        if len(profile["outcome_trajectory"]) != 3:
            return False

        if len(profile["state_trajectory"]) != 3:
            return False

        if len(profile["action_trajectory"]) != 3:
            return False

        if profile["history_complete"] is not True:
            return False

        if profile["send_status"] != "NOT_SENT":
            return False

        if profile["sequence"] not in range(1, 7):
            return False

        records = source_history[lead_id]
        latest = max(
            records,
            key=lambda record: record["interaction_number"],
        )

        if profile["latest_outcome"] != latest["outcome"]:
            return False

        if profile["current_state"] != latest["next_state"]:
            return False

        if profile["latest_action"] != latest["next_action"]:
            return False

        if profile["latest_priority"] != latest["priority"]:
            return False

        if profile["latest_channel"] != latest["channel"]:
            return False

        if profile["latest_timing"] != latest["timing"]:
            return False

        if profile["counsellor_ready"] != latest["counsellor_ready"]:
            return False

    rules = data["profile_rules"]

    required_rules = [
        "history_source",
        "lead_identity_retained",
        "interaction_order_retained",
        "outcome_trajectory_retained",
        "state_trajectory_retained",
        "latest_outcome_retained",
        "latest_action_retained",
        "priority_retained",
        "channel_retained",
        "timing_retained",
        "no_send_enforced",
        "source_data_unchanged",
        "profile_generation_run_local",
    ]

    for rule in required_rules:
        if rule not in rules:
            return False

    if rules["history_source"] != "BATCH17":
        return False

    for rule in required_rules[1:]:
        if not rules[rule]:
            return False

    return True


if __name__ == "__main__":
    data = build_longitudinal_profiles()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 18")
    print("LONGITUDINAL LEAD INTELLIGENCE PROFILE ENGINE")
    print("=" * 78)

    print(f"Leads profiled: {data['lead_count']}")
    print(f"Interactions consumed: {data['total_interactions']}")
    print("READ-ONLY MODE: source longitudinal history is not modified.")
    print("PLANNING MODE: no messages are sent.")
    print("-" * 78)

    for lead_id, profile in data["profiles"].items():
        print(
            f"{lead_id} | "
            f"Interactions={profile['interaction_count']} | "
            f"State={profile['current_state']} | "
            f"Latest outcome={profile['latest_outcome']} | "
            f"Action={profile['latest_action']}"
        )

    print("-" * 78)

    if verify_longitudinal_profiles(data):
        print("BATCH 18 PROFILE INTEGRITY: PASSED")
    else:
        print("BATCH 18 PROFILE INTEGRITY: FAILED")
        raise AssertionError("Batch 18 profile verification failed")

    print("=" * 78)
    print("BATCH 18 READY FOR VERIFICATION")
    print("=" * 78)
