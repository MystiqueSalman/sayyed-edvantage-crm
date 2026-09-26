"""
Sayyed EdVantage CRM <-> AI Agent Alignment Verification
SAFE READ-ONLY CHECK.
No writes, POSTs, message sends, or external actions.
"""
from __future__ import annotations
import json
from pathlib import Path
import Sayyed_EdVantage_AI_Agent_BATCH30 as batch30

ROOT = Path.cwd()
DATA_FILE = ROOT / "data" / "leads.json"
EXPECTED_IDS = [f"SE-{i:05d}" for i in range(1, 7)]
TEST_MARKER = "TEST COUNSELLING - CRM PORTAL E2E VERIFICATION"

def check(label, condition):
    print(f"{label:<70}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)

print("=" * 78)
print("SAYYED EDVANTAGE CRM <-> AI AGENT ALIGNMENT VERIFICATION")
print("=" * 78)

check("Shared leads.json exists", DATA_FILE.is_file())
crm = json.loads(DATA_FILE.read_text(encoding="utf-8"))
check("CRM lead store is an object", isinstance(crm, dict))

crm_ids = sorted(str(k) for k in crm.keys())
check("CRM has six Phase-2 test leads", crm_ids == EXPECTED_IDS)

agent = batch30.build_phase2_certificate()
agent_ids = sorted(agent["gate_records"].keys())
check("AI Agent has six Phase-2 test leads", agent_ids == EXPECTED_IDS)
check("CRM and AI Agent Lead IDs match", crm_ids == agent_ids)

se1 = crm["SE-00001"]
se2 = crm["SE-00002"]
se1_history = se1.get("counselling_history", [])
se2_history = se2.get("counselling_history", [])

check("SE-00001 counselling history is a list", isinstance(se1_history, list))
check("SE-00002 counselling history is a list", isinstance(se2_history, list))
check("SE-00001 contains E2E test counselling",
      any(TEST_MARKER in json.dumps(x, ensure_ascii=False) for x in se1_history))
check("SE-00002 does not contain SE-00001 E2E test counselling",
      not any(TEST_MARKER in json.dumps(x, ensure_ascii=False) for x in se2_history))

rules = agent["certificate_rules"]
check("Agent execution disabled", agent["execution_enabled"] is False)
check("Agent messages sent is false", agent["messages_sent"] is False)
check("Agent external actions false", agent["external_actions_executed"] is False)
check("Agent source data modified is false", agent["source_data_modified"] is False)
check("Agent no-send rule", rules["no_send"] is True)
check("CRM verification remains pending",
      agent["crm_verification_status"] == "CRM_PORTAL_VERIFICATION_PENDING")

for lead_id, record in agent["gate_records"].items():
    check(f"{lead_id} authorization pending", record["authorization_state"] == "PENDING")
    check(f"{lead_id} execution disabled", record["execution_authorized"] is False)
    check(f"{lead_id} no-send", record["send_status"] == "NOT_SENT")

print()
print("=" * 78)
print("CRM <-> AI AGENT ALIGNMENT VERIFICATION PASSED")
print("=" * 78)
print("No CRM write, POST, message send, or external action was performed.")
print("=" * 78)
