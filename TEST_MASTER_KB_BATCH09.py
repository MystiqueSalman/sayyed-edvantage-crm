from Sayyed_EdVantage_Master_KB_BATCH09 import (
    DATA_SCIENCE_COURSE_ID, get_source, list_sources,
    register_knowledge_source, set_source_status,
    validate_source_registry, attach_source_registry_metadata,
    build_master_kb_with_batch09
)

# 1. Build integrated KB
kb = build_master_kb_with_batch09()
assert kb.validate()["valid"] is True

# 2. Source registry metadata
registry = kb.get_common_knowledge("source_registry")
assert registry["versioning_enabled"] is True
assert registry["approved_current_sources_only"] is True
assert registry["course_isolation"] is True
assert registry["provenance_required"] is True
assert registry["no_silent_source_replacement"] is True

# 3. Data Science source exists
source = get_source(kb, "DS-CURRICULUM-SOURCE-001")
assert source is not None
assert source.course_id == DATA_SCIENCE_COURSE_ID
assert source.status == "approved"
assert source.version == "1.0"

# 4. Source listing and course isolation
sources = list_sources(kb, DATA_SCIENCE_COURSE_ID)
assert len(sources) >= 2
assert all(s["course_id"] == DATA_SCIENCE_COURSE_ID for s in sources)

# 5. Register a versioned source
register_knowledge_source(
    kb,
    source_id="DS-TEST-SOURCE-001",
    title="Data Science Test Source",
    source_type="test_source",
    course_id=DATA_SCIENCE_COURSE_ID,
    version="2.0",
    status="draft",
)
test_source = get_source(kb, "DS-TEST-SOURCE-001")
assert test_source.version == "2.0"
assert test_source.status == "draft"

# 6. Source status transition
updated = set_source_status(kb, "DS-TEST-SOURCE-001", "approved")
assert updated.status == "approved"

# 7. Deprecated source transition
updated = set_source_status(
    kb, "DS-TEST-SOURCE-001", "deprecated",
    replacement_source_id="DS-CURRICULUM-SOURCE-001"
)
assert updated.status == "deprecated"
assert "Replacement source: DS-CURRICULUM-SOURCE-001" in updated.notes

# 8. Invalid status is rejected
try:
    set_source_status(kb, "DS-CURRICULUM-SOURCE-001", "invalid")
    raise AssertionError("Invalid source status was accepted.")
except ValueError:
    pass

# 9. Registry validation
# The deprecated test source is not attached to current course knowledge,
# so validation remains valid.
assert validate_source_registry(kb)["valid"] is True

# 10. Current course source reference remains approved
course = kb.get_course(DATA_SCIENCE_COURSE_ID)
assert course.source_ids == ["DS-CURRICULUM-SOURCE-001"]
assert get_source(kb, course.source_ids[0]).status == "approved"

# 11. Source/version control is integrated into course knowledge
svc = course.knowledge["source_version_control"]
assert svc["enabled"] is True
assert svc["provenance_required"] is True
assert svc["approved_current_sources_only"] is True

# 12. Defensive copy
source_copy = get_source(kb, "DS-CURRICULUM-SOURCE-001")
source_copy.status = "tampered"
assert get_source(kb, "DS-CURRICULUM-SOURCE-001").status == "approved"

# 13. Previous layers remain intact
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["detailed_curriculum"]["modules"]) == 14
assert course.knowledge["commercial_knowledge"]["india"]["base_fee"] == 50000
assert course.knowledge["commercial_knowledge"]["international"]["base_fee"] is None
assert course.knowledge["retrieval_metadata"]["enabled"] is True

print("MASTER KB BATCH 09: 13/13 PASSED")
