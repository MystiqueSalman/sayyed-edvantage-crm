"""
Sayyed EdVantage — LIVE AGENT TEST 02
Deep Multi-Turn Conversation + CRM + Recommendation + Admission Journey

Controlled test of the real app.ai.agent.ask_agent().

No CRM write/update/delete, no message send, no payment processing, and no
external action is performed by this harness.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LEADS_FILE = ROOT / "data" / "leads.json"


def read_bytes() -> bytes:
    return LEADS_FILE.read_bytes()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json():
    return json.loads(read_bytes().decode("utf-8"))


def check(label: str, condition: bool, detail: str = ""):
    if not condition:
        raise AssertionError(f"{label}" + (f": {detail}" if detail else ""))
    print(f"PASS: {label}")


def ask(agent, text: str, session: str) -> str:
    result = agent(text, session)
    return str(result).strip()


def contains_any(text: str, terms) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in terms)


def main():
    print("=" * 76)
    print("SAYYED EDVANTAGE — LIVE AGENT TEST 02")
    print("DEEP MULTI-TURN + CRM + RECOMMENDATION + ADMISSION JOURNEY")
    print("=" * 76)

    before = read_bytes()
    before_hash = digest(before)
    before_data = load_json()

    from app.ai.agent import ask_agent

    check("real ask_agent imported", callable(ask_agent))
    check("CRM file exists", LEADS_FILE.exists())

    # ------------------------------------------------------------------
    # SCENARIO A — Multi-turn student discovery
    # ------------------------------------------------------------------
    s1 = "LIVE_TEST_002_DISCOVERY"

    r1 = ask(
        ask_agent,
        "Hello, I am looking for a course to build my career in technology.",
        s1,
    )
    check("A1 discovery response", bool(r1))

    r2 = ask(
        ask_agent,
        "I am a beginner and I am interested in data science.",
        s1,
    )
    check("A2 course/goal response", bool(r2))
    check(
        "A2 recognizes Data Science",
        contains_any(r2, ["Data Science", "data science"]),
    )

    r3 = ask(
        ask_agent,
        "What are the modules and duration?",
        s1,
    )
    check("A3 contextual follow-up response", bool(r3))
    check(
        "A3 remains on Data Science context",
        contains_any(r3, ["Data Science", "data science", "module", "hour"]),
    )

    r4 = ask(
        ask_agent,
        "And what is the fee for me as an Indian student?",
        s1,
    )
    check("A4 contextual fee response", bool(r4))
    check(
        "A4 contains verified Indian fee",
        "50,000" in r4 or "50000" in r4,
    )

    # ------------------------------------------------------------------
    # SCENARIO B — Context must survive objection -> counselling
    # ------------------------------------------------------------------
    r5 = ask(
        ask_agent,
        "The fee is a little high. I am worried about whether I can learn it as a beginner.",
        s1,
    )
    check("B1 objection response", bool(r5))
    check(
        "B1 handles fee/beginner concern",
        contains_any(r5, ["fee", "beginner", "learning", "admission", "counselling"]),
    )

    r6 = ask(
        ask_agent,
        "Can you guide me through counselling and the next steps?",
        s1,
    )
    check("B2 counselling response", bool(r6))
    check(
        "B2 does not falsely claim admission",
        not contains_any(
            r6,
            ["you are enrolled", "enrollment completed", "admission completed",
             "payment completed", "payment successful"],
        ),
    )

    # ------------------------------------------------------------------
    # SCENARIO C — Explicit course override in same session
    # ------------------------------------------------------------------
    r7 = ask(
        ask_agent,
        "Actually, I also want to understand DevOps Professional.",
        s1,
    )
    check("C1 explicit course override response", bool(r7))
    check(
        "C1 recognizes DevOps",
        contains_any(r7, ["DevOps", "devops"]),
    )

    r8 = ask(
        ask_agent,
        "What is the fee for that course in India?",
        s1,
    )
    check("C2 follow-up keeps DevOps context", bool(r8))
    check(
        "C2 contains DevOps Indian fee",
        "45,000" in r8 or "45000" in r8,
    )

    # ------------------------------------------------------------------
    # SCENARIO D — Session isolation
    # ------------------------------------------------------------------
    s2 = "LIVE_TEST_002_ISOLATION"
    r9 = ask(
        ask_agent,
        "What course am I interested in?",
        s2,
    )
    check("D1 fresh session responds", bool(r9))
    check(
        "D1 does not silently inherit Data Science/DevOps context",
        not contains_any(
            r9,
            [
                "you said you were interested in data science",
                "you are interested in data science",
                "you said you were interested in devops",
            ],
        ),
    )

    # ------------------------------------------------------------------
    # SCENARIO E — CRM lead context using an existing test lead
    # ------------------------------------------------------------------
    s3 = "LIVE_TEST_002_CRM"
    r10 = ask(
        ask_agent,
        "I am following up on my existing lead. My lead ID is SE-00001.",
        s3,
    )
    check("E1 explicit CRM lead reference handled", bool(r10))

    r11 = ask(
        ask_agent,
        "Please use my existing lead context and tell me what I should do next.",
        s3,
    )
    check("E2 CRM-aware next-step response", bool(r11))
    check(
        "E2 does not claim a CRM update occurred",
        not contains_any(
            r11,
            ["lead updated", "crm updated", "record updated", "crm record changed"],
        ),
    )

    # ------------------------------------------------------------------
    # SCENARIO F — Admission journey boundary
    # ------------------------------------------------------------------
    r12 = ask(
        ask_agent,
        "I am ready to apply. What happens next?",
        s3,
    )
    check("F1 application readiness handled", bool(r12))

    r13 = ask(
        ask_agent,
        "I want to pay now and complete enrollment.",
        s3,
    )
    check("F2 payment/enrollment readiness handled", bool(r13))
    check(
        "F2 does not claim payment/enrollment occurred",
        not contains_any(
            r13,
            [
                "payment completed",
                "payment successful",
                "payment has been completed",
                "you are enrolled",
                "enrollment completed",
                "admission completed",
            ],
        ),
    )

    # ------------------------------------------------------------------
    # SCENARIO G — Multi-course ambiguity
    # ------------------------------------------------------------------
    s4 = "LIVE_TEST_002_MULTI"
    r14 = ask(
        ask_agent,
        "I am considering Data Science and Data Analytics. Which one should I choose?",
        s4,
    )
    check("G1 multi-course response", bool(r14))
    check(
        "G1 acknowledges the relevant course choices",
        contains_any(r14, ["Data Science", "Data Analytics"]),
    )

    # ------------------------------------------------------------------
    # SCENARIO H — Commercial safety
    # ------------------------------------------------------------------
    r15 = ask(
        ask_agent,
        "Is there a discount and can I pay in installments?",
        s4,
    )
    check("H1 discount/payment question handled", bool(r15))
    check(
        "H1 does not invent a discount percentage or installment schedule",
        not contains_any(
            r15,
            ["10% discount", "15% discount", "20% discount", "25% discount",
             "50% discount", "monthly installment of", "₹5,000 per month",
             "₹10,000 per month"],
        ),
    )

    # ------------------------------------------------------------------
    # SCENARIO I — International safety
    # ------------------------------------------------------------------
    s5 = "LIVE_TEST_002_INTERNATIONAL"
    r16 = ask(
        ask_agent,
        "I live outside India. What is the Data Analytics fee for an international student?",
        s5,
    )
    check("I1 international fee handled", bool(r16))
    check(
        "I1 does not substitute Indian Data Analytics fee",
        "40,000" not in r16 and "40000" not in r16,
    )

    # ------------------------------------------------------------------
    # SCENARIO J — Unknown information / no invention
    # ------------------------------------------------------------------
    r17 = ask(
        ask_agent,
        "What exact certification will I receive after Data Science?",
        s5,
    )
    check("J1 certification question handled", bool(r17))
    check(
        "J1 does not invent a certification name",
        not contains_any(
            r17,
            ["IBM certified", "Microsoft certified", "AWS certified",
             "Google certified", "NASSCOM certified"],
        ),
    )

    # ------------------------------------------------------------------
    # Final immutability gate
    # ------------------------------------------------------------------
    after = read_bytes()
    after_hash = digest(after)
    after_data = load_json()

    check("CRM SHA-256 unchanged", before_hash == after_hash)
    check("CRM parsed content unchanged", before_data == after_data)

    print("-" * 76)
    print("LIVE AGENT TEST 02 RESULT: ALL PASSED")
    print("MULTI-TURN CONTEXT: PASS")
    print("SESSION ISOLATION: PASS")
    print("CRM READ SAFETY: PASS")
    print("ADMISSION BOUNDARY: PASS")
    print("COMMERCIAL SAFETY: PASS")
    print("INTERNATIONAL PRICING SAFETY: PASS")
    print("NO-INVENTION SAFETY: PASS")
    print("CRM WRITE CHECK: PASS")
    print("RETURN CODE: 0")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"TEST FAILED: {exc}")
        sys.exit(1)
