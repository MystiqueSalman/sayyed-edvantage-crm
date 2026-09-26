from Sayyed_EdVantage_Master_KB_BATCH16 import (
    EHC_COURSE_ID,
    EHC_SOURCE_ID,
    EHC_OFFERING_ID,
    get_ehc_knowledge,
    get_ehc_commercial_knowledge,
    validate_ehc_knowledge,
    build_master_kb_with_ehc,
)

# 1. Standalone validation
report = validate_ehc_knowledge()
assert report["valid"] is True
assert report["errors"] == []

# 2. Integrated Master KB
kb = build_master_kb_with_ehc()
assert kb.validate()["valid"] is True

# 3. Course identity
course = kb.get_course(EHC_COURSE_ID)
assert course is not None
assert course.official_name == "Ethical Hacking & Cybersecurity – Professional Program"
assert course.category == "Ethical Hacking & Cybersecurity"
assert course.status == "active"

# 4. Source program status is preserved separately
knowledge = get_ehc_knowledge()
assert knowledge["source_program_status"] == "Curriculum Design / Proposed"

# 5. Duration, level and mode
assert knowledge["duration_hours"] == 60
assert knowledge["level"] == "Beginner to Intermediate to Advanced"
assert knowledge["mode"] == "Instructor-Led / Online Live"

# 6. Prerequisites
assert knowledge["prerequisites"]["prior_cybersecurity_or_ethical_hacking_required"] is False
assert "Basic computer knowledge" in knowledge["prerequisites"]["required"]
assert "Logical thinking" in knowledge["prerequisites"]["required"]
assert "Basic Linux" in knowledge["prerequisites"]["helpful_but_not_mandatory"]

# 7. Exact 15-module curriculum and 60 hours
assert len(knowledge["modules"]) == 15
assert sum(m["hours"] for m in knowledge["modules"]) == 60
assert knowledge["modules"][0]["title"] == "Cybersecurity Foundations & Security Mindset"
assert knowledge["modules"][5]["title"] == "Recon/OSINT/Information Gathering"
assert knowledge["modules"][7]["title"] == "Web Application Security & OWASP"
assert knowledge["modules"][8]["title"] == "Ethical Hacking Methodology & Pen Testing"
assert knowledge["modules"][14]["title"] == "Final Ethical Hacking & Cybersecurity Capstone"

# 8. Tools
assert len(knowledge["tools"]) == 13
assert "Nmap" in knowledge["tools"]
assert "Wireshark" in knowledge["tools"]
assert "Burp" in knowledge["tools"]
assert "OWASP ZAP" in knowledge["tools"]
assert "Metasploit concepts" in knowledge["tools"]
assert "CTF" in knowledge["tools"]

# 9. Learning outcomes
assert len(knowledge["learning_outcomes"]) == 15
assert "Understand web application security and OWASP concepts." in knowledge["learning_outcomes"]

# 10. Career safety
career = knowledge["career"]
assert "Cybersecurity foundations" in career["preparation_areas"]
assert career["guarantees"]["employment"] is False
assert career["guarantees"]["placement"] is False
assert career["guarantees"]["salary"] is False
assert career["guarantees"]["income"] is False

# 11. Authorized-environment safety
boundaries = knowledge["boundaries"]
assert boundaries["authorized_environment_only"] is True
assert "Authorized labs" in boundaries["allowed_environments"]
assert "CTFs" in boundaries["allowed_environments"]
assert "Virtual machines" in boundaries["allowed_environments"]
assert "Unauthorized access" in boundaries["prohibited"]
assert "Unauthorized testing" in boundaries["prohibited"]

# 12. Certification remains unspecified
assert knowledge["certification"]["status"] == "unknown"
assert knowledge["certification"]["issuer"] is None
assert knowledge["certification"]["certificate_title"] is None

# 13. Assessment is not invented
assert knowledge["assessment"]["status"] == "not_specified_in_source"
assert knowledge["assessment"]["details"] is None

# 14. Project information does not invent missing project details
assert knowledge["project_detail"]["capstone_present"] is True
assert knowledge["project_detail"]["capstone_title"] == "Final Ethical Hacking & Cybersecurity Capstone"
assert knowledge["project_detail"]["status"] == "not_fully_specified_in_source"

# 15. Source registration
assert EHC_SOURCE_ID in course.source_ids
source = kb.sources[EHC_SOURCE_ID]
assert source.status == "approved"
assert source.version == "1.0"

# 16. India commercial knowledge
commercial = get_ehc_commercial_knowledge()
assert commercial["pricing_regions"]["india"]["base_fee"] == 60000
assert commercial["pricing_regions"]["india"]["currency"] == "INR"

# 17. International pricing safety
international = commercial["pricing_regions"]["international"]
assert international["base_fee"] is None
assert international["currency"] is None
assert "Do not substitute Indian pricing" in international["quote_policy"]

# 18. Offering registration
offering = kb.get_offering(EHC_OFFERING_ID)
assert offering is not None
assert offering.pricing_regions["india"]["base_fee"] == 60000
assert offering.pricing_regions["international"]["base_fee"] is None

# 19. All seven individual courses are now present
for course_id in [
    "SE-DSP-001",
    "SE-DA-001",
    "SE-AIGEN-001",
    "SE-PY-001",
    "SE-LINUX-001",
    "SE-DEVOPS-001",
    "SE-EHC-001",
]:
    assert kb.get_course(course_id) is not None

# 20. Previous safety layers remain intact
assert kb.get_common_knowledge("conflict_control")["enabled"] is True
assert kb.get_common_knowledge("safety_contract")["execution_allowed"] is False
assert kb.get_common_knowledge("safety_contract")["message_sending_allowed"] is False
assert kb.get_common_knowledge("safety_contract")["external_actions_allowed"] is False
assert kb.get_common_knowledge("safety_contract")["crm_write_allowed"] is False

# 21. Defensive copy
copy_knowledge = get_ehc_knowledge()
copy_knowledge["duration_hours"] = 999
assert get_ehc_knowledge()["duration_hours"] == 60

print("MASTER KB BATCH 16: 21/21 PASSED")
