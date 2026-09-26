"""
Verification — Phase 2 / Batch 17
Longitudinal Multi-Interaction Learning Engine.
"""

from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH17 as agent


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH17.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<60}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 17 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_longitudinal_history"))

data = agent.build_longitudinal_history()
history = data["history"]

check("Six leads tracked", data["lead_count"] == 6)
check("Eighteen interactions generated", data["total_interactions"] == 18)
check(
    "Unique six-lead sequence mapping",
    sorted({records[0]["sequence"] for records in history.values()}) == list(range(1, 7)),
)
check("Three interactions per lead", data["interactions_per_lead"] == 3)

for lead_id, records in history.items():
    check(f"Three-interaction history / {lead_id}", len(records) == 3)

    for number, record in enumerate(records, start=1):
        check(
            f"Interaction numbering / {lead_id} / #{number}",
            record["interaction_number"] == number,
        )
        check(
            f"Lead identity retained / {lead_id} / #{number}",
            record["lead_id"] == lead_id,
        )
        check(
            f"Sequence retained / {lead_id} / #{number}",
            record["sequence"] in range(1, 7),
        )
        check(
            f"Outcome retained / {lead_id} / #{number}",
            bool(record["outcome"]),
        )
        check(
            f"Outcome-driven state / {lead_id} / #{number}",
            record["next_state"] == agent.batch16.OUTCOME_TO_STATE[record["outcome"]],
        )
        check(
            f"Next action generated / {lead_id} / #{number}",
            bool(record["next_action"]),
        )
        check(
            f"Priority retained / {lead_id} / #{number}",
            bool(record["priority"]),
        )
        check(
            f"Channel retained / {lead_id} / #{number}",
            bool(record["channel"]),
        )
        check(
            f"Timing retained / {lead_id} / #{number}",
            bool(record["timing"]),
        )
        check(
            f"No-send guard / {lead_id} / #{number}",
            record["send_status"] == "NOT_SENT",
        )

    check(
        f"Sequential state continuity / {lead_id}",
        records[1]["previous_state"] == records[0]["next_state"]
        and records[2]["previous_state"] == records[1]["next_state"],
    )

# Cross-lead isolation: no record may carry another lead's identity.
all_ids = []
for records in history.values():
    all_ids.extend(record["lead_id"] for record in records)

check("Cross-lead identity isolation", all_ids == [
    "SE-00001", "SE-00001", "SE-00001",
    "SE-00002", "SE-00002", "SE-00002",
    "SE-00003", "SE-00003", "SE-00003",
    "SE-00004", "SE-00004", "SE-00004",
    "SE-00005", "SE-00005", "SE-00005",
    "SE-00006", "SE-00006", "SE-00006",
])

rules = data["learning_rules"]
check("Same-lead sequential history rule", rules["same_lead_history_is_sequential"])
check("Previous-state continuity rule", rules["previous_state_links_to_prior_next_state"])
check("Latest outcome drives state rule", rules["latest_outcome_drives_latest_state"])
check("Latest outcome drives action rule", rules["latest_outcome_drives_latest_action"])
check("Priority retention rule", rules["priority_retained"])
check("Channel retention rule", rules["channel_retained"])
check("Timing retention rule", rules["timing_retained"])
check("No-send enforcement rule", rules["no_send_enforced"])
check("Run-local history rule", rules["history_is_run_local"])
check("Data integrity / read-only", rules["source_data_unchanged"])

check("Longitudinal history integrity", agent.verify_longitudinal_history(data))

print()
print("=" * 78)
print("BATCH 17 VERIFICATION PASSED")
print("=" * 78)
