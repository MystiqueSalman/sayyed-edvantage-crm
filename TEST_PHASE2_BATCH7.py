from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH7.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def passed(label: str) -> None:
    print(f"{label:<46}: PASSED")


def failed(label: str, exc: Exception) -> None:
    print(f"{label:<46}: FAILED")
    print(f"ERROR: {type(exc).__name__}: {exc}")
    raise SystemExit(1)


print("=" * 82)
print("PHASE 2 / BATCH 7 - VERIFICATION")
print("=" * 82)

try:
    ast.parse(AGENT_FILE.read_text(encoding="utf-8"))
    passed("Python syntax")
except Exception as exc:
    failed("Python syntax", exc)

try:
    sys.path.insert(0, str(BASE_DIR))
    import Sayyed_EdVantage_AI_Agent_BATCH7 as module
    passed("Agent import")
except Exception as exc:
    failed("Agent import", exc)

try:
    leads = module.load_leads()
    if len(leads) != 6:
        raise AssertionError(f"expected 6 real leads, found {len(leads)}")
    passed(f"Real leads loaded ({len(leads)})")
except Exception as exc:
    failed("Real leads loaded", exc)

try:
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        lid = module.lead_id(leads[0])

        memory.remember_conversation(lid, "Asked about the course", "WhatsApp")
        memory.record_history(lid, "Counselling completed", "Interested")
        memory.remember_objection(lid, "Fees are higher than expected", "High")
        memory.record_outcome(lid, "Counselling", "Student requested fee discussion")
        memory.record_transition(lid, "New", "Interested", "Positive counselling response")

        summary = memory.summary(lid)

        if summary["conversations"] != 1:
            raise AssertionError("conversation memory not stored")
        if summary["history_events"] != 1:
            raise AssertionError("history not stored")
        if summary["objections"] != 1:
            raise AssertionError("objection memory not stored")
        if summary["outcomes"] != 1:
            raise AssertionError("outcome memory not stored")
        if summary["state_transitions"] != 1:
            raise AssertionError("transition memory not stored")

        reloaded = module.MemoryStore(Path(tmp) / "memory.json")
        if reloaded.summary(lid) != summary:
            raise AssertionError("memory did not persist after reload")

    passed("Persistent conversation memory")
except Exception as exc:
    failed("Persistent conversation memory", exc)

try:
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        lid = module.lead_id(leads[0])
        memory.record_history(lid, "Call completed", "New", "Initial qualification")
        memory.record_history(lid, "Counselling completed", "Interested", "Positive response")
        record = memory.get(lid)
        if len(record["history"]) != 2:
            raise AssertionError("history accumulation failed")
    passed("Lead history accumulation")
except Exception as exc:
    failed("Lead history accumulation", exc)

try:
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        lid = module.lead_id(leads[0])
        memory.remember_objection(lid, "Fees are high", "High")
        memory.remember_objection(lid, "Needs parent approval", "Medium")
        record = memory.get(lid)
        if len(record["objections"]) != 2:
            raise AssertionError("multiple objections not retained")
        if record["objections"][-1]["objection"] != "Needs parent approval":
            raise AssertionError("latest objection not retained")
    passed("Previous-objection memory")
except Exception as exc:
    failed("Previous-objection memory", exc)

try:
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        lid = module.lead_id(leads[0])
        memory.record_outcome(lid, "Call", "No answer")
        memory.record_outcome(lid, "Counselling", "Requested callback")
        record = memory.get(lid)
        if len(record["outcomes"]) != 2:
            raise AssertionError("outcomes not accumulated")
    passed("Counselling outcome memory")
except Exception as exc:
    failed("Counselling outcome memory", exc)

try:
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        lid = module.lead_id(leads[0])
        memory.record_transition(lid, "New", "Contacted", "First contact")
        memory.record_transition(lid, "Contacted", "Interested", "Positive counselling")
        probe = dict(leads[0])
        probe["lead_id"] = lid
        probe["stage"] = "Interested"
        transition = module.state_transition_intelligence(probe, memory)
        if transition["transition_count"] != 2:
            raise AssertionError("transition count incorrect")
        if transition["previous_recorded_stage"] != "Interested":
            raise AssertionError("latest state not detected")
    passed("Lead-state transition intelligence")
except Exception as exc:
    failed("Lead-state transition intelligence", exc)

try:
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        lid = module.lead_id(leads[0])
        probe = dict(leads[0])
        probe["lead_id"] = lid
        probe["stage"] = "Interested"

        memory.remember_objection(lid, "Fees are too high", "High")
        result = module.adaptive_next_best_action(probe, memory)

        if result["priority"] != "High":
            raise AssertionError("objection did not raise action priority")
        if "fee" not in result["action"].lower() and "payment" not in result["action"].lower():
            raise AssertionError("fee-specific adaptive action not selected")
    passed("Adaptive next-best-action engine")
except Exception as exc:
    failed("Adaptive next-best-action engine", exc)

try:
    before = DATA_FILE.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        memory = module.MemoryStore(Path(tmp) / "memory.json")
        results = [module.analyze_lead(lead, memory) for lead in leads]
        if len(results) != 6:
            raise AssertionError("analysis count is not 6")
    after = DATA_FILE.read_bytes()
    if before != after:
        raise AssertionError("leads.json was modified")
    passed("Six-lead integration / read-only")
except Exception as exc:
    failed("Six-lead integration / read-only", exc)

print()
print("BATCH 7 VERIFICATION PASSED")
print("=" * 82)
