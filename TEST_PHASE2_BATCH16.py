"""
Verification — Phase 2 / Batch 16
Closed-Loop Outcome Learning Engine.
"""

from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH16 as agent


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH16.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<55}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 16 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)

check("Agent import", hasattr(agent, "build_transition_history"))

data = agent.build_transition_history()
history = data["transition_history"]

check("Real adaptive leads loaded (6)", data["total_leads"] == 6)
check("Six-lead transition history", len(history) == 6)

for record in history:
    lead_id = record["lead_id"]
    outcome = record["outcome"]

    check(f"Previous state retained / {lead_id}", bool(record["previous_state"]))
    check(f"Outcome retained / {lead_id}", bool(outcome))
    check(
        f"Outcome-driven next state / {lead_id}",
        record["next_state"] == agent.OUTCOME_TO_STATE[outcome],
    )
    check(f"Next action generated / {lead_id}", bool(record["next_action"]))
    check(f"Priority retained / {lead_id}", bool(record["priority"]))
    check(f"Channel retained / {lead_id}", bool(record["channel"]))
    check(f"Timing retained / {lead_id}", bool(record["timing"]))
    check(f"Counsellor-ready status / {lead_id}", record["counsellor_ready"] is True)
    check(f"No-send guard / {lead_id}", record["send_status"] == "NOT_SENT")
    check(f"Transition integrity / {lead_id}", agent.verify_transition(record))

ids = [r["lead_id"] for r in history]
check("Lead identity isolation", len(ids) == len(set(ids)))

rules = data["learning_rules"]
check("Outcome drives next state rule", rules["outcome_drives_next_state"] is True)
check("Outcome drives next action rule", rules["outcome_drives_next_action"] is True)
check("Previous state retention rule", rules["previous_state_retained"] is True)
check("Priority retention rule", rules["priority_retained"] is True)
check("Channel retention rule", rules["channel_retained"] is True)
check("Timing retention rule", rules["timing_retained"] is True)
check("No-send enforcement rule", rules["no_send_enforced"] is True)
check("Run-local learning rule", rules["learning_is_run_local"] is True)
check("Data integrity / read-only", rules["source_data_unchanged"] is True)

print()
print("=" * 78)
print("BATCH 16 VERIFICATION PASSED")
print("=" * 78)
