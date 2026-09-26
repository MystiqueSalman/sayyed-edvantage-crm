
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from Sayyed_EdVantage_PHASE4_LIVE_AGENT_API import *

passed = failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print("PASS:", name)
    else:
        failed += 1; print("FAIL:", name)

def turn(status="LIVE_TURN_READY", mode="RESPOND", ready=True, **kw):
    d = dict(
        status=status, mode=mode, session_id="S1", lead_id="SE-00001",
        course_ids=["SE-DS-001"], intent="program_information",
        response_text="Verified response.", response_ready=ready,
        evidence=[{"source_id":"KB-1"}], provenance=["MASTER_KB"],
        prohibited_claims=["No guaranteed outcomes."],
        conflicts=[], errors=[], human_handoff=False,
        message_send_authorized=False, message_sent=False,
        crm_write_authorized=False, crm_write_occurred=False,
        external_action_authorized=False, external_action_occurred=False,
        executor_invoked=False
    )
    d.update(kw)
    return d

# Ready
r = run_live_agent_api(turn())
check("ready status", r.status == API_READY)
check("ready mode", r.mode == API_RESPOND)
check("ready response", r.response_ready and r.response_text == "Verified response.")
check("session preserved", r.session_id == "S1")
check("lead preserved", r.lead_id == "SE-00001")
check("course preserved", r.course_ids == ["SE-DS-001"])
check("intent preserved", r.intent == "program_information")
check("evidence preserved", r.evidence[0]["source_id"] == "KB-1")
check("provenance preserved", r.provenance == ["MASTER_KB"])
check("ready validation", validate_live_agent_api_result(r) == [])

# Clarification
r = run_live_agent_api(turn("LIVE_TURN_CLARIFICATION", "CLARIFY", False))
check("clarification status", r.status == API_CLARIFICATION)
check("clarification mode", r.mode == API_CLARIFY)
check("clarification not ready", not r.response_ready)

# Review
r = run_live_agent_api(turn("LIVE_TURN_REVIEW", "HUMAN_REVIEW", False, human_handoff=True))
check("review status", r.status == API_REVIEW)
check("review mode", r.mode == API_HUMAN_REVIEW)
check("review handoff", r.human_handoff)
check("review not ready", not r.response_ready)

# Blocked
r = run_live_agent_api(turn("LIVE_TURN_BLOCKED", "BLOCK", False))
check("blocked status", r.status == API_BLOCKED)
check("blocked mode", r.mode == API_BLOCK)
check("blocked not ready", not r.response_ready)

# Unknown
r = run_live_agent_api(turn("LIVE_TURN_UNKNOWN", "OBTAIN_STATE", False))
check("unknown status", r.status == API_UNKNOWN)
check("unknown mode", r.mode == API_OBTAIN_STATE)
check("unknown not ready", not r.response_ready)
check("unknown response blank", r.response_text == "")

# Malformed state fail closed
r = run_live_agent_api({"status":"LIVE_TURN_READY"})
check("malformed state blocks", r.status == API_BLOCKED)
check("malformed state not ready", not r.response_ready)
check("malformed state has error", bool(r.errors))

# Unsafe upstream flags fail closed
for flag in [
    "message_send_authorized", "message_sent",
    "crm_write_authorized", "crm_write_occurred",
    "external_action_authorized", "external_action_occurred",
    "executor_invoked",
]:
    r = run_live_agent_api(turn(**{flag: True}))
    check(f"unsafe {flag} blocks", r.status == API_BLOCKED)
    check(f"unsafe {flag} not ready", not r.response_ready)

# Defensive copies
source = turn()
r = run_live_agent_api(source)
source["course_ids"].append("SE-PY-001")
source["evidence"].append({"source_id":"MUTATION"})
check("course defensive copy", r.course_ids == ["SE-DS-001"])
check("evidence defensive copy", len(r.evidence) == 1)

# Serialization
r = run_live_agent_api(turn())
d = live_agent_api_result_to_dict(r)
check("serialization dict", isinstance(d, dict))
check("serialized validation", validate_serialized_live_agent_api_result(d) == [])
d["message_sent"] = True
check("serialized safety", validate_serialized_live_agent_api_result(d) != [])

# Unknown combination fail closed
r = run_live_agent_api(turn("LIVE_TURN_READY", "WRONG_MODE", True))
check("status-mode mismatch blocks", r.status == API_BLOCKED)
check("status-mode mismatch not ready", not r.response_ready)

print(f"\nPHASE 4 LIVE AGENT API TEST RESULT: {'ALL PASSED' if failed == 0 else 'FAILED'}")
print("PASSED:", passed)
print("FAILED:", failed)
sys.exit(0 if failed == 0 else 1)
