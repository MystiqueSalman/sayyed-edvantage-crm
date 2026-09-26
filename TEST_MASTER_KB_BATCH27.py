import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH27 import (
    DELIVERABLE,
    HANDOFF_ONLY,
    create_delivery_envelope,
    deliver_query,
    delivery_envelope_to_dict,
    validate_delivery_envelope,
    build_master_kb_with_delivery_contract,
)
from Sayyed_EdVantage_Master_KB_BATCH26 import (
    BLOCKED,
    FINALIZED,
    finalize_query,
)

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_delivery_contract()

# 1–6: verified Indian fee is a normal deliverable
ds = deliver_query(kb, "What is the fee for Data Science in India?")
check(ds.delivery_status == DELIVERABLE, "Indian fee should be DELIVERABLE")
check(ds.finalization_status == FINALIZED, "Indian fee must be FINALIZED")
check(ds.response_status == "READY", "Indian fee must be READY")
check(ds.grounded is True, "Indian fee must remain grounded")
check(ds.source_ids, "Indian fee must retain provenance")
check("₹50,000 + GST" in ds.answer, "Indian fee missing")

# 7–11: partial international answer remains deliverable with handoff
intl = deliver_query(kb, "What is the fee for Data Science outside India?")
check(intl.delivery_status == DELIVERABLE,
      "Safe partial international answer should be deliverable")
check(intl.completeness_status == "PARTIAL",
      "International answer must remain PARTIAL")
check(intl.human_handoff_required is True,
      "International handoff must be retained")
check(intl.source_ids, "International provenance must remain")
check("Indian pricing must not be substituted" in intl.answer,
      "International pricing protection missing")

# 12–15: certification remains safe and controlled
cert = deliver_query(kb, "Does Data Science provide certification?")
check(cert.delivery_status == DELIVERABLE,
      "Safe certification-unknown answer should be deliverable")
check(cert.completeness_status == "PARTIAL",
      "Certification must remain PARTIAL")
check(cert.human_handoff_required is True,
      "Certification must retain handoff")
check("Certification details" in cert.answer,
      "Certification wording missing")

# 16–19: documented inconsistency remains visible
linux = deliver_query(kb, "Linux administration duration")
check(linux.delivery_status == DELIVERABLE,
      "Linux duration should be deliverable")
check("40" in linux.answer and "44" in linux.answer,
      "Linux figures must remain visible")
check("documented duration inconsistency" in linux.answer.lower(),
      "Linux warning missing")
check(linux.warnings, "Linux warnings must be retained")

# 20–23: no-match is handoff-only and exposes no final answer
none = deliver_query(kb, "zzzz completely nonexistent topic")
check(none.delivery_status == HANDOFF_ONLY,
      "NO_MATCH must be HANDOFF_ONLY")
check(none.answer == "",
      "NO_MATCH handoff must not expose final answer text")
check(none.human_handoff_required is True,
      "NO_MATCH must require handoff")
check(none.gate_errors,
      "NO_MATCH handoff should expose gate errors")

# 24–27: serialization and validation
check(validate_delivery_envelope(ds)["valid"] is True,
      "DELIVERABLE validation failed")
serialized = delivery_envelope_to_dict(ds)
check(serialized["delivery_status"] == DELIVERABLE,
      "Serialization delivery status mismatch")
check(serialized["source_ids"] == ds.source_ids,
      "Serialization provenance mismatch")
check(serialized["safety"]["no_invention"] is True,
      "Serialization no-invention mismatch")

# 28–32: unsafe execution is converted to handoff-only
unsafe = finalize_query(kb, "Python programming")
unsafe.safety["execution_enabled"] = True
blocked = create_delivery_envelope(unsafe)
check(blocked.delivery_status == HANDOFF_ONLY,
      "Unsafe execution must become HANDOFF_ONLY")
check(blocked.answer == "",
      "Unsafe answer must not be exposed")
check(blocked.human_handoff_required is True,
      "Unsafe answer must require handoff")
check(blocked.gate_errors,
      "Unsafe answer must expose gate errors")
check(validate_delivery_envelope(blocked)["valid"] is True,
      "Unsafe HANDOFF_ONLY envelope should validate")

# 33–35: each action boundary independently blocks delivery
for key in (
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    unsafe2 = finalize_query(kb, "Python programming")
    unsafe2.safety[key] = True
    blocked2 = create_delivery_envelope(unsafe2)
    check(blocked2.delivery_status == HANDOFF_ONLY,
          f"{key} must prevent normal delivery")

# 36–38: no-invention and provenance
unsafe3 = finalize_query(kb, "Python programming")
unsafe3.safety["no_invention"] = False
blocked3 = create_delivery_envelope(unsafe3)
check(blocked3.delivery_status == HANDOFF_ONLY,
      "no_invention=False must prevent delivery")
check(blocked3.gate_errors,
      "no_invention gate error must be retained")
check(blocked3.human_handoff_required is True,
      "no-invention violation must require handoff")

unsafe4 = finalize_query(kb, "Python programming")
unsafe4.source_ids = []
blocked4 = create_delivery_envelope(unsafe4)
check(blocked4.delivery_status == HANDOFF_ONLY,
      "Missing provenance must prevent delivery")

# 39–42: contract invariants on a normal deliverable
check(ds.gate_errors == [], "Normal deliverable must have no gate errors")
check(ds.safety["execution_enabled"] is False,
      "Execution safety invariant failed")
check(ds.safety["messaging_enabled"] is False,
      "Messaging safety invariant failed")
check(ds.safety["external_actions_enabled"] is False,
      "External action safety invariant failed")

# 43–45: defensive-copy behavior
copy_a = delivery_envelope_to_dict(ds)
copy_a["source_ids"].append("MUTATION")
copy_a["safety"]["execution_enabled"] = True
check("MUTATION" not in ds.source_ids,
      "Serialization must not mutate source IDs")
check(ds.safety["execution_enabled"] is False,
      "Serialization must not mutate safety")
check(validate_delivery_envelope(ds)["valid"] is True,
      "Original deliverable must remain valid")

print(f"MASTER KB BATCH 27: {passed}/{total} PASSED")
