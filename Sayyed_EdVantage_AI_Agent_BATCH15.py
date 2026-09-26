"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 15
Outcome-Driven Adaptive Follow-Up Engine.

Builds on Batch 14.
Simulation/planning only: no messages are sent and leads.json is never modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH14 as batch14


NEXT_ACTION_MAP = {
    "PENDING": {
        "next_state": "READY_FOR_COUNSELLOR",
        "action": "Review lead and prepare initial counselling contact",
        "timing": "As scheduled",
    },
    "CONTACTED": {
        "next_state": "FOLLOW_UP_REQUIRED",
        "action": "Review contact result and prepare follow-up",
        "timing": "High",
    },
    "RESPONDED": {
        "next_state": "IN_PROGRESS",
        "action": "Continue personalised counselling conversation",
        "timing": "High",
    },
    "INTERESTED": {
        "next_state": "IN_PROGRESS",
        "action": "Advance admission discussion and address remaining blocker",
        "timing": "Immediate",
    },
    "NOT_INTERESTED": {
        "next_state": "COMPLETED",
        "action": "Record outcome and close counselling cycle",
        "timing": "Low",
    },
    "CALL_BACK": {
        "next_state": "FOLLOW_UP_REQUIRED",
        "action": "Prepare callback plan and preserve requested timing",
        "timing": "High",
    },
    "CONVERTED": {
        "next_state": "COMPLETED",
        "action": "Prepare admission completion handoff",
        "timing": "Immediate",
    },
    "ESCALATED": {
        "next_state": "ESCALATED",
        "action": "Prepare counsellor escalation brief",
        "timing": "Immediate",
    },
}


def adapt_action(item: Dict[str, Any], outcome: str) -> Dict[str, Any]:
    """Return an adaptive plan without mutating the supplied item."""
    if outcome not in batch14.OUTCOME_VALUES:
        raise ValueError(f"Unsupported outcome: {outcome}")

    plan = NEXT_ACTION_MAP[outcome]

    return {
        "sequence": item["sequence"],
        "lead_id": item["lead_id"],
        "name": item["name"],
        "priority": item["priority"],
        "channel": item["channel"],
        # Batch 14 uses "state"; an already-adapted Batch 15 item uses
        # "previous_state". Support both representations without mutating input.
        "previous_state": item.get("state", item.get("previous_state")),
        "outcome": outcome,
        "next_state": plan["next_state"],
        "next_action": plan["action"],
        "timing": plan["timing"],
        "send_status": "NOT_SENT",
        "counsellor_ready": True,
    }


def build_adaptive_board() -> Dict[str, Any]:
    source = batch14.build_execution_state_board()
    board = []

    # Use the verified pending state as the initial scenario for every lead.
    for item in source["state_board"]:
        board.append(adapt_action(item, "PENDING"))

    return {
        "total_leads": len(board),
        "adaptive_board": board,
        "rules": {
            "outcome_drives_next_action": True,
            "state_transition_is_explicit": True,
            "lead_identity_isolated": True,
            "priority_retained": True,
            "channel_retained": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
        },
    }


if __name__ == "__main__":
    data = build_adaptive_board()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 15")
    print("=" * 78)
    print(f"Adaptive leads: {data['total_leads']}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("ADAPTIVE MODE: next-action planning only; no messages are sent.")
    print("-" * 78)

    for item in data["adaptive_board"]:
        print(
            f'{item["sequence"]:02d}. {item["lead_id"]:<10} '
            f'{item["name"]:<24} '
            f'Outcome={item["outcome"]:<14} '
            f'NextState={item["next_state"]:<22} '
            f'Action={item["next_action"]}'
        )

    print("=" * 78)
