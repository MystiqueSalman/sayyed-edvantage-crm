import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH28 import (
    INTEGRATION_READY,
    INTEGRATION_HANDOFF,
    adapt_delivery_to_agent,
    agent_response_query,
    agent_response_to_dict,
    validate_agent_response_contract,
    build_master_kb_with_agent_integration,
)
from Sayyed_EdVantage_Master_KB_BATCH27 import (
    DELIVERABLE,
    HANDOFF_ONLY,
    deliver_query,
)


passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_agent_integration()

# 1–7: normal verified answer crosses the integration boundary
ds = agent_response_query(kb, "What is the fee for Data Science in India?")
check(ds.integration_status == INTEGRATION_READY,
      "Indian fee should be INTEGRATION_READY")
check(ds.delivery_status == DELIVERABLE,
      "Indian fee must remain DELIVERABLE")
check(ds.response_status == "READY",
      "Indian fee must remain READY")
check(ds.grounded is True,
      "Integrated answer must remain grounded")
check(ds.source_ids,
      "Integrated answer must retain provenance")
check("₹50,000 + GST" in ds.response,
      "Integrated fee response missing")
check(validate_agent_response_contract(ds)["valid"] is True,
      "Normal integration contract validation failed")

# 8–13: safe partial international answer remains usable with handoff
intl = agent_response_query(
    kb,
    "What is the fee for Data Science outside India?"
)
check(intl.integration_status == INTEGRATION_READY,
      "Safe partial international answer should remain READY")
check(intl.completeness_status == "PARTIAL",
      "International answer must remain PARTIAL")
check(intl.human_handoff_required is True,
      "International handoff must be preserved")
check(intl.source_ids,
      "International provenance missing")
check("Indian pricing must not be substituted" in intl.response,
      "International protection missing")
check(validate_agent_response_contract(intl)["valid"] is True,
      "International integration validation failed")

# 14–18: certification remains controlled
cert = agent_response_query(
    kb,
    "Does Data Science provide certification?"
)
check(cert.integration_status == INTEGRATION_READY,
      "Certification answer should be integration-ready")
check(cert.completeness_status == "PARTIAL",
      "Certification must remain PARTIAL")
check(cert.human_handoff_required is True,
      "Certification handoff must be preserved")
check("Certification details" in cert.response,
      "Certification wording missing")
check(validate_agent_response_contract(cert)["valid"] is True,
      "Certification integration validation failed")

# 19–22: Linux inconsistency remains preserved
linux = agent_response_query(kb, "Linux administration duration")
check(linux.integration_status == INTEGRATION_READY,
      "Linux answer should be integration-ready")
check("40" in linux.response and "44" in linux.response,
      "Linux figures must remain visible")
check("documented duration inconsistency" in linux.response.lower(),
      "Linux inconsistency warning missing")
check(linux.warnings,
      "Linux warnings must be preserved")

# 23–27: NO_MATCH becomes handoff-only with no response text
none = agent_response_query(kb, "zzzz completely nonexistent topic")
check(none.integration_status == INTEGRATION_HANDOFF,
      "NO_MATCH must become INTEGRATION_HANDOFF")
check(none.response == "",
      "NO_MATCH must expose no response text")
check(none.human_handoff_required is True,
      "NO_MATCH must require handoff")
check(none.gate_errors,
      "NO_MATCH handoff reason must be preserved")
check(validate_agent_response_contract(none)["valid"] is True,
      "NO_MATCH handoff contract should validate")

# 28–32: unsafe delivery state is contained at the integration boundary
unsafe = deliver_query(kb, "Python programming")
unsafe.safety["execution_enabled"] = True
blocked = adapt_delivery_to_agent(unsafe)
check(blocked.integration_status == INTEGRATION_HANDOFF,
      "Unsafe execution must become integration handoff")
check(blocked.response == "",
      "Unsafe response must not be exposed")
check(blocked.human_handoff_required is True,
      "Unsafe integration must require handoff")
check(blocked.gate_errors,
      "Unsafe integration must retain diagnostics")
check(validate_agent_response_contract(blocked)["valid"] is True,
      "Unsafe handoff contract should validate")

# 33–35: independent action boundaries
for key in (
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    unsafe2 = deliver_query(kb, "Python programming")
    unsafe2.safety[key] = True
    blocked2 = adapt_delivery_to_agent(unsafe2)
    check(blocked2.integration_status == INTEGRATION_HANDOFF,
          f"{key} must prevent integration")

# 36–38: no-invention and provenance
unsafe3 = deliver_query(kb, "Python programming")
unsafe3.safety["no_invention"] = False
blocked3 = adapt_delivery_to_agent(unsafe3)
check(blocked3.integration_status == INTEGRATION_HANDOFF,
      "no_invention=False must prevent integration")
check(blocked3.gate_errors,
      "no-invention diagnostics must be preserved")
check(blocked3.human_handoff_required is True,
      "no-invention violation must require handoff")

unsafe4 = deliver_query(kb, "Python programming")
unsafe4.source_ids = []
blocked4 = adapt_delivery_to_agent(unsafe4)
check(blocked4.integration_status == INTEGRATION_HANDOFF,
      "Missing provenance must prevent integration")

# 39–42: read-only safety contract is always sanitized
check(ds.safety["execution_enabled"] is False,
      "Execution must remain disabled")
check(ds.safety["messaging_enabled"] is False,
      "Messaging must remain disabled")
check(ds.safety["external_actions_enabled"] is False,
      "External actions must remain disabled")
check(ds.safety["crm_writes_enabled"] is False,
      "CRM writes must remain disabled")

# 43–45: serialization is defensive
serialized = agent_response_to_dict(ds)
check(serialized["integration_status"] == INTEGRATION_READY,
      "Serialization integration status mismatch")
serialized["source_ids"].append("MUTATION")
serialized["safety"]["execution_enabled"] = True
check("MUTATION" not in ds.source_ids,
      "Serialization must not mutate provenance")
check(ds.safety["execution_enabled"] is False,
      "Serialization must not mutate safety")

print(f"MASTER KB BATCH 28: {passed}/{total} PASSED")
