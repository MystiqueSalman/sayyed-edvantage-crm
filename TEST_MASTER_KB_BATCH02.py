from Sayyed_EdVantage_Master_KB_BATCH02 import (
    DATA_SCIENCE_COURSE_ID, DATA_SCIENCE_KNOWLEDGE, DATA_SCIENCE_SOURCE_ID,
    validate_data_science_knowledge, build_master_kb_with_data_science
)

report = validate_data_science_knowledge()
assert report["valid"] is True
assert DATA_SCIENCE_COURSE_ID == "SE-DSP-001"
assert DATA_SCIENCE_KNOWLEDGE["official_name"] == "Data Science – Professional Program"
assert DATA_SCIENCE_KNOWLEDGE["total_duration_hours"] == 60
assert len(DATA_SCIENCE_KNOWLEDGE["modules"]) == 14
assert sum(m["hours"] for m in DATA_SCIENCE_KNOWLEDGE["modules"]) == 60
assert "No prior programming experience required" in DATA_SCIENCE_KNOWLEDGE["prerequisites"]
assert DATA_SCIENCE_KNOWLEDGE["core_learning_flow"][0] == "Problem Definition"
assert DATA_SCIENCE_KNOWLEDGE["core_learning_flow"][-1] == "Communication"
assert len(DATA_SCIENCE_KNOWLEDGE["projects"]) == 9
assert DATA_SCIENCE_KNOWLEDGE["capstone"]["title"] == "End-to-End Data Science Project"
assert sum(DATA_SCIENCE_KNOWLEDGE["assessment"].values()) == 100
for tool in ("Python", "SQL", "Pandas", "Scikit-Learn", "TensorFlow", "Docker"):
    assert tool in DATA_SCIENCE_KNOWLEDGE["tools"]
assert "LangChain" in DATA_SCIENCE_KNOWLEDGE["course_boundary_excluded"]
assert "RAG" in DATA_SCIENCE_KNOWLEDGE["course_boundary_excluded"]
assert "Agentic AI" in DATA_SCIENCE_KNOWLEDGE["course_boundary_excluded"]
assert DATA_SCIENCE_KNOWLEDGE["unsupported_or_unspecified"]["fee_details_in_curriculum"] == "Not specified in the curriculum source."
assert DATA_SCIENCE_KNOWLEDGE["unsupported_or_unspecified"]["certification_details_in_curriculum"] == "Not specified in the curriculum source."

kb = build_master_kb_with_data_science()
course = kb.get_course(DATA_SCIENCE_COURSE_ID)
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["modules"]) == 14
assert course.source_ids == [DATA_SCIENCE_SOURCE_ID]
assert DATA_SCIENCE_SOURCE_ID in kb.sources
assert kb.sources[DATA_SCIENCE_SOURCE_ID].status == "approved"
master_report = kb.validate()
assert master_report["valid"] is True
assert master_report["course_count"] == 1
assert master_report["source_count"] == 1
course.knowledge["tampered"] = True
assert "tampered" not in kb.get_course(DATA_SCIENCE_COURSE_ID).knowledge

print("MASTER KB BATCH 02: 16/16 PASSED")
