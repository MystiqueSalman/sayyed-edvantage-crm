from pathlib import Path
import hashlib
from Sayyed_EdVantage_AI_Agent_BATCH2 import (
    LEADS_FILE, all_leads, lead_decision, rank_decisions,
    detect_intent, detect_objections, detect_buying_signals,
    counselling_strategy, generate_script, risk_and_conversion
)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    print("=" * 76)
    print("PHASE 1 / BATCH 2 — VERIFICATION")
    print("=" * 76)

    before = digest(LEADS_FILE) if LEADS_FILE.exists() else None
    leads = all_leads()
    results = rank_decisions(leads)

    assert len(results) == len(leads)

    for lead in leads:
        intent = detect_intent(lead)
        objections = detect_objections(lead)
        buying = detect_buying_signals(lead)
        strategy = counselling_strategy(lead, intent, objections, buying)
        script = generate_script(lead, strategy, intent, objections, buying)
        risk = risk_and_conversion(lead, intent, objections, buying)
        result = lead_decision(lead)

        assert intent["primary"] in {
            "Enrolled", "Admission Intent", "Information Seeking", "Early Exploration"
        }
        assert 0 <= intent["confidence"] <= 100
        assert objections["count"] >= 0
        assert buying["level"] in {"Strong", "Moderate", "Weak"}
        assert 0 <= buying["strength"] <= 100
        assert isinstance(strategy["objective"], str) and strategy["objective"]
        assert isinstance(strategy["recommended_question"], str) and strategy["recommended_question"]
        assert isinstance(script["full_script"], str) and script["full_script"]
        assert 0 <= risk["risk_score"] <= 100
        assert 0 <= risk["conversion_score"] <= 100
        assert risk["conversion_outlook"] in {"High", "Moderate", "Low"}
        assert set(result) == {
            "lead_id", "name", "intent", "objections", "buying_signals",
            "counselling_strategy", "personalized_script", "risk_and_conversion"
        }

    after = digest(LEADS_FILE) if LEADS_FILE.exists() else None
    assert before == after, "leads.json was modified"

    print(f"Leads checked         : {len(leads)}")
    print("Intent detection      : PASSED")
    print("Objection detection   : PASSED")
    print("Buying signals        : PASSED")
    print("Counselling strategy  : PASSED")
    print("Personalized script   : PASSED")
    print("Risk/conversion       : PASSED")
    print("Data integrity        : PASSED")
    print()
    print("BATCH 2 VERIFICATION PASSED")
    print("=" * 76)

if __name__ == "__main__":
    main()
