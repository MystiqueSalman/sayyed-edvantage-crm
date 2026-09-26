"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 14
Execution State & Outcome Tracking.

Builds on Batch 13.
Planning/state-tracking only: no messages are sent and leads.json is never modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH13 as batch13


ALLOWED_STATES = {
    "READY_FOR_COUNSELLOR",
    "IN_PROGRESS",
    "FOLLOW_UP_REQUIRED",
    "COMPLETED",
    "ESCALATED",
    "NOT_SENT",
}

OUTCOME_VALUES = {
    "PENDING",
    "CONTACTED",
    "RESPONDED",
    "INTERESTED",
    "NOT_INTERESTED",
    "CALL_BACK",
    "CONVERTED",
    "ESCALATED",
}

# Batch 14 starts from the verified Batch 13 board.
# No real-world action is performed here.
DEFAULT_OUTCOME = "PENDING"
DEFAULT_STATE = "READY_FOR_COUNSELLOR"


def build_execution_state_board() -> Dict[str, Any]:
    source = batch13.build_execution_board()

    states: List[Dict[str, Any]] = []

    for item in source["board"]:
        states.append(
            {
                "sequence": item["sequence"],
                "lead_id": item["lead_id"],
                "name": item["name"],
                "priority": item["priority"],
                "action": item["action"],
                "channel": item["channel"],
                "timing": item["timing"],
                "objective": item["objective"],
                "handoff": item["handoff"],
                "state": DEFAULT_STATE,
                "outcome": DEFAULT_OUTCOME,
                "send_status": "NOT_SENT",
                "next_state": DEFAULT_STATE,
            }
        )

    return {
        "total_actions": len(states),
        "state_board": states,
        "state_rules": {
            "initial_state_is_counsellor_ready": True,
            "pending_outcome_is_preserved": True,
            "no_send_is_enforced": True,
            "lead_identity_isolated": True,
            "source_board_unchanged": True,
        },
    }


def validate_transition(current_state: str, next_state: str) -> bool:
    """Validate a safe state transition without changing any stored data."""
    if current_state not in ALLOWED_STATES:
        return False
    if next_state not in ALLOWED_STATES:
        return False
    if current_state == "NOT_SENT" and next_state != "NOT_SENT":
        return False
    return True


if __name__ == "__main__":
    data = build_execution_state_board()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 14")
    print("=" * 78)
    print(f"Execution states: {data['total_actions']}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("STATE MODE: tracking only; no messages are sent.")
    print("-" * 78)

    for item in data["state_board"]:
        print(
            f'{item["sequence"]:02d}. {item["lead_id"]:<10} '
            f'{item["name"]:<24} '
            f'Priority={item["priority"]:<8} '
            f'State={item["state"]:<24} '
            f'Outcome={item["outcome"]:<14} '
            f'Send={item["send_status"]}'
        )

    print("=" * 78)
