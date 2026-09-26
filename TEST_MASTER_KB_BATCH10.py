from Sayyed_EdVantage_Master_KB_BATCH10 import (
    build_master_kb_with_batch10,
    get_conflict_policies,
    get_safety_invariants,
    classify_source_status,
    rank_source_status,
    validate_source_conflicts,
    validate_commercial_safety,
    validate_safety_contract,
    validate_batch10,
)

# 1. Integrated KB remains valid
kb = build_master_kb_with_batch10()
assert kb.validate()["valid"] is True

# 2. Conflict policies are present
policies = get_conflict_policies()
assert policies["same_priority_conflict"] == "do_not_invent; flag_for_human_review"
assert policies["missing_information"] == "return_unknown_or_admissions_handoff"
assert policies["commercial_conflict"] == "use_verified_region_specific_value_only"
assert policies["international_pricing"] == "never_substitute_india_pricing"

# 3. Source-status classification
assert classify_source_status("approved") == "approved_current_source"
assert classify_source_status("draft") == "draft_source"
assert classify_source_status("deprecated") == "deprecated_or_superseded_source"
assert classify_source_status("superseded") == "deprecated_or_superseded_source"

# 4. Source ranking is deterministic
assert rank_source_status("approved") < rank_source_status("draft")
assert rank_source_status("draft") < rank_source_status("deprecated")
assert rank_source_status("deprecated") < rank_source_status("unknown")

# 5. Existing source registry has no conflict
source_report = validate_source_conflicts(kb)
assert source_report["valid"] is True
assert source_report["errors"] == []

# 6. Commercial safety is valid
commercial_report = validate_commercial_safety(kb)
assert commercial_report["valid"] is True
assert commercial_report["errors"] == []

# 7. Find the actual Data Science commercial offering registered by Batch 06.
# Do not hard-code an offering ID: the offering ID is an implementation
# identifier and is not part of the user-facing commercial specification.
data_science_offerings = [
    offering
    for offering in kb.offerings.values()
    if offering.name.strip().lower().startswith("data science")
    and "india" in offering.pricing_regions
    and "international" in offering.pricing_regions
]
assert len(data_science_offerings) >= 1
offering = data_science_offerings[0]

# 8. International Data Science fee remains unknown
assert offering.pricing_regions["international"]["base_fee"] is None
assert offering.pricing_regions["international"]["currency"] is None

# 9. Indian Data Science fee remains the verified user-supplied amount
assert offering.pricing_regions["india"]["base_fee"] == 50000
assert offering.pricing_regions["india"]["currency"] == "INR"

# 10. Safety contract is valid
safety_report = validate_safety_contract(kb)
assert safety_report["valid"] is True
assert safety_report["errors"] == []

# 11. Execution/message/external/CRM writes remain disabled
safety = get_safety_invariants()
assert safety["execution_allowed"] is False
assert safety["message_sending_allowed"] is False
assert safety["external_actions_allowed"] is False
assert safety["crm_write_allowed"] is False
assert safety["no_invention"] is True

# 12. Retrieval cannot execute actions
course = kb.get_course("SE-DSP-001")
assert course.knowledge["retrieval_metadata"]["execution_allowed"] is False

# 13. Integrated control metadata
conflict_control = kb.get_common_knowledge("conflict_control")
assert conflict_control["enabled"] is True
assert conflict_control["last_validation"] == "passed"

# 14. Full Batch 10 validation
report = validate_batch10(kb)
assert report["valid"] is True
assert report["source_conflicts"]["valid"] is True
assert report["commercial_safety"]["valid"] is True
assert report["safety_contract"]["valid"] is True

print("MASTER KB BATCH 10: 14/14 PASSED")
