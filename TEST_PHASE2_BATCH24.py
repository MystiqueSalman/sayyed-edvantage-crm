"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 24
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import Sayyed_EdVantage_AI_Agent_BATCH24 as agent

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH24.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<64}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 24 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_execution_readiness"))

data = agent.build_execution_readiness()

check("Six leads assessed", data["lead_count"] == 6)
check("Six readiness records generated", len(data["readiness"]) == 6)

for lead_id, item in data["readiness"].items():
    check(
        f"Lead identity retained / {lead_id}",
        item["lead_id"] == lead_id,
    )
    check(
        f"Validated source / {lead_id}",
        item["validation_status"] == "VALIDATED",
    )
    check(
        f"Three-step plan retained / {lead_id}",
        len(item["steps"]) == 3,
    )
    check(
        f"Readiness deterministic / {lead_id}",
        item["execution_readiness"] == "READY_FOR_AUTHORIZATION",
    )
    check(
        f"Human authorization gate / {lead_id}",
        item["authorization_gate"] == "HUMAN_AUTHORIZATION_REQUIRED",
    )
    check(
        f"Execution disabled / {lead_id}",
        item["execution_authorized"] is False,
    )
    check(
        f"No-send guard / {lead_id}",
        item["send_status"] == "NOT_SENT",
    )
    check(
        f"Batch-23 source retained / {lead_id}",
        item["source_batch"] == 23,
    )
    check(
        f"Confidence retained / {lead_id}",
        item["confidence"] in {"HIGH", "NORMAL"},
    )

rules = data["execution_rules"]
check("Validated-plan prerequisite rule", rules["validated_plan_required"])
check("Human authorization rule", rules["human_authorization_required"])
check(
    "Execution disabled by default",
    rules["execution_authorized_by_default"] is False,
)
check("No-send enforcement rule", rules["no_send_enforced"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("Run-local generation rule", rules["run_local_generation"])
check(
    "Batch 24 verification function",
    agent.verify_execution_readiness(data),
)

print()
print("=" * 78)
print("BATCH 24 VERIFICATION PASSED")
print("=" * 78)
