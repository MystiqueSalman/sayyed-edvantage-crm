
from Sayyed_EdVantage_AI_CORE14 import *

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

# Detection
cases = [
    ("I still need to complete my application.", FOLLOWUP_APPLICATION, "Application signal"),
    ("Payment is pending.", FOLLOWUP_PAYMENT, "Payment signal"),
    ("I need the fee details.", FOLLOWUP_FEE, "Fee signal"),
    ("I still have a concern about the course.", FOLLOWUP_OBJECTION, "Objection signal"),
    ("We discussed this in counselling.", FOLLOWUP_COUNSELLING, "Counselling signal"),
    ("I need to know what documents are required.", FOLLOWUP_APPLICATION, "Documents/application signal"),
    ("I need to discuss this with the admissions team.", FOLLOWUP_HUMAN_HANDOFF, "Human handoff signal"),
]
for msg, expected, label in cases:
    check(detect_followup_signal(msg).reason == expected, label)

check(detect_followup_signal("").reason == FOLLOWUP_UNKNOWN, "Empty signal unknown")
check(detect_followup_signal("Hello, how are you?").reason == FOLLOWUP_NONE, "Normal message no follow-up")

# Basic recommendations
p = build_followup_plan("I still need to complete my application.", "F14-01")
check(p.status == FOLLOWUP_RECOMMEND, "Application follow-up recommended")
check(p.priority == PRIORITY_HIGH, "Application follow-up high priority")
check(bool(p.next_conversation_topics), "Application topic present")
check(p.avoid_repetition is True, "Repetition avoidance enabled")

p = build_followup_plan("Payment is pending.", "F14-02")
check(p.status == FOLLOWUP_RECOMMEND, "Payment follow-up recommended")
check(p.priority == PRIORITY_HIGH, "Payment follow-up high priority")
check("payment" in p.next_conversation_topics[0].lower(), "Payment topic explicit")

p = build_followup_plan("I need the fee details.", "F14-03")
check(p.status == FOLLOWUP_RECOMMEND, "Fee follow-up recommended")
check(p.priority == PRIORITY_NORMAL, "Fee priority normal")
check(bool(p.clarification_questions), "Fee region/course clarification present")

# Pending context preserved
p = build_followup_plan(
    "Application is pending.",
    "F14-04",
    pending_items=["Course selection confirmed", "Application documents pending"],
)
check("Course selection confirmed" in p.pending_items, "Existing pending item preserved")
check("Application documents pending" in p.pending_items, "Second pending item preserved")

# Avoid repetition
p = build_followup_plan(
    "Payment is pending.",
    "F14-05",
    prior_topics=["Verified payment details and authorized payment status verification."],
)
check(p.status == FOLLOWUP_NOT_NEEDED, "Repeated topic not recommended")
check(not p.next_conversation_topics, "Repeated topic produces no new topic")
check(p.avoid_repetition is True, "Repetition safeguard remains enabled")

# Unknown clarification
p = build_followup_plan("", "F14-06")
check(p.status == FOLLOWUP_CLARIFICATION, "Unknown context clarifies")
check(bool(p.clarification_questions), "Unknown context asks question")

# No forced follow-up
p = build_followup_plan("Tell me about the course.", "F14-07")
check(p.status == FOLLOWUP_NOT_NEEDED, "No follow-up signal does not force follow-up")
check(not p.next_conversation_topics, "No topic when follow-up not needed")

# Existing human review wins
p = build_followup_plan(
    "Payment is pending.",
    "F14-08",
    human_review_required=True,
    human_review_reason="Admissions verification required.",
)
check(p.status == FOLLOWUP_HANDOFF, "Human review forces handoff")
check(p.human_handoff_required is True, "Handoff flag true")
check(p.priority == PRIORITY_HIGH, "Handoff high priority")
check("verification" in (p.handoff_reason or "").lower(), "Handoff reason preserved")

# Multiple signals are retained
p = build_followup_plan("The fee is high and payment is pending.", "F14-09")
check(p.signal.reason in {FOLLOWUP_PAYMENT, FOLLOWUP_FEE}, "Primary commercial follow-up signal deterministic")
check(len(p.signal.matched_terms) >= 2, "Multiple matched terms retained")

# Safety invariants
p = run_followup_intelligence("Application is pending.", "F14-10")
check(p.no_invention is True, "No invention")
check(p.execution_enabled is False, "Execution disabled")
check(p.messaging_enabled is False, "Messaging disabled")
check(p.external_actions_enabled is False, "External actions disabled")
check(p.crm_writes_enabled is False, "CRM writes disabled")

prohibited = " ".join([
    " ".join(p.rationale),
    " ".join(p.safe_next_steps),
    "Do not invent urgency or a deadline.",
    "Do not send a follow-up message automatically.",
])
check("invent" in prohibited.lower(), "No invention safety explicit")
check("automatically" in prohibited.lower(), "Automatic sending prohibited")

# Validation
v = validate_followup_plan(p)
check(v["valid"] is True, "Valid plan validates")

bad = run_followup_intelligence("Payment is pending.", "BAD-01")
bad.execution_enabled = True
check(not validate_followup_plan(bad)["valid"], "Execution mutation rejected")

bad = run_followup_intelligence("Payment is pending.", "BAD-02")
bad.messaging_enabled = True
check(not validate_followup_plan(bad)["valid"], "Messaging mutation rejected")

bad = run_followup_intelligence("Payment is pending.", "BAD-03")
bad.crm_writes_enabled = True
check(not validate_followup_plan(bad)["valid"], "CRM mutation rejected")

bad = run_followup_intelligence("Payment is pending.", "BAD-04")
bad.avoid_repetition = False
check(not validate_followup_plan(bad)["valid"], "Repetition safeguard mutation rejected")

bad = run_followup_intelligence("Payment is pending.", "BAD-05")
bad.status = FOLLOWUP_RECOMMEND
bad.next_conversation_topics = []
check(not validate_followup_plan(bad)["valid"], "Empty recommendation rejected")

bad = run_followup_intelligence("", "BAD-06")
bad.status = FOLLOWUP_CLARIFICATION
bad.clarification_questions = []
check(not validate_followup_plan(bad)["valid"], "Empty clarification rejected")

bad = run_followup_intelligence("Payment is pending.", "BAD-07")
bad.status = FOLLOWUP_HANDOFF
bad.human_handoff_required = False
bad.handoff_reason = None
check(not validate_followup_plan(bad)["valid"], "Invalid handoff rejected")

# Serialization
p = run_followup_intelligence("I need the fee details.", "F14-11")
d = followup_plan_to_dict(p)
check(d["session_id"] == "F14-11", "Serialization session")
check(d["status"] == p.status, "Serialization status")
check(d["priority"] == p.priority, "Serialization priority")
check(d["signal"]["reason"] == p.signal.reason, "Serialization signal")
check(d["avoid_repetition"] is True, "Serialization repetition safeguard")
check(d["no_invention"] is True, "Serialization no invention")

# Determinism
a = detect_followup_signal("Payment is pending.")
b = detect_followup_signal("Payment is pending.")
check(a.reason == b.reason, "Detection deterministic")
check(a.matched_terms == b.matched_terms, "Matched terms deterministic")

# Explicit text preserved
check(a.explicit_text == "Payment is pending.", "Explicit text preserved")

print(f"AI CORE 14: {passed}/{total} PASSED")
