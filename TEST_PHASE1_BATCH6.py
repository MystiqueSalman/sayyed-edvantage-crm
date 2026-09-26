from __future__ import annotations

import ast
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
AGENT_FILE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH6.py"
DATA_FILE = BASE_DIR / "data" / "leads.json"


def passed(label: str) -> None:
    print(f"{label:<42}: PASSED")


def failed(label: str, exc: Exception) -> None:
    print(f"{label:<42}: FAILED")
    print(f"ERROR: {type(exc).__name__}: {exc}")
    raise SystemExit(1)


print("=" * 78)
print("PHASE 1 / BATCH 6 - VERIFICATION")
print("=" * 78)

try:
    ast.parse(AGENT_FILE.read_text(encoding="utf-8"))
    passed("Python syntax")
except Exception as exc:
    failed("Python syntax", exc)

try:
    sys.path.insert(0, str(BASE_DIR))
    import Sayyed_EdVantage_AI_Agent_BATCH6 as module
    passed("Agent import")
except Exception as exc:
    failed("Agent import", exc)

try:
    leads = module.load_leads()
    if len(leads) != 6:
        raise AssertionError(f"expected 6 leads, found {len(leads)}")
    passed(f"Leads checked ({len(leads)})")
except Exception as exc:
    failed("Leads checked", exc)

try:
    results = [module.analyze_lead(lead) for lead in leads]
    if len(results) != 6:
        raise AssertionError("analysis count does not equal 6")
    passed("Lead analysis")
except Exception as exc:
    failed("Lead analysis", exc)

try:
    required = (
        "risk_conversion",
        "conversion_blocker_map",
        "workflow_intelligence",
        "escalation",
        "human_handoff",
    )
    for result in results:
        missing = [key for key in required if key not in result]
        if missing:
            raise AssertionError(f"missing keys: {missing}")
    passed("Batch-6 intelligence fields")
except Exception as exc:
    failed("Batch-6 intelligence fields", exc)

try:
    for result in results:
        risk = float(result["risk_conversion"])
        if not 0 <= risk <= 100:
            raise AssertionError("risk outside 0-100")
        if result["escalation"]["level"] not in {"None", "Medium", "High"}:
            raise AssertionError("invalid escalation level")
    passed("Risk / escalation engine")
except Exception as exc:
    failed("Risk / escalation engine", exc)

try:
    before = DATA_FILE.read_bytes()
    module.analyze_all()
    after = DATA_FILE.read_bytes()
    if before != after:
        raise AssertionError("leads.json was modified")
    passed("Data integrity / read-only")
except Exception as exc:
    failed("Data integrity / read-only", exc)

print()
print("BATCH 6 VERIFICATION PASSED")
print("=" * 78)
print()
print("Sample output:")

for result in results:
    print(
        f'{result["lead_id"]:<10} '
        f'{result["name"]:<24} '
        f'Risk={result["risk_conversion"]:<3} '
        f'Escalation={result["escalation"]["level"]}'
    )
