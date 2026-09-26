from Sayyed_EdVantage_Master_KB_BATCH07 import (
    CERTIFICATION_KNOWLEDGE, PROGRAM_INFORMATION, ANSWER_SAFETY_RULES,
    get_certification_knowledge, get_program_information,
    get_answer_safety_rules, validate_batch07, build_master_kb_with_batch07
)

# 1. Batch validation
report = validate_batch07()
assert report["valid"] is True

# 2. Certification is explicitly unknown
cert = get_certification_knowledge()
assert cert["course_id"] == "SE-DSP-001"
assert cert["status"] == "unknown"
for field in (
    "certificate_title", "certificate_type", "issuing_body",
    "accrediting_body", "award_conditions", "validity",
    "verification_method"
):
    assert cert[field] is None

# 3. Certification safety wording exists
assert "Do not invent" in cert["agent_rule"]
assert "admissions/team" in cert["agent_rule"]

# 4. Program information
program = get_program_information()
assert program["official_name"] == "Data Science – Professional Program"
assert program["duration_hours"] == 60
assert program["level"] == "Beginner to Intermediate"
assert program["mode"] == "Instructor-Led / Online Live"
assert "No prior programming experience required" in program["prerequisites"]

# 5. AI-program boundary
assert "AI + Generative AI" in program["relationship_to_ai_program"]

# 6. Safety rules
rules = get_answer_safety_rules()
assert rules["source_grounding"] is True
assert rules["no_invention"] is True
assert rules["certification_unknown"] is True
assert rules["no_job_guarantee"] is True
assert rules["no_salary_guarantee"] is True
assert rules["no_placement_guarantee"] is True

# 7. Commercial safety inherited
assert rules["commercial_region_awareness"] is True
assert rules["international_fee_no_india_fallback"] is True

# 8. Execution safety
assert rules["execution_allowed"] is False
assert rules["message_send_allowed"] is False
assert rules["external_action_allowed"] is False
assert rules["crm_write_allowed"] is False

# 9. Defensive copies
cert_copy = get_certification_knowledge()
cert_copy["status"] = "TAMPERED"
assert CERTIFICATION_KNOWLEDGE["status"] == "unknown"

program_copy = get_program_information()
program_copy["duration_hours"] = 1
assert PROGRAM_INFORMATION["duration_hours"] == 60

# 10. Master KB integration
kb = build_master_kb_with_batch07()
course = kb.get_course("SE-DSP-001")
assert course is not None
assert course.knowledge["certification_knowledge"]["status"] == "unknown"
assert course.knowledge["program_information"]["duration_hours"] == 60
assert course.knowledge["answer_safety_rules"]["no_invention"] is True

# 11. Previous layers remain intact
assert course.knowledge["total_duration_hours"] == 60
assert len(course.knowledge["detailed_curriculum"]["modules"]) == 14
assert len(course.knowledge["project_knowledge"]) == 9
assert course.knowledge["commercial_knowledge"]["india"]["base_fee"] == 50000
assert course.knowledge["commercial_knowledge"]["international"]["base_fee"] is None

# 12. Master validation
assert kb.validate()["valid"] is True

print("MASTER KB BATCH 07: 12/12 PASSED")
