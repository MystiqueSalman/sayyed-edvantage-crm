"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 11
Counsellor Action Queue & Priority Orchestration.

Builds on Batch 10 communication plans and creates a safe, read-only
execution queue for counsellors.

Nothing is sent, scheduled externally, or written to leads.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH10 as batch10


def _priority(plan: Dict[str, Any]) -> str:
    level = str(plan.get("handoff", {}).get("level", "")).strip()
    timing = str(plan.get("timing", "")).strip()

    if level == "Immediate" or timing == "Immediate":
        return "CRITICAL"
    if level in {"High", "Senior"} or timing == "Within 24 hours":
        return "HIGH"
    if timing == "Within 48 hours":
        return "MEDIUM"
    return "NORMAL"


def _action(plan: Dict[str, Any]) -> str:
    handoff = plan.get("handoff", {})
    if handoff.get("handoff_required"):
        return "Senior counsellor review"
    if plan.get("objective", "").startswith("Resolve"):
        return "Contact and resolve objection"
    return "Initial/next-step contact"


def build_action_queue() -> List[Dict[str, Any]]:
    plans = batch10.build_all_plans()
    queue: List[Dict[str, Any]] = []

    for plan in plans:
        queue.append(
            {
                "lead_id": plan["lead_id"],
                "name": plan["name"],
                "priority": _priority(plan),
                "action": _action(plan),
                "channel": plan["channel"],
                "timing": plan["timing"],
                "objective": plan["objective"],
                "handoff": plan["handoff"],
                "draft_ready": bool(plan["draft_message"]),
                "status": "READY_FOR_COUNSELLOR",
                "send_status": "NOT_SENT",
            }
        )

    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3}
    queue.sort(key=lambda item: (rank[item["priority"]], item["lead_id"]))
    return queue


def get_lead_action(lead_id: str) -> Dict[str, Any]:
    for item in build_action_queue():
        if item["lead_id"] == lead_id:
            return item
    raise KeyError(f"Unknown lead_id: {lead_id}")


if __name__ == "__main__":
    queue = build_action_queue()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 11")
    print("=" * 78)
    print(f"Leads loaded: {len(queue)}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("EXECUTION MODE: counsellor-ready queue only; no messages are sent.")
    print("-" * 78)

    for item in queue:
        print(
            f'{item["lead_id"]:<10} {item["name"]:<24} '
            f'Priority={item["priority"]:<8} '
            f'Action={item["action"]:<31} '
            f'Channel={item["channel"]}'
        )

    print("=" * 78)
