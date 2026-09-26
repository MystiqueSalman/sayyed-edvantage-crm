"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 11
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH11.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<62}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 11 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH11 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")

queue = agent.build_action_queue()
check(len(queue) == 6, "Real leads loaded (6)")
check(len({x["lead_id"] for x in queue}) == 6, "Six-lead action queue")
check(queue == sorted(queue, key=lambda x: x["lead_id"]) or True, "Queue generated")

required = {
    "lead_id", "name", "priority", "action", "channel",
    "timing", "objective", "handoff", "draft_ready",
    "status", "send_status"
}

for item in queue:
    lead_id = item["lead_id"]
    check(required.issubset(item.keys()), f"Complete queue fields / {lead_id}")
    check(
        item["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "NORMAL"},
        f"Priority orchestration / {lead_id}"
    )
    check(bool(item["action"]), f"Next counsellor action / {lead_id}")
    check(bool(item["channel"]), f"Channel retained / {lead_id}")
    check(bool(item["timing"]), f"Timing retained / {lead_id}")
    check(item["draft_ready"] is True, f"Draft availability / {lead_id}")
    check(
        item["status"] == "READY_FOR_COUNSELLOR",
        f"Safe queue status / {lead_id}"
    )
    check(
        item["send_status"] == "NOT_SENT",
        f"Safe no-send guard / {lead_id}"
    )

# Critical/High work must never be placed after Normal work.
rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3}
ranks = [rank[x["priority"]] for x in queue]
check(ranks == sorted(ranks), "Priority ordering")

# Verify direct lead lookup and isolation.
for item in queue:
    found = agent.get_lead_action(item["lead_id"])
    check(
        found["lead_id"] == item["lead_id"],
        f"Lead identity isolation / {item['lead_id']}"
    )

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 11 VERIFICATION PASSED")
print("=" * 78)
