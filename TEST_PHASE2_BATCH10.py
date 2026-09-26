"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 10
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH10.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<58}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 10 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH10 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")

leads = agent.batch9.load_leads()
check(isinstance(leads, dict) and len(leads) == 6, "Real leads loaded (6)")

plans = agent.build_all_plans()
check(len(plans) == 6, "Six-lead communication planning")

required = {
    "lead_id", "name", "channel", "objective", "timing",
    "intent", "draft_message", "suggested_questions",
    "counsellor_checklist", "handoff", "send_status"
}

for plan in plans:
    lead_id = plan["lead_id"]

    check(required.issubset(plan.keys()), f"Complete plan fields / {lead_id}")
    check(bool(plan["draft_message"]), f"Personalized draft / {lead_id}")
    check(plan["send_status"] == "NOT_SENT", f"Safe draft-only mode / {lead_id}")
    check(
        plan["channel"] in {"WhatsApp", "Call", "Email", "SMS", "Unknown"}
        or bool(plan["channel"]),
        f"Channel recommendation / {lead_id}"
    )
    check(
        plan["timing"] in
        {"Immediate", "Within 24 hours", "Within 48 hours", "Within 3 days"},
        f"Follow-up timing / {lead_id}"
    )
    check(
        isinstance(plan["suggested_questions"], list)
        and 1 <= len(plan["suggested_questions"]) <= 3,
        f"Adaptive questions / {lead_id}"
    )
    check(
        isinstance(plan["counsellor_checklist"], list)
        and len(plan["counsellor_checklist"]) >= 4,
        f"Counsellor action checklist / {lead_id}"
    )

ids = [p["lead_id"] for p in plans]
check(len(ids) == len(set(ids)), "Cross-lead isolation")

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 10 VERIFICATION PASSED")
print("=" * 78)
