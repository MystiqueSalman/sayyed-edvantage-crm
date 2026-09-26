"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 9
"""

from __future__ import annotations
import py_compile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH9.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"{message:<52}: PASSED")


print("=" * 78)
print("PHASE 2 / BATCH 9 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(AGENT_FILE), doraise=True)
check(True, "Python syntax")

sys.path.insert(0, str(BASE_DIR))
import Sayyed_EdVantage_AI_Agent_BATCH9 as agent
check(True, "Agent import")

original = DATA_FILE.read_text(encoding="utf-8")
leads = agent.load_leads()
check(isinstance(leads, dict) and len(leads) == 6, "Real leads loaded (6)")

results = agent.analyze_all()
check(len(results) == 6, "Six-lead analysis")

for r in results:
    lead_id = r["lead_id"]
    check(bool(lead_id), f"Lead identity / {lead_id}")
    check(
        r["objection_intelligence"]["category"] in
        {"Admission / Conversion Blocker", "Previous Objection", "None"},
        f"Objection detection / {lead_id}"
    )
    check(
        isinstance(r["objection_response"]["response"], str)
        and len(r["objection_response"]["response"]) > 20,
        f"Objection response / {lead_id}"
    )
    check(
        isinstance(r["adaptive_questions"], list)
        and 1 <= len(r["adaptive_questions"]) <= 3,
        f"Adaptive questions / {lead_id}"
    )
    check(
        r["refined_intent"]["confidence"] in {"High", "Medium", "Low"},
        f"Intent refinement / {lead_id}"
    )
    conv = r["refined_conversion"]
    check(
        0 <= conv["refined_score"] <= 100
        and conv["conversion_band"] in {"High", "Medium", "Low"},
        f"Conversion refinement / {lead_id}"
    )
    check(
        isinstance(r["counsellor_talking_points"], list)
        and len(r["counsellor_talking_points"]) >= 3,
        f"Counsellor talking points / {lead_id}"
    )
    check(
        r["handoff"]["level"] in {"Immediate", "Priority", "Standard"},
        f"Safe handoff recommendation / {lead_id}"
    )

# Explicit cross-lead isolation.
ids = [r["lead_id"] for r in results]
check(len(ids) == len(set(ids)), "Lead identity isolation")

after = DATA_FILE.read_text(encoding="utf-8")
check(original == after, "Data integrity / read-only")

print()
print("=" * 78)
print("BATCH 9 VERIFICATION PASSED")
print("=" * 78)
