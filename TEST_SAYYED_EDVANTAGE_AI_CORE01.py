import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE01 import (
    RUNTIME_READY, RUNTIME_HANDOFF, RUNTIME_BLOCKED,
    create_session, run_agent_turn, agent_runtime_query,
    session_to_dict, runtime_result_to_dict,
    validate_session_state, validate_runtime_result, build_agent_runtime,
)

passed = total = 0
def check(condition, label):
    global passed, total
    total += 1
    if not condition: raise AssertionError(label)
    passed += 1

kb = build_agent_runtime()

state = create_session("TEST-SESSION-001")
check(state.session_id == "TEST-SESSION-001", "Session ID mismatch")
check(state.turn_count == 0, "New session must have zero turns")
check(state.turns == [], "New session must have no turns")
check(validate_session_state(state)["valid"], "New session validation failed")
check(state.safety["execution_enabled"] is False, "Execution must be disabled")
check(state.safety["crm_writes_enabled"] is False, "CRM writes must be disabled")
check(state.safety["no_invention"] is True, "No-invention must be enabled")

result = run_agent_turn(kb, state, "What is the fee for Data Science in India?")
check(result.runtime_status == RUNTIME_READY, "Verified answer should be runtime-ready")
check(result.integration_status == "INTEGRATION_READY", "Integration status mismatch")
check("₹50,000 + GST" in result.response, "Verified fee missing")
check(result.source_ids, "Runtime must retain provenance")
check(state.turn_count == 1, "Session turn count not incremented")

check(state.turns[0].user_message == "What is the fee for Data Science in India?", "Turn message not stored")
check(state.turns[0].source_ids == result.source_ids, "Turn provenance mismatch")
check("SE-DS-001" in state.active_course_ids, "Active course not tracked")
check(state.active_intent == result.intent, "Active intent not tracked")
check(validate_session_state(state)["valid"], "Session validation failed after turn")

intl_state = create_session("TEST-SESSION-002")
intl = run_agent_turn(kb, intl_state, "What is the fee for Data Science outside India?")
check(intl.runtime_status == RUNTIME_READY, "Safe partial answer should be runtime-ready")
check(intl.human_handoff_required is True, "International handoff must be retained")
check(intl.source_ids, "International provenance missing")
check("Indian pricing must not be substituted" in intl.response, "International protection missing")
check(intl_state.handoff_required is True, "Session handoff state not retained")
check(validate_runtime_result(intl)["valid"], "International runtime result invalid")

none = agent_runtime_query(kb, "zzzz completely nonexistent topic", session_id="TEST-SESSION-003")
check(none.runtime_status == RUNTIME_HANDOFF, "No-match must enter runtime handoff")
check(none.response == "", "No-match must not expose response")
check(none.human_handoff_required is True, "No-match must require handoff")
check(none.errors, "No-match must preserve diagnostic errors")
check(validate_runtime_result(none)["valid"], "No-match runtime result invalid")

empty_state = create_session("TEST-SESSION-004")
empty = run_agent_turn(kb, empty_state, "   ")
check(empty.runtime_status == RUNTIME_BLOCKED, "Empty input must be blocked")
check(empty.response == "", "Blocked input must not expose response")
check(empty.human_handoff_required is True, "Blocked input must require handoff")
check(empty.errors, "Blocked input must have an error")
check(validate_runtime_result(empty)["valid"], "Blocked input runtime result invalid")

for key in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled"):
    check(result.safety[key] is False, f"Runtime safety failed: {key}")
check(result.safety["no_invention"] is True, "Runtime no-invention failed")

sd = session_to_dict(state)
rd = runtime_result_to_dict(result)
check(sd["turn_count"] == 1, "Session serialization turn count mismatch")
check(rd["runtime_status"] == RUNTIME_READY, "Result serialization status mismatch")
sd["active_course_ids"].append("MUTATION")
rd["source_ids"].append("MUTATION")
rd["safety"]["execution_enabled"] = True
check("MUTATION" not in state.active_course_ids, "Session serialization mutated state")
check("MUTATION" not in result.source_ids, "Result serialization mutated provenance")
check(result.safety["execution_enabled"] is False, "Result serialization mutated safety")

a = create_session("DETERMINISTIC-001")
b = create_session("DETERMINISTIC-001")
check(a.session_id == b.session_id, "Explicit session IDs must be deterministic")
check(a.turn_count == b.turn_count == 0, "New explicit sessions must start identically")
check(validate_session_state(a)["valid"], "Explicit session validation failed")

print(f"AI CORE 01: {passed}/{total} PASSED")
