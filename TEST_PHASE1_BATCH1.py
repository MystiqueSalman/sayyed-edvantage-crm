from pathlib import Path
import hashlib
from Sayyed_EdVantage_AI_Agent_BATCH1 import (
    LEADS_FILE, get_all_leads, lead_intelligence, rank_leads
)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    print("=" * 72)
    print("PHASE 1 / BATCH 1 — VERIFICATION")
    print("=" * 72)

    before = digest(LEADS_FILE) if LEADS_FILE.exists() else None
    leads = get_all_leads()
    ranked = rank_leads(leads)

    assert isinstance(leads, list)
    assert len(ranked) == len(leads)

    required = {
        "lead_id", "name", "status", "score", "classification",
        "priority", "next_best_action", "activity"
    }

    for lead in leads:
        result = lead_intelligence(lead)
        assert required.issubset(result)
        assert 0 <= result["score"] <= 100
        assert result["classification"] in {"Hot", "Warm", "Cold", "Enrolled", "Lost"}
        assert result["priority"] in {"Critical", "High", "Medium", "Low"}
        assert isinstance(result["next_best_action"], str)
        assert isinstance(result["activity"], dict)

    after = digest(LEADS_FILE) if LEADS_FILE.exists() else None
    assert before == after, "leads.json was modified"

    print(f"Leads checked       : {len(leads)}")
    print("Scoring             : PASSED")
    print("Priority            : PASSED")
    print("Classification      : PASSED")
    print("Next best action    : PASSED")
    print("Intelligence panel  : PASSED")
    print("Activity history    : PASSED")
    print("Data integrity      : PASSED")
    print()
    print("BATCH 1 VERIFICATION PASSED")
    print("=" * 72)

if __name__ == "__main__":
    main()
