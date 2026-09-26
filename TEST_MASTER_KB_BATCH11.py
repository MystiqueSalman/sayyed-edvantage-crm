from Sayyed_EdVantage_Master_KB_BATCH11 import (
    DATA_ANALYTICS_COURSE_ID,
    DATA_ANALYTICS_SOURCE_ID,
    DATA_ANALYTICS_OFFERING_ID,
    get_data_analytics_knowledge,
    get_data_analytics_commercial_knowledge,
    validate_data_analytics_knowledge,
    build_master_kb_with_data_analytics,
)

# 1. Standalone knowledge validation
report = validate_data_analytics_knowledge()
assert report["valid"] is True
assert report["errors"] == []

# 2. Build integrated Master KB
kb = build_master_kb_with_data_analytics()
assert kb.validate()["valid"] is True

# 3. Course identity
course = kb.get_course(DATA_ANALYTICS_COURSE_ID)
assert course is not None
assert course.official_name == "Data Analytics – Professional Program"
assert course.category == "Data Analytics"

# 4. Duration and level
knowledge = get_data_analytics_knowledge()
assert knowledge["duration_hours"] == 60
assert knowledge["level"] == "Beginner to Intermediate"
assert knowledge["mode"] == "Instructor-Led / Online Live"

# 5. Prerequisites
assert knowledge["prerequisites"]["prior_programming_required"] is False
assert "Basic computer knowledge" in knowledge["prerequisites"]["required"]
assert "Logical thinking" in knowledge["prerequisites"]["required"]

# 6. Exact 12-module curriculum and 60 hours
assert len(knowledge["modules"]) == 12
assert sum(m["hours"] for m in knowledge["modules"]) == 60
assert knowledge["modules"][1]["title"] == "Advanced Excel"
assert knowledge["modules"][3]["title"] == "SQL for Data Analytics"
assert knowledge["modules"][8]["title"] == "Power BI Data Modeling & DAX"

# 7. Assessment
assert knowledge["assessment"]["total_percent"] == 100
assessment = knowledge["assessment"]
assert sum([
    assessment["quizzes_and_assignments_percent"],
    assessment["hands_on_labs_percent"],
    assessment["mini_projects_percent"],
    assessment["case_study_problem_solving_percent"],
    assessment["capstone_percent"],
    assessment["presentation_and_viva_percent"],
]) == 100
assert assessment["total_percent"] == 100

# 8. Tools
assert knowledge["tools"] == [
    "Microsoft Excel",
    "Power Query",
    "SQL",
    "Power BI",
    "DAX",
]

# 9. Learning outcomes and projects
assert len(knowledge["learning_outcomes"]) == 13
assert len(knowledge["projects"]) == 8
assert "Power BI dashboard project" in knowledge["projects"]

# 10. Career safety
career = knowledge["career"]
assert "Data Analyst" in career["example_roles"]
assert career["guarantees"]["employment"] is False
assert career["guarantees"]["placement"] is False
assert career["guarantees"]["salary"] is False

# 11. Boundary safety
boundaries = knowledge["boundaries"]
assert boundaries["python_is_not_core"] is True
assert "Machine Learning" in boundaries["excluded_as_core"]
assert "RAG" in boundaries["excluded_as_core"]
assert "Agentic AI" in boundaries["excluded_as_core"]

# 12. Certification remains unspecified
assert knowledge["certification"]["status"] == "unknown"
assert knowledge["certification"]["issuer"] is None
assert knowledge["certification"]["certificate_title"] is None

# 13. Source registration and course provenance
assert DATA_ANALYTICS_SOURCE_ID in course.source_ids
source = kb.sources[DATA_ANALYTICS_SOURCE_ID]
assert source.status == "approved"
assert source.version == "1.0"

# 14. India commercial knowledge
commercial = get_data_analytics_commercial_knowledge()
assert commercial["pricing_regions"]["india"]["base_fee"] == 40000
assert commercial["pricing_regions"]["india"]["currency"] == "INR"

# 15. International pricing safety
international = commercial["pricing_regions"]["international"]
assert international["base_fee"] is None
assert international["currency"] is None
assert international["quote_policy"].find("Do not substitute Indian pricing") >= 0

# 16. Offering registered correctly
offering = kb.get_offering(DATA_ANALYTICS_OFFERING_ID)
assert offering is not None
assert offering.pricing_regions["india"]["base_fee"] == 40000
assert offering.pricing_regions["international"]["base_fee"] is None

# 17. Previous Master KB layers remain intact
ds = kb.get_course("SE-DSP-001")
assert ds is not None
assert ds.knowledge["total_duration_hours"] == 60
assert ds.knowledge["retrieval_metadata"]["enabled"] is True
assert kb.get_common_knowledge("conflict_control")["enabled"] is True

# 18. Defensive copy
copy_knowledge = get_data_analytics_knowledge()
copy_knowledge["duration_hours"] = 999
assert get_data_analytics_knowledge()["duration_hours"] == 60

print("MASTER KB BATCH 11: 18/18 PASSED")
