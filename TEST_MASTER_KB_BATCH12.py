from Sayyed_EdVantage_Master_KB_BATCH12 import (
    AI_GENAI_COURSE_ID,
    AI_GENAI_SOURCE_ID,
    AI_GENAI_OFFERING_ID,
    get_ai_genai_knowledge,
    get_ai_genai_commercial_knowledge,
    validate_ai_genai_knowledge,
    build_master_kb_with_ai_genai,
)

# 1. Standalone knowledge validation
report = validate_ai_genai_knowledge()
assert report["valid"] is True
assert report["errors"] == []

# 2. Build integrated Master KB
kb = build_master_kb_with_ai_genai()
assert kb.validate()["valid"] is True

# 3. Course identity
course = kb.get_course(AI_GENAI_COURSE_ID)
assert course is not None
assert course.official_name == "AI + Generative AI – Professional Program"
assert course.category == "Artificial Intelligence / Generative AI"
assert course.status == "active"

# 4. Duration, level and mode
knowledge = get_ai_genai_knowledge()
assert knowledge["duration_hours"] == 60
assert knowledge["level"] == "Intermediate to Advanced"
assert knowledge["mode"] == "Instructor-Led / Online Live"
assert knowledge["source_consistency"]["declared_total_hours"] == 60
assert knowledge["source_consistency"]["module_hours_total"] == 59
assert knowledge["source_consistency"]["status"] == "documented_source_inconsistency"

# 5. Prerequisites
assert knowledge["prerequisites"]["prior_programming_required"] is True
assert "Basic Python programming knowledge" in knowledge["prerequisites"]["recommended"]
assert "Basic understanding of Data Science and Machine Learning is strongly recommended" in knowledge["prerequisites"]["recommended"]

# 6. Exact 16-module curriculum and 60 hours
assert len(knowledge["modules"]) == 16
assert sum(m["hours"] for m in knowledge["modules"]) == 59
# The source declares 60 hours separately; the discrepancy is preserved,
# not silently corrected.
assert knowledge["modules"][0]["title"] == "AI Foundations & Modern AI Ecosystem"
assert knowledge["modules"][4]["title"] == "Generative AI Fundamentals"
assert knowledge["modules"][9]["title"] == "RAG"
assert knowledge["modules"][10]["title"] == "LangGraph & Agentic AI"
assert knowledge["modules"][15]["title"] == "AI Product Development, Portfolio & Career Lab"

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
assert len(knowledge["tools"]) == 20
assert "Python" in knowledge["tools"]
assert "OpenAI APIs" in knowledge["tools"]
assert "LangChain" in knowledge["tools"]
assert "LangGraph" in knowledge["tools"]
assert "ChromaDB" in knowledge["tools"]
assert "FAISS" in knowledge["tools"]
assert "LangSmith" in knowledge["tools"]

# 9. Projects
assert len(knowledge["projects"]) == 13
assert "End-to-End AI Product" in knowledge["projects"]
assert "RAG application" in knowledge["projects"]

# 10. Career safety
career = knowledge["career"]
assert "AI application development" in career["preparation_areas"]
assert career["guarantees"]["employment"] is False
assert career["guarantees"]["placement"] is False
assert career["guarantees"]["salary"] is False
assert career["guarantees"]["income"] is False

# 11. Advanced AI boundaries
boundaries = knowledge["boundaries"]
assert "RAG" in boundaries["advanced_topics"]
assert "Agentic AI" in boundaries["advanced_topics"]
assert "LLMOps" in boundaries["advanced_topics"]

# 12. Eligibility
assert knowledge["eligibility"]["prior_programming_required"] is True
assert "Python" in knowledge["eligibility"]["required"]

# 13. Certification remains unspecified
assert knowledge["certification"]["status"] == "unknown"
assert knowledge["certification"]["issuer"] is None
assert knowledge["certification"]["certificate_title"] is None

# 14. Source registration and provenance
assert AI_GENAI_SOURCE_ID in course.source_ids
source = kb.sources[AI_GENAI_SOURCE_ID]
assert source.status == "approved"
assert source.version == "1.0"

# 15. India commercial knowledge
commercial = get_ai_genai_commercial_knowledge()
assert commercial["pricing_regions"]["india"]["base_fee"] == 70000
assert commercial["pricing_regions"]["india"]["currency"] == "INR"

# 16. International pricing safety
international = commercial["pricing_regions"]["international"]
assert international["base_fee"] is None
assert international["currency"] is None
assert "Do not substitute Indian pricing" in international["quote_policy"]

# 17. Offering registered correctly
offering = kb.get_offering(AI_GENAI_OFFERING_ID)
assert offering is not None
assert offering.pricing_regions["india"]["base_fee"] == 70000
assert offering.pricing_regions["international"]["base_fee"] is None

# 18. Previous courses and safety layers remain intact
ds = kb.get_course("SE-DSP-001")
da = kb.get_course("SE-DA-001")
assert ds is not None
assert da is not None
assert ds.knowledge["total_duration_hours"] == 60
assert da.knowledge["duration_hours"] == 60
assert course.knowledge["source_consistency"]["status"] == "documented_source_inconsistency"
assert ds.knowledge["retrieval_metadata"]["enabled"] is True
assert kb.get_common_knowledge("conflict_control")["enabled"] is True
assert kb.get_common_knowledge("safety_contract")["execution_allowed"] is False

# 19. Defensive copy
copy_knowledge = get_ai_genai_knowledge()
copy_knowledge["duration_hours"] = 999
assert get_ai_genai_knowledge()["duration_hours"] == 60

print("MASTER KB BATCH 12: 19/19 PASSED")
