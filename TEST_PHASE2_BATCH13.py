"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 13
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH13.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<64}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 13 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH13 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")

data = agent.build_execution_board()

check(data["total_actions"] == 6, "Six execution actions")
check(len(data["board"]) == 6, "Six-lead execution board")

required = {
    "sequence", "lead_id", "name", "priority", "action",
    "channel", "timing", "objective", "handoff", "status", "send_status"
}

for item in data["board"]:
    lead_id = item["lead_id"]
    check(required.issubset(item.keys()), f"Complete board fields / {lead_id}")
    check(bool(item["action"]), f"Action retained / {lead_id}")
    check(bool(item["channel"]), f"Channel retained / {lead_id}")
    check(bool(item["timing"]), f"Timing retained / {lead_id}")
    check(
        item["status"] == "READY_FOR_COUNSELLOR",
        f"Counsellor-ready status / {lead_id}"
    )
    check(
        item["send_status"] == "NOT_SENT",
        f"No-send guard / {lead_id}"
    )

sequences = [item["sequence"] for item in data["board"]]
check(sequences == list(range(1, 7)), "Execution sequence integrity")

ids = [item["lead_id"] for item in data["board"]]
check(len(ids) == len(set(ids)), "Cross-lead identity isolation")

priorities = [
    agent.PRIORITY_RANK.get(item["priority"], 99)
    for item in data["board"]
]
check(priorities == sorted(priorities), "Priority-first orchestration")

check(
    data["execution_rules"]["highest_priority_first"] is True,
    "Highest-priority-first rule"
)
check(
    data["execution_rules"]["timing_preserved"] is True,
    "Timing preservation rule"
)
check(
    data["execution_rules"]["lead_identity_isolated"] is True,
    "Lead isolation rule"
)
check(
    data["execution_rules"]["send_status_must_remain_not_sent"] is True,
    "No-send execution rule"
)

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 13 VERIFICATION PASSED")
print("=" * 78)
