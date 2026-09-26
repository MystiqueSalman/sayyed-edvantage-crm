from __future__ import annotations

import json
import py_compile
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
BATCH3 = ROOT / "Sayyed_EdVantage_AI_Agent_BATCH3.py"
BATCH4 = ROOT / "Sayyed_EdVantage_AI_Agent_BATCH4.py"
DATA = ROOT / "data" / "leads.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"{label:<28}: PASSED")


print("=" * 78)
print("PHASE 1 / BATCH 4 — VERIFICATION")
print("=" * 78)

py_compile.compile(str(BATCH4), doraise=True)
check(True, "Python syntax")

before = DATA.read_bytes() if DATA.exists() else None

b4 = load_module(BATCH4, "sayyed_ai_batch4_test")
leads = b4.B3.all_leads()
check(len(leads) > 0, f"Leads checked ({len(leads)})")

results = [b4.analyze_lead(lead) for lead in leads]
check(len(results) == len(leads), "Analysis coverage")

for item in results:
    scoring = item["refined_scoring"]
    priority = item["priority"]
    action = item["next_best_action"]
    objections = item["objection_detection"]
    signals = item["buying_signals"]
    plan = item["ai_action_plan"]

    check(0 <= scoring["score"] <= 100, "Scoring range")
    check(priority["priority"] in {"Critical", "High", "Medium", "Low"}, "Priority engine")
    check(bool(action["action"]) and bool(action["objective"]), "Next best action")
    check(bool(objections["primary_objection"]), "Objection detection")
    check("strength" in signals and "score_adjustment" in signals, "Buying signals")
    check(len(plan["steps"]) >= 4 and bool(plan["headline"]), "AI action plan")

after = DATA.read_bytes() if DATA.exists() else None
check(before == after, "Data integrity / read-only")

print()
print("BATCH 4 VERIFICATION PASSED")
print("=" * 78)
