from Sayyed_EdVantage_Master_KB_BATCH05 import (
    ELIGIBILITY_KNOWLEDGE, CAREER_KNOWLEDGE, BOUNDARY_KNOWLEDGE,
    get_eligibility_knowledge, get_career_knowledge, get_boundary_knowledge,
    validate_batch05, build_master_kb_with_batch05
)

# 1. Batch validation
report = validate_batch05()
assert report["valid"] is True

# 2. Eligibility identity and level
assert ELIGIBILITY_KNOWLEDGE["course_id"] == "SE-DSP-001"
assert ELIGIBILITY_KNOWLEDGE["level"] == "Beginner to Intermediate"
assert ELIGIBILITY_KNOWLEDGE["mode"] == "Instructor-Led / Online Live"

# 3. Required prerequisites
required = ELIGIBILITY_KNOWLEDGE["prerequisites"]["required"]
assert "Basic computer knowledge" in required
assert "Logical thinking" in required
assert ELIGIBILITY_KNOWLEDGE["prerequisites"]["programming_experience_required"] is False
assert "No prior programming experience required" in ELIGIBILITY_KNOWLEDGE["prerequisites"]["statement"]

# 4. Unspecified fields stay unspecified
assert len(ELIGIBILITY_KNOWLEDGE["not_specified_by_source"]) == 5
assert "Minimum academic qualification" in ELIGIBILITY_KNOWLEDGE["not_specified_by_source"]
assert "Minimum age" in ELIGIBILITY_KNOWLEDGE["not_specified_by_source"]
assert "Work experience requirement" in ELIGIBILITY_KNOWLEDGE["not_specified_by_source"]

# 5. Career skills
skills = get_career_knowledge()["core_career_skills"]
assert "Python programming" in skills
assert "SQL and data extraction" in skills
assert "Machine learning" in skills
assert "Model evaluation" in skills

# 6. Career preparation
prep = get_career_knowledge()["career_preparation"]
assert "GitHub portfolio development" in prep
assert "Technical interview preparation" in prep
assert "Mock interview" in prep
assert "Technical presentation" in prep

# 7. Career safety
unsupported = CAREER_KNOWLEDGE["unsupported_claims"]
assert "Guaranteed employment" in unsupported
assert "Guaranteed placement" in unsupported
assert "Guaranteed salary" in unsupported
assert "Guaranteed income" in unsupported

# 8. Boundaries
excluded = get_boundary_knowledge()["advanced_ai_topics_excluded"]
for topic in ("LangChain", "LangGraph", "RAG", "Agentic AI", "LLMOps", "Advanced Generative AI"):
    assert topic in excluded

# 9. Defensive copies
elig = get_eligibility_knowledge()
elig["level"] = "TAMPERED"
assert ELIGIBILITY_KNOWLEDGE["level"] == "Beginner to Intermediate"

career = get_career_knowledge()
career["core_career_skills"].append("TAMPERED")
assert "TAMPERED" not in CAREER_KNOWLEDGE["core_career_skills"]

# 10. Master KB integration
kb = build_master_kb_with_batch05()
course = kb.get_course("SE-DSP-001")
assert course is not None
assert course.knowledge["eligibility_knowledge"]["prerequisites"]["programming_experience_required"] is False
assert "Machine learning" in course.knowledge["career_knowledge"]["core_career_skills"]
assert "RAG" in course.knowledge["boundary_knowledge"]["advanced_ai_topics_excluded"]

# 11. Previous KB layers remain intact
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["detailed_curriculum"]["modules"]) == 14
assert len(course.knowledge["project_knowledge"]) == 9

# 12. Master validation
assert kb.validate()["valid"] is True

print("MASTER KB BATCH 05: 12/12 PASSED")
