"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 16
Closed-Loop Outcome Learning Engine.

Builds on Batch 15.
Simulation/planning only: no messages are sent and leads.json is never modified.

Purpose:
- Convert observed counselling outcomes into verified next-state transitions.
- Preserve lead identity, priority, channel and timing context.
- Maintain an in-memory transition history for the current run.
- Produce learning signals without changing source data.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH15 as batch15


OUTCOME_SEQUENCE = [
    "CONTACTED",
    "RESPONDED",
    "INTERESTED",
    "NOT_INTERESTED",
    "CALL_BACK",
    "CONVERTED",
    "ESCALATED",
]

OUTCOME_TO_STATE = {
    "CONTACTED": "FOLLOW_UP_REQUIRED",
    "RESPONDED": "IN_PROGRESS",
    "INTERESTED": "IN_PROGRESS",
    "NOT_INTERESTED": "COMPLETED",
    "CALL_BACK": "FOLLOW_UP_REQUIRED",
    "CONVERTED": "COMPLETED",
    "ESCALATED": "ESCALATED",
}


def observe_outcome(item: Dict[str, Any], outcome: str) -> Dict[str, Any]:
    """Apply one observed outcome to a Batch-15 adaptive item.

    The input item is never mutated. The returned record is a new dictionary.
    """
    if outcome not in OUTCOME_TO_STATE:
        raise ValueError(f"Unsupported outcome: {outcome}")

    source = deepcopy(item)

    # Batch 15 adaptive records use previous_state.
    # Accept state as well so the transition engine can consume Batch-14 records.
    previous_state = source.get("previous_state", source.get("state"))
    if previous_state is None:
        raise KeyError("previous_state")

    normalized = {
        "sequence": source["sequence"],
        "lead_id": source["lead_id"],
        "name": source["name"],
        "priority": source["priority"],
        "channel": source["channel"],
        "state": previous_state,
    }

    adapted = batch15.adapt_action(normalized, outcome)

    return {
        "lead_id": adapted["lead_id"],
        "name": adapted["name"],
        "previous_state": previous_state,
        "outcome": outcome,
        "next_state": OUTCOME_TO_STATE[outcome],
        "next_action": adapted["next_action"],
        "priority": adapted["priority"],
        "channel": adapted["channel"],
        "timing": adapted["timing"],
        "send_status": "NOT_SENT",
        "counsellor_ready": adapted["counsellor_ready"],
    }


def build_transition_history() -> Dict[str, Any]:
    """Create one in-memory learning/transition record per lead."""
    board = batch15.build_adaptive_board()["adaptive_board"]
    history: List[Dict[str, Any]] = []

    for index, item in enumerate(board):
        outcome = OUTCOME_SEQUENCE[index % len(OUTCOME_SEQUENCE)]
        history.append(observe_outcome(item, outcome))

    return {
        "total_leads": len(history),
        "transition_history": history,
        "learning_rules": {
            "outcome_drives_next_state": True,
            "outcome_drives_next_action": True,
            "previous_state_retained": True,
            "lead_identity_isolated": True,
            "priority_retained": True,
            "channel_retained": True,
            "timing_retained": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "learning_is_run_local": True,
        },
    }


def verify_transition(record: Dict[str, Any]) -> bool:
    """Verify the core closed-loop transition contract."""
    outcome = record["outcome"]

    return (
        record["next_state"] == OUTCOME_TO_STATE[outcome]
        and record["previous_state"] is not None
        and record["lead_id"]
        and record["priority"]
        and record["channel"]
        and record["send_status"] == "NOT_SENT"
        and record["counsellor_ready"] is True
    )


if __name__ == "__main__":
    data = build_transition_history()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 16")
    print("=" * 78)
    print(f"Transition records: {data['total_leads']}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("LEARNING MODE: transition history is in-memory only; no messages are sent.")
    print("-" * 78)

    for record in data["transition_history"]:
        print(
            f'{record["lead_id"]:<10} '
            f'Outcome={record["outcome"]:<15} '
            f'Previous={record["previous_state"]:<24} '
            f'Next={record["next_state"]:<22} '
            f'Priority={record["priority"]:<6} '
            f'Channel={record["channel"]}'
        )

    print("=" * 78)
