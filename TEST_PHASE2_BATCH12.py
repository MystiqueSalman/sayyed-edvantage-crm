"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 12
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH12.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<64}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 12 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH12 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")

data = agent.build_daily_action_intelligence()

check(data["total_leads"] == 6, "Real leads loaded (6)")
check(len(data["action_packages"]) == 6, "Six-lead action packages")

counts = data["priority_counts"]
check(
    set(counts.keys()) == {"CRITICAL", "HIGH", "MEDIUM", "NORMAL"},
    "Priority summary coverage"
)
check(sum(counts.values()) == 6, "Priority count integrity")

required = {
    "lead_id", "name", "priority", "action", "channel",
    "timing", "objective", "handoff", "status", "send_status"
}

for item in data["action_packages"]:
    lead_id = item["lead_id"]
    check(required.issubset(item.keys()), f"Complete action package / {lead_id}")
    check(
        item["priority"] in agent.PRIORITY_RANK,
        f"Priority validity / {lead_id}"
    )
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

expected_urgent = [
    item["lead_id"]
    for item in data["action_packages"]
    if item["priority"] in {"CRITICAL", "HIGH"}
]
check(
    data["urgent_leads"] == expected_urgent,
    "Urgent lead identification"
)

# Ensure no duplicate lead identity exists in the action packages.
ids = [item["lead_id"] for item in data["action_packages"]]
check(len(ids) == len(set(ids)), "Cross-lead identity isolation")

# Verify the status vocabulary is explicit and stable.
check(
    set(data["allowed_statuses"])
    == {"READY_FOR_COUNSELLOR", "IN_PROGRESS", "COMPLETED", "ESCALATED"},
    "Action status vocabulary"
)

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 12 VERIFICATION PASSED")
print("=" * 78)
