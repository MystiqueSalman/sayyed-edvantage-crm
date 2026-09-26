from Sayyed_EdVantage_Master_KB_BATCH14 import (
    LINUX_COURSE_ID,
    LINUX_SOURCE_ID,
    LINUX_OFFERING_ID,
    get_linux_knowledge,
    get_linux_commercial_knowledge,
    validate_linux_knowledge,
    build_master_kb_with_linux,
)

# 1. Standalone validation
report = validate_linux_knowledge()
assert report["valid"] is True
assert report["errors"] == []

# 2. Integrated Master KB
kb = build_master_kb_with_linux()
assert kb.validate()["valid"] is True

# 3. Course identity
course = kb.get_course(LINUX_COURSE_ID)
assert course is not None
assert course.official_name == "Linux Administration – Professional Program"
assert course.category == "Linux"
assert course.status == "active"

# 4. Source duration inconsistency is preserved, not invented away
knowledge = get_linux_knowledge()
assert knowledge["declared_duration_hours"] == 40
assert knowledge["module_hours_total"] == 44
assert sum(m["hours"] for m in knowledge["modules"]) == 44
assert knowledge["source_consistency"]["status"] == "documented_source_inconsistency"

# 5. Level and mode
assert knowledge["level"] == "Beginner to Intermediate"
assert knowledge["mode"] == "Instructor-Led / Online Live"

# 6. Prerequisites
assert knowledge["prerequisites"]["prior_linux_experience_required"] is False
assert "Basic computer knowledge" in knowledge["prerequisites"]["required"]
assert "Logical thinking" in knowledge["prerequisites"]["required"]

# 7. Exact 12-module curriculum
assert len(knowledge["modules"]) == 12
assert knowledge["modules"][0]["title"] == "Linux Fundamentals & OS Concepts"
assert knowledge["modules"][1]["title"] == "Command Line & Filesystem"
assert knowledge["modules"][7]["title"] == "Networking & Remote Admin"
assert knowledge["modules"][9]["title"] == "Shell Scripting & Automation"
assert knowledge["modules"][11]["title"] == "Server Project/Portfolio/Career"

# 8. Projects
assert len(knowledge["projects"]) == 10
assert "Shell scripting and automation" in knowledge["projects"]
assert "Final server project / portfolio work" in knowledge["projects"]

# 9. Tools
assert len(knowledge["tools"]) == 16
assert "Linux" in knowledge["tools"]
assert "Ubuntu" in knowledge["tools"]
assert "Bash" in knowledge["tools"]
assert "SSH" in knowledge["tools"]
assert "systemd" in knowledge["tools"]
assert "cron" in knowledge["tools"]
assert "LVM" in knowledge["tools"]
assert "rsync" in knowledge["tools"]

# 10. Learning outcomes
assert len(knowledge["learning_outcomes"]) == 13
assert "Manage users, groups and access." in knowledge["learning_outcomes"]

# 11. Career safety
career = knowledge["career"]
assert "Linux administration" in career["preparation_areas"]
assert career["guarantees"]["employment"] is False
assert career["guarantees"]["placement"] is False
assert career["guarantees"]["salary"] is False
assert career["guarantees"]["income"] is False

# 12. DevOps boundary
assert knowledge["boundaries"]["devops_boundary"] is True

# 13. Certification remains unspecified
assert knowledge["certification"]["status"] == "unknown"
assert knowledge["certification"]["issuer"] is None
assert knowledge["certification"]["certificate_title"] is None

# 14. Source registration
assert LINUX_SOURCE_ID in course.source_ids
source = kb.sources[LINUX_SOURCE_ID]
assert source.status == "approved"
assert source.version == "1.0"

# 15. India commercial knowledge
commercial = get_linux_commercial_knowledge()
assert commercial["pricing_regions"]["india"]["base_fee"] == 25000
assert commercial["pricing_regions"]["india"]["currency"] == "INR"

# 16. International pricing safety
international = commercial["pricing_regions"]["international"]
assert international["base_fee"] is None
assert international["currency"] is None
assert "Do not substitute Indian pricing" in international["quote_policy"]

# 17. Offering registration
offering = kb.get_offering(LINUX_OFFERING_ID)
assert offering is not None
assert offering.pricing_regions["india"]["base_fee"] == 25000
assert offering.pricing_regions["international"]["base_fee"] is None

# 18. Previous courses and safety layers remain intact
assert kb.get_course("SE-DSP-001") is not None
assert kb.get_course("SE-DA-001") is not None
assert kb.get_course("SE-AIGEN-001") is not None
assert kb.get_course("SE-PY-001") is not None
assert kb.get_common_knowledge("conflict_control")["enabled"] is True
assert kb.get_common_knowledge("safety_contract")["execution_allowed"] is False

# 19. Defensive copy
copy_knowledge = get_linux_knowledge()
copy_knowledge["declared_duration_hours"] = 999
assert get_linux_knowledge()["declared_duration_hours"] == 40

print("MASTER KB BATCH 14: 19/19 PASSED")
