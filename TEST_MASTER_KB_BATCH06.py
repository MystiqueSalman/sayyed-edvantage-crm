from Sayyed_EdVantage_Master_KB_BATCH06 import (
    DATA_SCIENCE_INDIA_COMMERCIAL,
    DATA_SCIENCE_INTERNATIONAL_COMMERCIAL,
    INDIA_FEE_SOURCE_ID,
    get_data_science_india_fee,
    get_data_science_international_fee,
    get_commercial_rules,
    get_fee_for_region,
    validate_batch06,
    build_master_kb_with_batch06,
)

# 1. Batch validation
report = validate_batch06()
assert report["valid"] is True

# 2. Indian fee
india = get_data_science_india_fee()
assert india["region"] == "india"
assert india["currency"] == "INR"
assert india["base_fee"] == 50000
assert india["pricing_status"] == "verified_user_supplied"
assert india["final_fee"] is None
assert india["discount"] is None

# 3. GST/final-fee safety
assert "GST" in india["gst"]
assert "confirmed by admissions" in india["gst"]
assert "final fee" in india["handoff"]

# 4. International pricing must remain unknown
international = get_data_science_international_fee()
assert international["pricing_status"] == "unknown"
assert international["base_fee"] is None
assert international["currency"] is None
assert international["final_fee"] is None

# 5. No international fallback to India
rules = get_commercial_rules()
assert rules["international"]["can_quote_india_fee"] is False
assert rules["international"]["fallback_to_india"] is False
assert rules["global"]["no_invention"] is True

# 6. Region-aware lookup
assert get_fee_for_region("india")["base_fee"] == 50000
assert get_fee_for_region("international")["base_fee"] is None
assert get_fee_for_region("international")["pricing_status"] == "unknown"
assert get_fee_for_region("unknown-region")["pricing_status"] == "unknown"

# 7. Defensive copies
india_copy = get_data_science_india_fee()
india_copy["base_fee"] = 1
assert DATA_SCIENCE_INDIA_COMMERCIAL["base_fee"] == 50000

# 8. Master KB integration
kb = build_master_kb_with_batch06()
course = kb.get_course("SE-DSP-001")
offering = kb.get_offering("SE-DSP-001")
assert course is not None
assert offering is not None
assert course.knowledge["commercial_knowledge"]["india"]["base_fee"] == 50000
assert course.knowledge["commercial_knowledge"]["international"]["base_fee"] is None

# 9. Offering has independent regional pricing
assert offering.pricing_regions["india"]["base_fee"] == 50000
assert offering.pricing_regions["international"]["base_fee"] is None

# 10. Fee source is registered
assert INDIA_FEE_SOURCE_ID in kb.sources
assert kb.sources[INDIA_FEE_SOURCE_ID].status == "approved"
assert kb.sources[INDIA_FEE_SOURCE_ID].source_type == "user_supplied_commercial_fee"

# 11. Previous course knowledge remains intact
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["detailed_curriculum"]["modules"]) == 14
assert len(course.knowledge["project_knowledge"]) == 9
assert "eligibility_knowledge" in course.knowledge

# 12. Master validation
assert kb.validate()["valid"] is True

print("MASTER KB BATCH 06: 12/12 PASSED")
