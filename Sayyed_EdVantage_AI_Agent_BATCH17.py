"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 17
Longitudinal Multi-Interaction Learning Engine.

Builds on verified Batch 16.
Planning/simulation only:
- no messages are sent
- source leads.json is never modified
- learning records remain in memory for the current run

Purpose:
Track multiple counselling interactions for the same lead and preserve
continuity across interactions without mixing one lead's history with another.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH16 as batch16


# A deterministic, in-memory interaction scenario used only for verification.
# It intentionally exercises different paths through the state machine.
INTERACTION_SCENARIOS = {
    "SE-00001": ["CONTACTED", "RESPONDED", "INTERESTED"],
    "SE-00002": ["CONTACTED", "CALL_BACK", "RESPONDED"],
    "SE-00003": ["CONTACTED", "NOT_INTERESTED", "NOT_INTERESTED"],
    "SE-00004": ["CONTACTED", "RESPONDED", "CALL_BACK"],
    "SE-00005": ["CONTACTED", "INTERESTED", "CONVERTED"],
    "SE-00006": ["CONTACTED", "RESPONDED", "ESCALATED"],
}


def _base_records() -> Dict[str, Dict[str, Any]]:
    """Get Batch-16 records and restore the immutable sequence metadata.

    Batch 16 intentionally returns transition records without the original
    ``sequence`` field, while its ``observe_outcome`` contract consumes that
    field. We therefore recover the sequence from the verified Batch-15
    adaptive board and attach it only to the in-memory Batch-17 working copy.
    Source data is never modified.
    """
    data = batch16.build_transition_history()
    records = {
        item["lead_id"]: deepcopy(item)
        for item in data["transition_history"]
    }

    board = batch16.batch15.build_adaptive_board()["adaptive_board"]
    sequence_by_id = {
        item["lead_id"]: item["sequence"]
        for item in board
    }

    for lead_id, record in records.items():
        record["sequence"] = sequence_by_id[lead_id]

    return records


def append_interaction(
    history: List[Dict[str, Any]],
    current: Dict[str, Any],
    outcome: str,
    interaction_number: int,
) -> Dict[str, Any]:
    # Create one longitudinal interaction with strict state continuity.
    working = deepcopy(current)

    # Recover immutable sequence metadata when Batch 16 omits it.
    if "sequence" not in working:
        board = batch16.batch15.build_adaptive_board()["adaptive_board"]
        sequence_by_id = {
            item["lead_id"]: item["sequence"]
            for item in board
        }
        lead_id = working["lead_id"]
        if lead_id not in sequence_by_id:
            raise KeyError(f"Unknown lead_id for sequence recovery: {lead_id}")
        working["sequence"] = sequence_by_id[lead_id]

    # Interaction #2 starts from #1's resulting state.
    # Interaction #3 starts from #2's resulting state.
    if interaction_number > 1:
        if not history:
            raise RuntimeError(
                f"Missing prior interaction for {working['lead_id']} "
                f"interaction #{interaction_number}"
            )
        working["previous_state"] = history[-1]["next_state"]

    transition = batch16.observe_outcome(working, outcome)

    record = {
        "interaction_number": interaction_number,
        "sequence": working["sequence"],
        "lead_id": transition["lead_id"],
        "name": transition["name"],
        "previous_state": transition["previous_state"],
        "outcome": transition["outcome"],
        "next_state": transition["next_state"],
        "next_action": transition["next_action"],
        "priority": transition["priority"],
        "channel": transition["channel"],
        "timing": transition["timing"],
        "send_status": "NOT_SENT",
        "counsellor_ready": transition["counsellor_ready"],
    }

    history.append(deepcopy(record))
    return record


def build_longitudinal_history() -> Dict[str, Any]:
    """Build three sequential interactions for each of the six leads."""
    bases = _base_records()
    all_history: Dict[str, List[Dict[str, Any]]] = {}

    for lead_id, outcomes in INTERACTION_SCENARIOS.items():
        current = deepcopy(bases[lead_id])
        lead_history: List[Dict[str, Any]] = []

        for number, outcome in enumerate(outcomes, start=1):
            current = append_interaction(
                lead_history,
                current,
                outcome,
                number,
            )

            # The next interaction consumes the prior interaction's transition.
            current = deepcopy(current)

        all_history[lead_id] = lead_history

    return {
        "lead_count": len(all_history),
        "interactions_per_lead": 3,
        "total_interactions": sum(len(v) for v in all_history.values()),
        "history": all_history,
        "learning_rules": {
            "same_lead_history_is_sequential": True,
            "previous_state_links_to_prior_next_state": True,
            "latest_outcome_drives_latest_state": True,
            "latest_outcome_drives_latest_action": True,
            "lead_identity_isolated": True,
            "priority_retained": True,
            "channel_retained": True,
            "timing_retained": True,
            "no_send_enforced": True,
            "source_data_unchanged": True,
            "history_is_run_local": True,
        },
    }


def verify_longitudinal_history(data: Dict[str, Any]) -> bool:
    """Verify continuity and isolation across all interactions."""
    history = data["history"]

    if data["lead_count"] != 6 or data["total_interactions"] != 18:
        return False

    for lead_id, records in history.items():
        if len(records) != 3:
            return False

        for index, record in enumerate(records):
            if record["lead_id"] != lead_id:
                return False

            if record["next_state"] != batch16.OUTCOME_TO_STATE[record["outcome"]]:
                return False

            if index > 0:
                prior = records[index - 1]
                if record["previous_state"] != prior["next_state"]:
                    return False

            if record["send_status"] != "NOT_SENT":
                return False

    return True


if __name__ == "__main__":
    data = build_longitudinal_history()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 17")
    print("=" * 78)
    print(f"Leads tracked: {data['lead_count']}")
    print(f"Interactions tracked: {data['total_interactions']}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("LEARNING MODE: longitudinal history is in-memory only; no messages are sent.")
    print("-" * 78)

    for lead_id, records in data["history"].items():
        print(f"{lead_id} / {records[0]['name']}")
        for record in records:
            print(
                f'  #{record["interaction_number"]} '
                f'{record["previous_state"]} -> {record["outcome"]} '
                f'-> {record["next_state"]} '
                f'Action={record["next_action"]}'
            )

    print("=" * 78)
