"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 14
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH14.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<64}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 14 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH14 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")

data = agent.build_execution_state_board()

check(data["total_actions"] == 6, "Six execution states")
check(len(data["state_board"]) == 6, "Six-lead state board")

required = {
    "sequence", "lead_id", "name", "priority", "action",
    "channel", "timing", "objective", "handoff",
    "state", "outcome", "send_status", "next_state",
}

for item in data["state_board"]:
    lead_id = item["lead_id"]

    check(required.issubset(item.keys()), f"Complete state fields / {lead_id}")
    check(
        item["state"] == "READY_FOR_COUNSELLOR",
        f"Initial state / {lead_id}"
    )
    check(
        item["outcome"] == "PENDING",
        f"Pending outcome / {lead_id}"
    )
    check(
        item["next_state"] == "READY_FOR_COUNSELLOR",
        f"Next state / {lead_id}"
    )
    check(
        item["send_status"] == "NOT_SENT",
        f"No-send guard / {lead_id}"
    )
    check(
        item["state"] in agent.ALLOWED_STATES,
        f"Valid state vocabulary / {lead_id}"
    )
    check(
        item["outcome"] in agent.OUTCOME_VALUES,
        f"Valid outcome vocabulary / {lead_id}"
    )

sequences = [item["sequence"] for item in data["state_board"]]
check(sequences == list(range(1, 7)), "State sequence integrity")

ids = [item["lead_id"] for item in data["state_board"]]
check(len(ids) == len(set(ids)), "Cross-lead identity isolation")

check(
    agent.validate_transition("READY_FOR_COUNSELLOR", "IN_PROGRESS"),
    "Safe forward transition"
)
check(
    agent.validate_transition("IN_PROGRESS", "FOLLOW_UP_REQUIRED"),
    "Safe follow-up transition"
)
check(
    not agent.validate_transition("NOT_SENT", "IN_PROGRESS"),
    "No-send transition guard"
)

check(
    data["state_rules"]["initial_state_is_counsellor_ready"] is True,
    "Initial-state rule"
)
check(
    data["state_rules"]["pending_outcome_is_preserved"] is True,
    "Pending-outcome rule"
)
check(
    data["state_rules"]["no_send_is_enforced"] is True,
    "No-send enforcement rule"
)
check(
    data["state_rules"]["lead_identity_isolated"] is True,
    "Lead-isolation rule"
)
check(
    data["state_rules"]["source_board_unchanged"] is True,
    "Source-board immutability rule"
)

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 14 VERIFICATION PASSED")
print("=" * 78)
