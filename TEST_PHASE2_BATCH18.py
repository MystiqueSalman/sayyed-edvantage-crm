"""
Verification — Phase 2 / Batch 18

Longitudinal Lead Intelligence Profile Engine.
"""

from __future__ import annotations

import py_compile
from copy import deepcopy
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH18 as agent


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH18.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 18 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)

check(
    "Agent import",
    hasattr(agent, "build_longitudinal_profiles"),
)

data = agent.build_longitudinal_profiles()

check("Six leads profiled", data["lead_count"] == 6)
check("Eighteen interactions consumed", data["total_interactions"] == 18)
check("Six profiles generated", len(data["profiles"]) == 6)

expected_leads = [
    "SE-00001",
    "SE-00002",
    "SE-00003",
    "SE-00004",
    "SE-00005",
    "SE-00006",
]

check(
    "Six-lead identity mapping",
    sorted(data["profiles"].keys()) == expected_leads,
)

for lead_id, profile in data["profiles"].items():
    check(
        f"Three-interaction profile / {lead_id}",
        profile["interaction_count"] == 3,
    )

    check(
        f"Outcome trajectory / {lead_id}",
        len(profile["outcome_trajectory"]) == 3,
    )

    check(
        f"State trajectory / {lead_id}",
        len(profile["state_trajectory"]) == 3,
    )

    check(
        f"Action trajectory / {lead_id}",
        len(profile["action_trajectory"]) == 3,
    )

    check(
        f"History complete / {lead_id}",
        profile["history_complete"] is True,
    )

    check(
        f"Lead identity retained / {lead_id}",
        profile["lead_id"] == lead_id,
    )

    check(
        f"Sequence retained / {lead_id}",
        profile["sequence"] in range(1, 7),
    )

    check(
        f"Latest outcome present / {lead_id}",
        bool(profile["latest_outcome"]),
    )

    check(
        f"Current state present / {lead_id}",
        bool(profile["current_state"]),
    )

    check(
        f"Latest action present / {lead_id}",
        bool(profile["latest_action"]),
    )

    check(
        f"Priority retained / {lead_id}",
        bool(profile["latest_priority"]),
    )

    check(
        f"Channel retained / {lead_id}",
        bool(profile["latest_channel"]),
    )

    check(
        f"Timing retained / {lead_id}",
        bool(profile["latest_timing"]),
    )

    check(
        f"No-send guard / {lead_id}",
        profile["send_status"] == "NOT_SENT",
    )

source = agent.batch17.build_longitudinal_history()
source_history = source["history"]

for lead_id, profile in data["profiles"].items():
    records = source_history[lead_id]

    latest = max(
        records,
        key=lambda record: record["interaction_number"],
    )

    check(
        f"Latest outcome mapping / {lead_id}",
        profile["latest_outcome"] == latest["outcome"],
    )

    check(
        f"Current state mapping / {lead_id}",
        profile["current_state"] == latest["next_state"],
    )

    check(
        f"Latest action mapping / {lead_id}",
        profile["latest_action"] == latest["next_action"],
    )

    check(
        f"Priority mapping / {lead_id}",
        profile["latest_priority"] == latest["priority"],
    )

    check(
        f"Channel mapping / {lead_id}",
        profile["latest_channel"] == latest["channel"],
    )

    check(
        f"Timing mapping / {lead_id}",
        profile["latest_timing"] == latest["timing"],
    )

for lead_id, profile in data["profiles"].items():
    trajectory = profile["outcome_trajectory"]
    counts = profile["outcome_counts"]

    reconstructed = {}
    for outcome in trajectory:
        reconstructed[outcome] = (
            reconstructed.get(outcome, 0) + 1
        )

    check(
        f"Outcome counts / {lead_id}",
        counts == reconstructed,
    )

all_profile_ids = []

for profile in data["profiles"].values():
    all_profile_ids.append(profile["lead_id"])

check(
    "Cross-lead identity isolation",
    all_profile_ids == expected_leads,
)

rules = data["profile_rules"]

check(
    "Batch-17 history source rule",
    rules["history_source"] == "BATCH17",
)

check(
    "Lead identity retention rule",
    rules["lead_identity_retained"],
)

check(
    "Interaction order retention rule",
    rules["interaction_order_retained"],
)

check(
    "Outcome trajectory retention rule",
    rules["outcome_trajectory_retained"],
)

check(
    "State trajectory retention rule",
    rules["state_trajectory_retained"],
)

check(
    "Latest outcome retention rule",
    rules["latest_outcome_retained"],
)

check(
    "Latest action retention rule",
    rules["latest_action_retained"],
)

check(
    "Priority retention rule",
    rules["priority_retained"],
)

check(
    "Channel retention rule",
    rules["channel_retained"],
)

check(
    "Timing retention rule",
    rules["timing_retained"],
)

check(
    "No-send enforcement rule",
    rules["no_send_enforced"],
)

check(
    "Source-data immutability rule",
    rules["source_data_unchanged"],
)

check(
    "Run-local profile rule",
    rules["profile_generation_run_local"],
)

first_run = deepcopy(agent.build_longitudinal_profiles())
second_run = deepcopy(agent.build_longitudinal_profiles())

check(
    "Deterministic profile generation",
    first_run == second_run,
)

check(
    "Batch 18 verification function",
    agent.verify_longitudinal_profiles(data),
)

print()
print("=" * 78)
print("BATCH 18 VERIFICATION PASSED")
print("=" * 78)
