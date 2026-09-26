"""
Verification — Sayyed EdVantage AI Agent / Phase 2 / Batch 25
"""

from __future__ import annotations

import py_compile
from pathlib import Path

import Sayyed_EdVantage_AI_Agent_BATCH25 as agent

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH25.py"


def check(label: str, condition: bool) -> None:
    print(f"{label:<64}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


print("=" * 78)
print("PHASE 2 / BATCH 25 - VERIFICATION")
print("=" * 78)

py_compile.compile(str(SOURCE), doraise=True)
check("Python syntax", True)
check("Agent import", hasattr(agent, "build_authorization_requests"))

data = agent.build_authorization_requests()

check("Six leads assessed", data["lead_count"] == 6)
check("Six authorization requests generated", len(data["authorization_requests"]) == 6)

for lead_id, item in data["authorization_requests"].items():
    check(f"Lead identity retained / {lead_id}", item["lead_id"] == lead_id)
    check(f"Validated source / {lead_id}", item["validation_status"] == "VALIDATED")
    check(
        f"Execution readiness retained / {lead_id}",
        item["execution_readiness"] == agent.batch24.EXECUTION_READY,
    )
    check(
        f"Authorization pending / {lead_id}",
        item["authorization_request"] == "AUTHORIZATION_PENDING",
    )
    check(
        f"Authorization not granted / {lead_id}",
        item["authorization_granted"] is False,
    )
    check(
        f"Human authorization required / {lead_id}",
        item["authorization_required"] is True,
    )
    check(
        f"No authorization actor / {lead_id}",
        item["authorization_actor"] is None,
    )
    check(
        f"No authorization timestamp / {lead_id}",
        item["authorization_timestamp"] is None,
    )
    check(f"Three-step plan retained / {lead_id}", len(item["steps"]) == 3)
    check(f"No-send guard / {lead_id}", item["send_status"] == "NOT_SENT")
    check(f"Batch-24 source retained / {lead_id}", item["source_batch"] == 24)

rules = data["authorization_rules"]
check("Readiness prerequisite rule", rules["readiness_required"])
check("Human authorization rule", rules["human_authorization_required"])
check(
    "Authorization disabled by default",
    rules["authorization_granted_by_default"] is False,
)
check("No automatic approval rule", rules["no_automatic_approval"])
check("No-send enforcement rule", rules["no_send_enforced"])
check("Source-data immutability rule", rules["source_data_unchanged"])
check("Run-local generation rule", rules["run_local_generation"])
check(
    "Batch 25 verification function",
    agent.verify_authorization_requests(data),
)

print()
print("=" * 78)
print("BATCH 25 VERIFICATION PASSED")
print("=" * 78)
