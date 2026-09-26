from Sayyed_EdVantage_Master_KB_BATCH13 import (
    PYTHON_COURSE_ID,
    PYTHON_SOURCE_ID,
    PYTHON_OFFERING_ID,
    get_python_knowledge,
    get_python_commercial_knowledge,
    validate_python_knowledge,
    build_master_kb_with_python,
)

# 1. Standalone knowledge validation
report = validate_python_knowledge()
assert report["valid"] is True
assert report["errors"] == []

# 2. Integrated Master KB
kb = build_master_kb_with_python()
assert kb.validate()["valid"] is True

# 3. Course identity
course = kb.get_course(PYTHON_COURSE_ID)
assert course is not None
assert course.official_name == "Python – Professional Program"
assert course.category == "Python"
assert course.status == "active"

# 4. Duration, level and mode
knowledge = get_python_knowledge()
assert knowledge["duration_hours"] == 40
assert knowledge["level"] == "Beginner to Intermediate"
assert knowledge["mode"] == "Instructor-Led / Online Live"

# 5. Prerequisites
assert knowledge["prerequisites"]["prior_programming_required"] is False
assert "Basic computer knowledge" in knowledge["prerequisites"]["required"]
assert "Logical thinking" in knowledge["prerequisites"]["required"]

# 6. Exact 8-module curriculum and 40 hours
assert len(knowledge["modules"]) == 8
assert sum(m["hours"] for m in knowledge["modules"]) == 40
assert knowledge["modules"][0]["title"] == "Programming Mindset & Python Foundations"
assert knowledge["modules"][2]["title"] == "Data Structures"
assert knowledge["modules"][6]["title"] == "APIs, Automation & Professional Python"
assert knowledge["modules"][7]["title"] == "Testing, Debugging, Projects & Career Lab"

# 7. Assessment
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
assert len(knowledge["tools"]) == 11
assert "Python" in knowledge["tools"]
assert "pip" in knowledge["tools"]
assert "venv" in knowledge["tools"]
assert "REST APIs" in knowledge["tools"]
assert "Git" in knowledge["tools"]
assert "GitHub" in knowledge["tools"]

# 9. Projects and outcomes
assert len(knowledge["projects"]) == 9
assert "Final real-world Python application" in knowledge["projects"]
assert len(knowledge["learning_outcomes"]) == 12

# 10. Career safety
career = knowledge["career"]
assert "Python Developer" in career["example_roles"]
assert career["guarantees"]["employment"] is False
assert career["guarantees"]["placement"] is False
assert career["guarantees"]["salary"] is False
assert career["guarantees"]["income"] is False

# 11. Program boundaries
boundaries = knowledge["boundaries"]
assert "Generative AI" in boundaries["not_core"]
assert "RAG" in boundaries["not_core"]
assert "Agentic AI" in boundaries["not_core"]

# 12. Certification remains unspecified
assert knowledge["certification"]["status"] == "unknown"
assert knowledge["certification"]["issuer"] is None
assert knowledge["certification"]["certificate_title"] is None

# 13. Source registration
assert PYTHON_SOURCE_ID in course.source_ids
source = kb.sources[PYTHON_SOURCE_ID]
assert source.status == "approved"
assert source.version == "1.0"

# 14. India commercial knowledge
commercial = get_python_commercial_knowledge()
assert commercial["pricing_regions"]["india"]["base_fee"] == 35000
assert commercial["pricing_regions"]["india"]["currency"] == "INR"

# 15. International pricing safety
international = commercial["pricing_regions"]["international"]
assert international["base_fee"] is None
assert international["currency"] is None
assert "Do not substitute Indian pricing" in international["quote_policy"]

# 16. Offering registered correctly
offering = kb.get_offering(PYTHON_OFFERING_ID)
assert offering is not None
assert offering.pricing_regions["india"]["base_fee"] == 35000
assert offering.pricing_regions["international"]["base_fee"] is None

# 17. Previous courses and safety layers remain intact
assert kb.get_course("SE-DSP-001") is not None
assert kb.get_course("SE-DA-001") is not None
assert kb.get_course("SE-AIGEN-001") is not None
assert kb.get_common_knowledge("conflict_control")["enabled"] is True
assert kb.get_common_knowledge("safety_contract")["execution_allowed"] is False

# 18. Defensive copy
copy_knowledge = get_python_knowledge()
copy_knowledge["duration_hours"] = 999
assert get_python_knowledge()["duration_hours"] == 40

print("MASTER KB BATCH 13: 18/18 PASSED")
