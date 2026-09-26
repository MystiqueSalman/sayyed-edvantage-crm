"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 15
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH15.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<68}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 15 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH15 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")

data = agent.build_adaptive_board()

check(data["total_leads"] == 6, "Six adaptive leads")
check(len(data["adaptive_board"]) == 6, "Six-lead adaptive board")

required = {
    "sequence", "lead_id", "name", "priority", "channel",
    "previous_state", "outcome", "next_state", "next_action",
    "timing", "send_status", "counsellor_ready",
}

for item in data["adaptive_board"]:
    lead_id = item["lead_id"]
    check(required.issubset(item.keys()), f"Complete adaptive fields / {lead_id}")
    check(item["previous_state"] == "READY_FOR_COUNSELLOR",
          f"Previous state retained / {lead_id}")
    check(item["outcome"] == "PENDING",
          f"Pending outcome retained / {lead_id}")
    check(item["next_state"] == "READY_FOR_COUNSELLOR",
          f"Pending next state / {lead_id}")
    check(bool(item["next_action"]),
          f"Next action generated / {lead_id}")
    check(bool(item["timing"]),
          f"Timing generated / {lead_id}")
    check(item["send_status"] == "NOT_SENT",
          f"No-send guard / {lead_id}")
    check(item["counsellor_ready"] is True,
          f"Counsellor-ready status / {lead_id}")

sequences = [x["sequence"] for x in data["adaptive_board"]]
check(sequences == list(range(1, 7)), "Adaptive sequence integrity")

ids = [x["lead_id"] for x in data["adaptive_board"]]
check(len(ids) == len(set(ids)), "Cross-lead identity isolation")

# Verify representative outcome-driven transitions.
sample = data["adaptive_board"][0]

cases = {
    "CONTACTED": "FOLLOW_UP_REQUIRED",
    "RESPONDED": "IN_PROGRESS",
    "INTERESTED": "IN_PROGRESS",
    "NOT_INTERESTED": "COMPLETED",
    "CALL_BACK": "FOLLOW_UP_REQUIRED",
    "CONVERTED": "COMPLETED",
    "ESCALATED": "ESCALATED",
}

for outcome, expected_state in cases.items():
    adapted = agent.adapt_action(sample, outcome)
    check(
        adapted["next_state"] == expected_state,
        f"Outcome transition / {outcome}"
    )
    check(
        adapted["send_status"] == "NOT_SENT",
        f"No-send preserved / {outcome}"
    )

check(data["rules"]["outcome_drives_next_action"] is True,
      "Outcome-driven action rule")
check(data["rules"]["state_transition_is_explicit"] is True,
      "Explicit state-transition rule")
check(data["rules"]["lead_identity_isolated"] is True,
      "Lead-isolation rule")
check(data["rules"]["priority_retained"] is True,
      "Priority-retention rule")
check(data["rules"]["channel_retained"] is True,
      "Channel-retention rule")
check(data["rules"]["no_send_enforced"] is True,
      "No-send enforcement rule")
check(data["rules"]["source_data_unchanged"] is True,
      "Source-data immutability rule")

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 15 VERIFICATION PASSED")
print("=" * 78)
