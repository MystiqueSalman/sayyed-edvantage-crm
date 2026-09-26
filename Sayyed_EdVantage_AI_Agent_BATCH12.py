"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 12
Counsellor Workload & Daily Action Intelligence.

Builds on Batch 11 and produces:
- daily action summary
- priority counts
- urgent lead identification
- counsellor-ready action packages
- safe completion-state vocabulary

No messages are sent and leads.json is never modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH11 as batch11


PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3}
ALLOWED_STATUS = {
    "READY_FOR_COUNSELLOR",
    "IN_PROGRESS",
    "COMPLETED",
    "ESCALATED",
}


def build_daily_action_intelligence() -> Dict[str, Any]:
    queue = batch11.build_action_queue()

    counts = {key: 0 for key in PRIORITY_RANK}
    for item in queue:
        counts[item["priority"]] += 1

    urgent = [
        item["lead_id"]
        for item in queue
        if item["priority"] in {"CRITICAL", "HIGH"}
    ]

    packages = []
    for item in queue:
        packages.append(
            {
                "lead_id": item["lead_id"],
                "name": item["name"],
                "priority": item["priority"],
                "action": item["action"],
                "channel": item["channel"],
                "timing": item["timing"],
                "objective": item["objective"],
                "handoff": item["handoff"],
                "status": "READY_FOR_COUNSELLOR",
                "send_status": "NOT_SENT",
            }
        )

    return {
        "total_leads": len(queue),
        "priority_counts": counts,
        "urgent_leads": urgent,
        "action_packages": packages,
        "allowed_statuses": sorted(ALLOWED_STATUS),
    }


if __name__ == "__main__":
    data = build_daily_action_intelligence()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 12")
    print("=" * 78)
    print(f"Leads loaded: {data['total_leads']}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("EXECUTION MODE: planning only; no messages are sent.")
    print("-" * 78)

    print(
        "Priority counts: "
        + " | ".join(
            f"{key}={data['priority_counts'][key]}"
            for key in PRIORITY_RANK
        )
    )
    print(f"Urgent leads: {', '.join(data['urgent_leads']) or 'None'}")
    print("-" * 78)

    for item in data["action_packages"]:
        print(
            f'{item["lead_id"]:<10} {item["name"]:<24} '
            f'Priority={item["priority"]:<8} '
            f'Status={item["status"]:<22} '
            f'Channel={item["channel"]}'
        )

    print("=" * 78)
