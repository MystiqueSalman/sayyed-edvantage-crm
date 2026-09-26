from pathlib import Path
import hashlib
from Sayyed_EdVantage_AI_Agent_BATCH3 import (
    LEADS_FILE, all_leads, workflow_intelligence,
    conversation_memory, infer_true_stage, follow_up_timing,
    communication_channel, escalation_detection, counsellor_brief
)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    print("=" * 78)
    print("PHASE 1 / BATCH 3 — VERIFICATION")
    print("=" * 78)

    before = digest(LEADS_FILE) if LEADS_FILE.exists() else None
    leads = all_leads()

    for lead in leads:
        memory = conversation_memory(lead)
        stage = infer_true_stage(lead, memory)
        timing = follow_up_timing(lead, stage)
        channel = communication_channel(lead, stage, memory)
        escalation = escalation_detection(lead, stage, timing, memory)
        brief = counsellor_brief(lead, memory, stage, timing, channel, escalation)
        result = workflow_intelligence(lead)

        assert isinstance(memory["interaction_count"], int)
        assert memory["interaction_count"] >= 0
        assert stage["crm_stage"]
        assert stage["inferred_stage"]
        assert 0 <= stage["confidence"] <= 100
        assert timing["urgency"] in {"None", "Immediate", "High", "Medium"}
        assert timing["recommended_window"]
        assert channel["recommended_channel"]
        assert escalation["escalation_level"] in {"None", "Low", "Medium", "High"}
        assert isinstance(escalation["escalate"], bool)
        assert brief["headline"]
        assert isinstance(brief["preparation_points"], list)

        assert set(result) == {
            "lead_id", "name", "conversation_memory", "stage_intelligence",
            "follow_up_timing", "communication_channel", "escalation",
            "counsellor_brief"
        }

    after = digest(LEADS_FILE) if LEADS_FILE.exists() else None
    assert before == after, "leads.json was modified"

    print(f"Leads checked         : {len(leads)}")
    print("Conversation memory   : PASSED")
    print("Stage intelligence   : PASSED")
    print("Follow-up timing     : PASSED")
    print("Channel recommendation: PASSED")
    print("Escalation detection : PASSED")
    print("Counsellor brief     : PASSED")
    print("Data integrity       : PASSED")
    print()
    print("BATCH 3 VERIFICATION PASSED")
    print("=" * 78)

if __name__ == "__main__":
    main()
