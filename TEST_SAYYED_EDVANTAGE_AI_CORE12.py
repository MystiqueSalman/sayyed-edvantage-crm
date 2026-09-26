
from Sayyed_EdVantage_AI_CORE12 import *

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

kb = build_master_kb_with_commercial_knowledge()
check(kb.commercial_layer.validate()["valid"], "Commercial layer validates")
check(len(kb.commercial_layer.list_offerings()) == 9, "Nine commercial offerings")
check(kb.commercial_layer.international_defined is False, "International pricing undefined")
check(COMMERCIAL_SOURCE_ID == "COMMERCIAL-FEE-INDIA-001", "Commercial source ID")

# Intent detection
for msg, expected, label in [
    ("What is the fee?", COMMERCIAL_INTENT_FEE, "Fee intent"),
    ("Can I get a discount?", COMMERCIAL_INTENT_DISCOUNT, "Discount intent"),
    ("Do you have EMI?", COMMERCIAL_INTENT_PAYMENT, "Payment intent"),
    ("Is GST included?", COMMERCIAL_INTENT_TAX, "Tax intent"),
    ("I am an international student.", COMMERCIAL_INTENT_INTERNATIONAL, "International intent"),
    ("What is the combo price?", COMMERCIAL_INTENT_COMBO, "Combo intent"),
]:
    check(detect_commercial_intent(msg).intent == expected, label)

check(detect_commercial_intent("").intent == COMMERCIAL_INTENT_UNKNOWN, "Empty commercial intent unknown")
check(detect_commercial_intent("Tell me about the curriculum.").intent == COMMERCIAL_INTENT_UNKNOWN, "Non-commercial intent unknown")

# Verified India fees
expected = {
    "Data Science": 50000,
    "Data Analytics": 40000,
    "Data Science + Data Analytics Combo": 80000,
    "AI + Generative AI": 70000,
    "Python": 35000,
    "Linux": 25000,
    "DevOps": 45000,
    "Linux + DevOps Combo": 60000,
    "Ethical Hacking & Cybersecurity": 60000,
}
for name, fee in expected.items():
    p = build_commercial_conversation_plan(f"What is the fee for {name} in India?", f"S-{name}")
    check(p.status == COMMERCIAL_READY, f"{name} fee ready")
    check(p.commercial_record["fee"] == fee, f"{name} fee exact")
    check(p.commercial_record["currency"] == "INR", f"{name} currency")
    check(p.commercial_record["source_id"] == COMMERCIAL_SOURCE_ID, f"{name} provenance")
    check("+ GST" in " ".join(p.answer_points), f"{name} GST note")

# Region safety
p = build_commercial_conversation_plan("What is the fee for Data Science?", "REG-01")
check(p.status == COMMERCIAL_CLARIFICATION, "Unknown region requires clarification")
check(p.commercial_record["fee"] is None, "Unknown region cannot quote fee")
check(bool(p.clarification_questions), "Region clarification question")

p = build_commercial_conversation_plan("What is the fee for Data Science for an international student?", "REG-02")
check(p.status == COMMERCIAL_HANDOFF, "International pricing handoff")
check(p.human_handoff_required is True, "International handoff required")
check(p.commercial_record["fee"] is None, "International fee undefined")
check("Indian pricing" in p.commercial_record["message"], "No India fallback message")

# Explicit region overrides query
p = build_commercial_conversation_plan("What is the fee for Data Science?", "REG-03", region="international")
check(p.status == COMMERCIAL_HANDOFF, "Explicit international region wins")
check(p.commercial_record["fee"] is None, "Explicit international fee undefined")

p = build_commercial_conversation_plan("What is the fee for Data Science?", "REG-04", region="india")
check(p.status == COMMERCIAL_READY, "Explicit India region works")

# Discount/payment are not invented
p = build_commercial_conversation_plan("Can you give me a discount on Data Science in India?", "DISC-01")
check(p.status == COMMERCIAL_HANDOFF, "Discount requires handoff")
check(p.human_handoff_required is True, "Discount handoff required")
check("discount" in " ".join(p.answer_points).lower(), "Discount limitation explicit")
check("invent" in " ".join(p.prohibited_claims).lower(), "Discount no-invention safety")

p = build_commercial_conversation_plan("Can I pay Data Science in EMI in India?", "PAY-01")
check(p.status == COMMERCIAL_HANDOFF, "Payment plan requires handoff")
check("payment plan" in " ".join(p.prohibited_claims).lower(), "Payment safety explicit")
check(p.human_handoff_required is True, "Payment handoff required")

# Tax
p = build_commercial_conversation_plan("What is the GST on Data Science in India?", "TAX-01")
check(p.status == COMMERCIAL_READY, "Tax query has controlled answer")
check("GST/tax" in " ".join(p.answer_points), "Tax applicability stated")
check("specific tax amount" in " ".join(p.answer_points), "Specific tax amount not invented")

# Combo safety
p = build_commercial_conversation_plan("What is the Data Science + Data Analytics Combo fee in India?", "COMBO-01")
check(p.status == COMMERCIAL_READY, "DSDA combo ready")
check(p.commercial_record["fee"] == 80000, "DSDA combo exact fee")
check("curriculum composition" in " ".join(p.answer_points), "Combo composition not invented")

p = build_commercial_conversation_plan("What is the Linux + DevOps Combo fee in India?", "COMBO-02")
check(p.status == COMMERCIAL_READY, "Linux DevOps combo ready")
check(p.commercial_record["fee"] == 60000, "Linux DevOps combo exact fee")

# Unknown offering
p = build_commercial_conversation_plan("What is the fee for Quantum AI in India?", "UNK-01")
check(p.status == COMMERCIAL_HANDOFF, "Unknown offering handoff")
check(p.human_handoff_required is True, "Unknown offering handoff flag")

# Unknown question
p = build_commercial_conversation_plan("Please help me.", "UNK-02")
check(p.status == COMMERCIAL_UNKNOWN, "Unknown commercial question remains unknown")
check(bool(p.clarification_questions), "Unknown commercial question asks clarification")

# Safety invariants
p = commercial_conversation_query("What is the fee for Python in India?", "SAFE-01")
check(p.no_invention is True, "No invention true")
check(p.execution_enabled is False, "Execution false")
check(p.messaging_enabled is False, "Messaging false")
check(p.external_actions_enabled is False, "External actions false")
check(p.crm_writes_enabled is False, "CRM writes false")
check(bool(p.prohibited_claims), "Prohibited claims present")

# Validation mutation checks
bad = commercial_conversation_query("What is the fee for Python in India?", "BAD-01")
bad.execution_enabled = True
check(not validate_commercial_conversation_plan(bad)["valid"], "Execution mutation rejected")

bad = commercial_conversation_query("What is the fee for Python in India?", "BAD-02")
bad.crm_writes_enabled = True
check(not validate_commercial_conversation_plan(bad)["valid"], "CRM mutation rejected")

bad = commercial_conversation_query("What is the fee for Python in India?", "BAD-03")
bad.prohibited_claims = []
check(not validate_commercial_conversation_plan(bad)["valid"], "Missing safety claims rejected")

bad = commercial_conversation_query("What is the fee for Python in India?", "BAD-04")
bad.status = COMMERCIAL_CLARIFICATION
bad.clarification_questions = []
check(not validate_commercial_conversation_plan(bad)["valid"], "Invalid clarification rejected")

bad = commercial_conversation_query("What is the fee for Python in India?", "BAD-05")
bad.status = COMMERCIAL_HANDOFF
bad.human_handoff_required = False
bad.handoff_reason = None
check(not validate_commercial_conversation_plan(bad)["valid"], "Invalid handoff rejected")

# Serialization
p = commercial_conversation_query("What is the fee for Python in India?", "SER-01")
d = commercial_plan_to_dict(p)
check(d["session_id"] == "SER-01", "Serialization session")
check(d["status"] == p.status, "Serialization status")
check(d["signal"]["intent"] == p.signal.intent, "Serialization intent")
check(d["commercial_record"]["fee"] == 35000, "Serialization fee")
check(d["no_invention"] is True, "Serialization safety")

# Determinism
a = detect_commercial_intent("What is the fee for Python in India?")
b = detect_commercial_intent("What is the fee for Python in India?")
check(a.intent == b.intent, "Intent deterministic")
check(a.matched_terms == b.matched_terms, "Terms deterministic")

# Exact source validation
record = get_commercial_answer(kb, "What is the fee for Data Science in India?", region="india")
check(validate_commercial_answer(record)["valid"], "Underlying commercial record validates")
check(record["source_id"] == COMMERCIAL_SOURCE_ID, "Underlying provenance preserved")

print(f"AI CORE 12: {passed}/{total} PASSED")
