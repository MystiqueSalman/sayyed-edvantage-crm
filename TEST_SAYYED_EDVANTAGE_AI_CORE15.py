
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from Sayyed_EdVantage_AI_CORE15 import *

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

LEADS = [
    {
        "lead_id": "SE-00001", "name": "Test One", "phone": "111",
        "email": "one@example.com", "course_id": "SE-DS-001",
        "pipeline_stage": "Counselling", "region": "India",
        "counselling_history": [{"date": "2026-09-14", "note": "Discussed DS"}],
        "follow_up_history": [{"date": "2026-09-15", "reason": "Fee"}],
        "fees": {"quoted": 50000}, "payments": {"status": "pending"},
        "activity_timeline": [{"type": "call"}],
        "pending_items": ["Confirm payment"],
    },
    {
        "lead_id": "SE-00002", "name": "Test Two", "course_id": "SE-PY-001",
        "pipeline_stage": "Interested", "region": "India",
        "counselling_history": [], "follow_up_history": [],
        "fees": {}, "payments": {}, "activity_timeline": [],
        "pending_items": [],
    },
]

with TemporaryDirectory() as td:
    path = Path(td) / "leads.json"
    path.write_text(json.dumps(LEADS, indent=2), encoding="utf-8")

    # Single lead read
    r = read_crm_lead("SE-00001", str(path))
    check(r.status == CRM_READ_READY, "Lead read ready")
    check(r.snapshot is not None, "Snapshot exists")
    check(r.snapshot.lead_id == "SE-00001", "Lead ID preserved")
    check(r.snapshot.name == "Test One", "Name read")
    check(r.snapshot.course_id == "SE-DS-001", "Course read")
    check(r.snapshot.pipeline_stage == "Counselling", "Stage read")
    check(r.snapshot.region == "India", "Region read")
    check(len(r.snapshot.counselling_history) == 1, "Counselling history read")
    check(len(r.snapshot.follow_up_history) == 1, "Follow-up history read")
    check(r.snapshot.fees["quoted"] == 50000, "Fees read")
    check(r.snapshot.payments["status"] == "pending", "Payments read")
    check(len(r.snapshot.activity_timeline) == 1, "Activity timeline read")
    check("Confirm payment" in r.snapshot.pending_items, "Pending item read")

    # Lead isolation
    r2 = read_crm_lead("SE-00002", str(path))
    check(r2.status == CRM_READ_READY, "Second lead read ready")
    check(r2.snapshot.name == "Test Two", "Second lead name isolated")
    check(r2.snapshot.course_id == "SE-PY-001", "Second lead course isolated")
    check(r2.snapshot.counselling_history == [], "Second lead counselling isolated")
    check(r2.snapshot.payments == {}, "Second lead payment isolated")
    check("Confirm payment" not in r2.snapshot.pending_items, "No pending-item leakage")

    # Not found
    r = read_crm_lead("SE-99999", str(path))
    check(r.status == CRM_READ_NOT_FOUND, "Unknown lead not found")
    check(r.snapshot is None, "Unknown lead has no snapshot")
    check(bool(r.errors), "Unknown lead has diagnostic")

    # Missing ID
    r = read_crm_lead("", str(path))
    check(r.status == CRM_READ_CLARIFICATION, "Missing lead ID clarification")

    # All reads
    all_r = read_crm_leads(str(path))
    check("SE-00001" in all_r and "SE-00002" in all_r, "All leads indexed")
    check(all_r["SE-00001"].snapshot.course_id == "SE-DS-001", "Indexed first lead")
    check(all_r["SE-00002"].snapshot.course_id == "SE-PY-001", "Indexed second lead")

    # Context discrepancy detection
    snap = r2.snapshot
    disc = compare_crm_snapshot_with_context(
        snap,
        {"course_id": "SE-DS-001", "pipeline_stage": "New"},
    )
    check(len(disc) == 2, "Both context discrepancies detected")
    check("Course discrepancy" in disc[0], "Course discrepancy diagnostic")
    check("Pipeline-stage discrepancy" in disc[1], "Stage discrepancy diagnostic")

    no_disc = compare_crm_snapshot_with_context(
        snap,
        {"course_id": "SE-PY-001", "pipeline_stage": "Interested"},
    )
    check(no_disc == [], "Matching context has no discrepancy")

    # Defensive copies
    sd = crm_snapshot_to_dict(snap)
    check(sd["lead_id"] == "SE-00002", "Snapshot serialization")
    sd["pending_items"].append("MUTATION")
    check("MUTATION" not in snap.pending_items, "Pending list defensive copy")
    sd["fees"]["x"] = 1
    check("x" not in snap.fees, "Fees defensive copy")

    # Validation + safety
    v = validate_crm_read_result(r2)
    check(v["valid"] is True, "Valid CRM read validates")
    check(r2.read_only is True, "Read-only true")
    check(r2.execution_enabled is False, "Execution disabled")
    check(r2.messaging_enabled is False, "Messaging disabled")
    check(r2.external_actions_enabled is False, "External actions disabled")
    check(r2.crm_writes_enabled is False, "CRM writes disabled")

    bad = read_crm_lead("SE-00001", str(path))
    bad.crm_writes_enabled = True
    check(not validate_crm_read_result(bad)["valid"], "CRM-write mutation rejected")

    bad = read_crm_lead("SE-00001", str(path))
    bad.execution_enabled = True
    check(not validate_crm_read_result(bad)["valid"], "Execution mutation rejected")

    # Invalid JSON
    badpath = Path(td) / "bad.json"
    badpath.write_text("{invalid", encoding="utf-8")
    r = read_crm_lead("SE-00001", str(badpath))
    check(r.status == CRM_READ_INVALID, "Invalid JSON fails closed")
    check(r.snapshot is None, "Invalid JSON has no snapshot")

    # Missing file
    r = read_crm_lead("SE-00001", str(Path(td) / "missing.json"))
    check(r.status == CRM_READ_ERROR, "Missing source returns read error")
    check(r.snapshot is None, "Missing source has no snapshot")

    # Duplicate IDs
    dup = Path(td) / "dup.json"
    dup.write_text(json.dumps([LEADS[0], LEADS[0]]), encoding="utf-8")
    rr = read_crm_leads(str(dup))
    check(rr["SE-00001"].status == CRM_READ_INVALID, "Duplicate lead ID fails closed")

# Serialization result
r = CRMReadResult(status=CRM_READ_NOT_FOUND, lead_id="SE-X", errors=["not found"])
d = crm_read_result_to_dict(r)
check(d["status"] == CRM_READ_NOT_FOUND, "Result serialization status")
check(d["lead_id"] == "SE-X", "Result serialization ID")
check(d["snapshot"] is None, "Result serialization no snapshot")

print(f"AI CORE 15: {passed}/{total} PASSED")
