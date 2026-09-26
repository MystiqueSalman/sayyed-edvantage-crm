"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 8
"""

from __future__ import annotations
import json
import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH8.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<46}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 8 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH8 as agent
check(True, "Agent import")

with DATA_FILE.open("r", encoding="utf-8") as f:
    original = f.read()

leads = agent.load_leads()
check(isinstance(leads, dict) and len(leads) == 6, "Real leads loaded (6)")

results = agent.analyze_all()
check(len(results) == 6, "Six-lead analysis")

for result in results:
    memory = result["memory"]
    context = result["context"]

    check(
        memory["lead_id"] == result["lead_id"],
        f'Memory retrieval / {result["lead_id"]}'
    )
    check(
        context["lead_id"] == result["lead_id"]
        and context["name"] == result["name"],
        f'Context isolation / {result["lead_id"]}'
    )
    check(
        isinstance(result["personalized_response"], str)
        and len(result["personalized_response"]) > 20,
        f'Personalized response / {result["lead_id"]}'
    )
    check(
        result["follow_up"]["timing"] in
        {"Immediate", "Within 24 hours", "Within 48–72 hours"},
        f'Follow-up recommendation / {result["lead_id"]}'
    )
    check(
        result["channel_strategy"]["primary"] in {"Call", "WhatsApp"},
        f'Channel strategy / {result["lead_id"]}'
    )

# Cross-lead isolation test: memory/context must belong to the requested lead.
if len(results) >= 2:
    check(
        results[0]["context"]["lead_id"] != results[1]["context"]["lead_id"],
        "Cross-lead memory isolation"
    )

with DATA_FILE.open("r", encoding="utf-8") as f:
    after = f.read()

check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 8 VERIFICATION PASSED")
print("=" * 78)
