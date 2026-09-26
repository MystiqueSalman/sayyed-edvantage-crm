import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE03 import (
    INTENT_UNKNOWN,
    INTENT_PROGRAM_INFORMATION,
    INTENT_COMMERCIAL,
    INTENT_ELIGIBILITY,
    INTENT_CERTIFICATION,
    INTENT_CAREER,
    INTENT_ASSESSMENT_PROJECTS,
    INTENT_TOOLS,
    INTENT_RECOMMENDATION,
    detect_explicit_courses,
    detect_intent,
    understand_message,
    validate_understanding,
    run_understood_turn,
    understanding_to_dict,
    understood_result_to_dict,
    validate_understood_turn,
    build_understanding_layer,
)
from Sayyed_EdVantage_AI_CORE01 import create_session
from Sayyed_EdVantage_AI_CORE02 import create_conversation_context

passed = total = 0
def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1

kb = build_understanding_layer()

# 1–10: normalization and explicit course detection
check(detect_explicit_courses("DATA SCIENCE") == ["SE-DS-001"],
      "Data Science detection failed")
check(detect_explicit_courses("I want Python programming") == ["SE-PY-001"],
      "Python detection failed")
check(detect_explicit_courses("Tell me about Linux administration") == ["SE-LINUX-001"],
      "Linux detection failed")
check(detect_explicit_courses("DevOps course") == ["SE-DEVOPS-001"],
      "DevOps detection failed")
check(detect_explicit_courses("ethical hacking and cybersecurity") == ["SE-EHC-001"],
      "Cybersecurity detection failed")
check(detect_explicit_courses("AI and Generative AI") == ["SE-AIGEN-001"],
      "AI+GenAI detection failed")
check(detect_explicit_courses("data analytics") == ["SE-DA-001"],
      "Data Analytics detection failed")
check("SE-DS-001" in detect_explicit_courses(
    "Data Science and Data Analytics"
), "Multi-course Data Science detection failed")
check("SE-DA-001" in detect_explicit_courses(
    "Data Science and Data Analytics"
), "Multi-course Data Analytics detection failed")
check(detect_explicit_courses("completely unrelated text") == [],
      "Unknown course detection should be empty")

# 11–20: intent classification
check(detect_intent("What is the fee?")["intent"] == INTENT_COMMERCIAL,
      "Commercial intent failed")
check(detect_intent("What are the eligibility requirements?")["intent"] == INTENT_ELIGIBILITY,
      "Eligibility intent failed")
check(detect_intent("Do you provide certification?")["intent"] == INTENT_CERTIFICATION,
      "Certification intent failed")
check(detect_intent("What jobs can I prepare for?")["intent"] == INTENT_CAREER,
      "Career intent failed")
check(detect_intent("What projects are included?")["intent"] == INTENT_ASSESSMENT_PROJECTS,
      "Project intent failed")
check(detect_intent("Which tools are taught?")["intent"] == INTENT_TOOLS,
      "Tools intent failed")
check(detect_intent("Which course should I choose?")["intent"] == INTENT_RECOMMENDATION,
      "Recommendation intent failed")
check(detect_intent("Tell me about the curriculum")["intent"] == INTENT_PROGRAM_INFORMATION,
      "Program-information intent failed")
check(detect_intent("hello there")["intent"] == INTENT_UNKNOWN,
      "Unknown intent failed")
check(detect_intent("How much does the Python course cost?")["intent"] == INTENT_COMMERCIAL,
      "Course+commercial intent failed")

# 21–27: understanding and context behavior
empty_ctx = create_conversation_context("U-001")
u1 = understand_message("What is the fee for Data Science in India?", empty_ctx)
check(u1.intent == INTENT_COMMERCIAL, "Understanding commercial intent failed")
check(u1.explicit_course_ids == ["SE-DS-001"], "Explicit course missing")
check(u1.effective_course_ids == ["SE-DS-001"], "Effective course missing")
check(u1.context_used is False, "Cold-start should not use context")
check(u1.ambiguous is False, "Explicit course query should not be ambiguous")
check(validate_understanding(u1)["valid"], "Understanding validation failed")

state = create_session("U-002")
ctx = create_conversation_context("U-002")
first = run_understood_turn(kb, state, ctx, "Tell me about Python")
check(first.understanding.explicit_course_ids == ["SE-PY-001"],
      "Python course understanding failed")
check(first.contextual_result.runtime_result.response,
      "Python first turn should produce a response")

# 28–35: follow-up uses context
second = run_understood_turn(
    kb, state, first.contextual_result.context, "How much does it cost?"
)
check(second.understanding.explicit_course_ids == [],
      "Follow-up should not require explicit course")
check(second.understanding.context_course_ids == ["SE-PY-001"],
      "Follow-up context course missing")
check(second.understanding.effective_course_ids == ["SE-PY-001"],
      "Follow-up effective course missing")
check(second.understanding.context_used is True,
      "Follow-up should use context")
check(second.understanding.intent == INTENT_COMMERCIAL,
      "Follow-up commercial intent failed")
check(second.contextual_result.runtime_result.response,
      "Follow-up should produce response")
check(second.contextual_result.context.session_id == "U-002",
      "Follow-up session changed")
check(validate_understood_turn(second)["valid"],
      "Follow-up validation failed")

# 36–40: ambiguity is explicit, never silently resolved
multi = understand_message(
    "Compare Data Science and Data Analytics fees",
    empty_ctx,
)
check(len(multi.explicit_course_ids) == 2,
      "Multi-course query should detect two courses")
check(multi.ambiguous is True,
      "Multi-course query should be marked ambiguous")
check(multi.ambiguity_reason,
      "Ambiguity must have a reason")
check(multi.effective_course_ids == multi.explicit_course_ids,
      "Ambiguous course list must be preserved")
check(validate_understanding(multi)["valid"],
      "Multi-course understanding invalid")

# 41–44: specific intent without course context is flagged
unclear = understand_message("What is the fee?", empty_ctx)
check(unclear.intent == INTENT_COMMERCIAL,
      "Fee intent failed")
check(unclear.ambiguous is True,
      "Fee without course should be ambiguous")
check(unclear.effective_course_ids == [],
      "No course should remain empty")
check(validate_understanding(unclear)["valid"],
      "Ambiguous fee understanding invalid")

# 45–49: serialization
ud = understanding_to_dict(u1)
urd = understood_result_to_dict(second)
check(ud["intent"] == INTENT_COMMERCIAL, "Understanding serialization failed")
check(ud["explicit_course_ids"] == ["SE-DS-001"],
      "Course serialization failed")
check(urd["runtime_status"], "Turn serialization status missing")
check(urd["source_ids"] is not None, "Turn serialization sources missing")
check("errors" in urd, "Turn serialization errors missing")

# 50–55: read-only safety through underlying runtime
safety = second.contextual_result.runtime_result.safety
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(safety[key] is False, f"Safety failed: {key}")
check(safety["no_invention"] is True, "No-invention failed")
check(validate_understood_turn(second)["valid"],
      "Final understood-turn validation failed")

print(f"AI CORE 03: {passed}/{total} PASSED")
