"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 13
Counsellor Execution Board & Action Sequencing.

Builds on Batch 12.
Planning only: no messages are sent and leads.json is never modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH12 as batch12


PRIORITY_RANK = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "NORMAL": 3,
}

EXECUTION_ORDER = {
    "Immediate": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
}


def build_execution_board() -> Dict[str, Any]:
    intelligence = batch12.build_daily_action_intelligence()
    packages = intelligence["action_packages"]

    board: List[Dict[str, Any]] = []

    for position, item in enumerate(
        sorted(
            packages,
            key=lambda x: (
                PRIORITY_RANK.get(x["priority"], 99),
                EXECUTION_ORDER.get(x["timing"], 99),
                x["lead_id"],
            ),
        ),
        start=1,
    ):
        board.append(
            {
                "sequence": position,
                "lead_id": item["lead_id"],
                "name": item["name"],
                "priority": item["priority"],
                "action": item["action"],
                "channel": item["channel"],
                "timing": item["timing"],
                "objective": item["objective"],
                "handoff": item["handoff"],
                "status": item["status"],
                "send_status": item["send_status"],
            }
        )

    return {
        "total_actions": len(board),
        "board": board,
        "execution_rules": {
            "highest_priority_first": True,
            "timing_preserved": True,
            "lead_identity_isolated": True,
            "send_status_must_remain_not_sent": True,
        },
    }


if __name__ == "__main__":
    data = build_execution_board()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 13")
    print("=" * 78)
    print(f"Execution actions: {data['total_actions']}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("EXECUTION MODE: counsellor planning board only; no messages are sent.")
    print("-" * 78)

    for item in data["board"]:
        print(
            f'{item["sequence"]:02d}. {item["lead_id"]:<10} '
            f'{item["name"]:<24} '
            f'Priority={item["priority"]:<8} '
            f'Timing={item["timing"]:<10} '
            f'Channel={item["channel"]:<10} '
            f'Status={item["status"]}'
        )

    print("=" * 78)
