import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE02 import (
    CONTEXT_READY, CONTEXT_EMPTY, CONTEXT_HANDOFF,
    create_conversation_context, context_from_session,
    update_conversation_context, validate_conversation_context,
    build_contextual_query, run_contextual_turn, contextual_query,
    context_to_dict, contextual_result_to_dict,
    validate_contextual_result, build_conversation_memory_layer,
)
from Sayyed_EdVantage_AI_CORE01 import create_session, run_agent_turn, RUNTIME_READY, RUNTIME_HANDOFF

passed = total = 0
def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1

kb = build_conversation_memory_layer()

# 1–8: empty context foundation
state = create_session("CTX-001")
ctx = create_conversation_context(state.session_id)
check(ctx.session_id == "CTX-001", "Context session ID mismatch")
check(ctx.turn_count == 0, "New context must have zero turns")
check(ctx.context_status == CONTEXT_EMPTY, "New context must be empty")
check(ctx.active_course_ids == [], "New context courses must be empty")
check(ctx.active_intent == "", "New context intent must be empty")
check(ctx.recent_user_messages == [], "New context messages must be empty")
check(ctx.source_ids == [], "New context sources must be empty")
check(validate_conversation_context(ctx)["valid"], "Empty context validation failed")

# 9–16: first turn populates structured context
first = run_contextual_turn(
    kb, state, ctx, "What is the fee for Data Science in India?"
)
check(first.runtime_result.runtime_status == RUNTIME_READY,
      "First turn should be runtime-ready")
check(first.context_used is False, "First turn should not use prior context")
check(first.context.turn_count == 1, "Context turn count not incremented")
check("SE-DS-001" in first.context.active_course_ids,
      "Data Science not stored in context")
check(first.context.active_intent,
      "Active intent not stored")
check(first.context.recent_user_messages[-1].startswith("What is the fee"),
      "User message not stored")
check(first.context.source_ids,
      "Provenance not stored in context")
check(first.context.context_status == CONTEXT_READY,
      "Context should be ready after first turn")

# 17–24: follow-up query explicitly receives prior context
ctx2 = first.context
state2 = state
second = run_contextual_turn(
    kb, state2, ctx2, "And what about certification?"
)
check(second.context_used is True, "Follow-up must use context")
check("Prior active course context: SE-DS-001" in second.effective_query,
      "Course context missing from effective query")
check("Prior active intent:" in second.effective_query,
      "Intent context missing from effective query")
check("And what about certification?" in second.effective_query,
      "Original follow-up message missing")
check(second.context.turn_count == 2,
      "Follow-up did not increment context")
check(len(second.context.recent_user_messages) == 2,
      "Recent message history incorrect")
check(second.context.source_ids,
      "Follow-up context lost provenance")
check(validate_contextual_result(second)["valid"],
      "Follow-up contextual result invalid")

# 25–30: context and session isolation
state_b = create_session("CTX-002")
ctx_b = create_conversation_context(state_b.session_id)
other = run_contextual_turn(kb, state_b, ctx_b, "Tell me about Python")
check(other.context.session_id == "CTX-002", "Second session ID mismatch")
check("SE-PY-001" in other.context.active_course_ids,
      "Python context missing")
check("SE-DS-001" not in other.context.active_course_ids,
      "Course context leaked between sessions")
check(other.context.turn_count == 1,
      "Second session turn count incorrect")
check(ctx2.session_id == "CTX-001",
      "First context session changed")
check(validate_conversation_context(other.context)["valid"],
      "Second context invalid")

# 31–35: context snapshot from an existing Agent Core session
snapshot_state = create_session("CTX-SNAPSHOT")
r = run_agent_turn(kb, snapshot_state, "Python programming")
snap = context_from_session(snapshot_state)
check(snap.session_id == "CTX-SNAPSHOT", "Snapshot ID mismatch")
check(snap.turn_count == 1, "Snapshot turn count mismatch")
check("SE-PY-001" in snap.active_course_ids,
      "Snapshot course missing")
check(snap.recent_user_messages, "Snapshot message missing")
check(snap.source_ids, "Snapshot provenance missing")

# 36–40: handoff/no-match remains controlled
handoff_state = create_session("CTX-HANDOFF")
handoff_ctx = create_conversation_context("CTX-HANDOFF")
nm = run_contextual_turn(
    kb, handoff_state, handoff_ctx, "zzzz completely nonexistent topic"
)
check(nm.runtime_result.runtime_status == RUNTIME_HANDOFF,
      "No-match should remain runtime handoff")
check(nm.runtime_result.response == "",
      "No-match response must remain empty")
check(nm.runtime_result.human_handoff_required is True,
      "No-match must require handoff")
check(nm.context.context_status == CONTEXT_HANDOFF,
      "Context should record handoff status")
check(validate_contextual_result(nm)["valid"],
      "No-match contextual result invalid")

# 41–44: invalid session/context mismatch is blocked
bad_state = create_session("CTX-A")
bad_ctx = create_conversation_context("CTX-B")
bad = run_contextual_turn(kb, bad_state, bad_ctx, "Python programming")
check(bad.runtime_result.runtime_status != RUNTIME_READY,
      "Mismatched context must not be runtime-ready")
check(bad.context_used is False,
      "Blocked mismatch must not claim context use")
check(bad.errors, "Mismatch must expose errors")
check(validate_conversation_context(bad.context)["valid"],
      "Returned mismatch context should remain structurally valid")

# 45–48: contextual query convenience API
single = contextual_query(
    kb, "What is the fee for Data Analytics in India?", "CTX-SINGLE"
)
check(single.runtime_result.runtime_status == RUNTIME_READY,
      "Convenience query should be ready")
check("₹40,000 + GST" in single.runtime_result.response,
      "Data Analytics fee missing")
check(single.context.session_id == "CTX-SINGLE",
      "Convenience session ID mismatch")
check(validate_contextual_result(single)["valid"],
      "Convenience contextual result invalid")

# 49–52: serialization is defensive
cd = context_to_dict(first.context)
cr = contextual_result_to_dict(second)
check(cd["session_id"] == first.context.session_id,
      "Context serialization ID mismatch")
check(cr["context"]["turn_count"] == second.context.turn_count,
      "Result serialization context mismatch")
cd["active_course_ids"].append("MUTATION")
cr["context"]["source_ids"].append("MUTATION")
check("MUTATION" not in first.context.active_course_ids,
      "Context serialization mutated original")
check("MUTATION" not in second.context.source_ids,
      "Result serialization mutated context")

# 53–57: safety remains read-only
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(second.runtime_result.safety[key] is False,
          f"Safety invariant failed: {key}")
check(second.runtime_result.safety["no_invention"] is True,
      "No-invention invariant failed")
check(validate_contextual_result(second)["valid"],
      "Final contextual validation failed")

print(f"AI CORE 02: {passed}/{total} PASSED")
