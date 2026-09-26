from pathlib import Path
import re

root = Path(__file__).resolve().parent
target = root / "Sayyed_EdVantage_AI_Agent_BATCH17.py"
text = target.read_text(encoding="utf-8")

pattern = re.compile(
    r"def append_interaction\(.*?\n(?=def build_longitudinal_history\(\))",
    re.DOTALL,
)

replacement = r"""def append_interaction(
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


"""

if not pattern.search(text):
    raise SystemExit("Could not find append_interaction() in Batch 17.")

target.write_text(pattern.sub(replacement, text, count=1), encoding="utf-8")
print("Batch 17 append_interaction() repaired.")
print("Continuity now comes from history[-1]['next_state'].")
