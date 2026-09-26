from Sayyed_EdVantage_Master_KB_BATCH15 import (
    DEVOPS_COURSE_ID,
    DEVOPS_SOURCE_ID,
    DEVOPS_OFFERING_ID,
    get_devops_knowledge,
    get_devops_commercial_knowledge,
    validate_devops_knowledge,
    build_master_kb_with_devops,
)

# 1. Standalone validation
report = validate_devops_knowledge()
assert report["valid"] is True
assert report["errors"] == []

# 2. Integrated Master KB
kb = build_master_kb_with_devops()
assert kb.validate()["valid"] is True

# 3. Course identity
course = kb.get_course(DEVOPS_COURSE_ID)
assert course is not None
assert course.official_name == "DevOps Professional Program"
assert course.category == "DevOps"
assert course.status == "active"

# 4. Duration, level and mode
knowledge = get_devops_knowledge()
assert knowledge["duration_hours"] == 60
assert knowledge["level"] == "Intermediate"
assert knowledge["mode"] == "Instructor-Led / Online Live"

# 5. Recommended prerequisites
assert knowledge["prerequisites"]["linux_recommended"] is True
assert knowledge["prerequisites"]["git_helpful"] is True
assert knowledge["prerequisites"]["programming_scripting_helpful"] is True
assert "Basic Linux" in knowledge["prerequisites"]["recommended"]

# 6. Exact 13-module curriculum and 60 hours
assert len(knowledge["modules"]) == 13
assert sum(m["hours"] for m in knowledge["modules"]) == 60
assert knowledge["modules"][0]["title"] == "DevOps Foundations & Software Delivery Lifecycle"
assert knowledge["modules"][5]["title"] == "Docker & Containerization"
assert knowledge["modules"][6]["title"] == "Kubernetes & Container Orchestration"
assert knowledge["modules"][7]["title"] == "Terraform"
assert knowledge["modules"][12]["title"] == "End-to-End DevOps Project & Career Lab"

# 7. Assessment
assessment = knowledge["assessment"]
assert sum([
    assessment["quizzes_and_assignments_percent"],
    assessment["hands_on_labs_percent"],
    assessment["mini_projects_percent"],
    assessment["case_study_problem_solving_percent"],
    assessment["capstone_percent"],
    assessment["presentation_and_viva_percent"],
    assessment["career_lab_percent"],
]) == 100
assert assessment["total_percent"] == 100

# 8. Tools
assert len(knowledge["tools"]) == 11
assert "Linux" in knowledge["tools"]
assert "Git/GitHub" in knowledge["tools"]
assert "Jenkins" in knowledge["tools"]
assert "GitLab CI/CD" in knowledge["tools"]
assert "Docker/Compose" in knowledge["tools"]
assert "Kubernetes/kubectl" in knowledge["tools"]
assert "Terraform" in knowledge["tools"]
assert "Ansible" in knowledge["tools"]
assert "AWS/Azure/GCP" in knowledge["tools"]
assert "Prometheus/Grafana" in knowledge["tools"]

# 9. Projects and learning outcomes
assert len(knowledge["projects"]) == 11
assert "Final end-to-end DevOps platform" in knowledge["projects"]
assert len(knowledge["learning_outcomes"]) == 13

# 10. Career safety
career = knowledge["career"]
assert "DevOps" in career["preparation_areas"]
assert career["guarantees"]["employment"] is False
assert career["guarantees"]["placement"] is False
assert career["guarantees"]["salary"] is False
assert career["guarantees"]["income"] is False

# 11. Boundaries
assert "Generative AI" in knowledge["boundaries"]["not_core"]
assert "RAG" in knowledge["boundaries"]["not_core"]
assert "Agentic AI" in knowledge["boundaries"]["not_core"]

# 12. Certification remains unspecified
assert knowledge["certification"]["status"] == "unknown"
assert knowledge["certification"]["issuer"] is None
assert knowledge["certification"]["certificate_title"] is None

# 13. Source registration
assert DEVOPS_SOURCE_ID in course.source_ids
source = kb.sources[DEVOPS_SOURCE_ID]
assert source.status == "approved"
assert source.version == "1.0"

# 14. India commercial knowledge
commercial = get_devops_commercial_knowledge()
assert commercial["pricing_regions"]["india"]["base_fee"] == 45000
assert commercial["pricing_regions"]["india"]["currency"] == "INR"

# 15. International pricing safety
international = commercial["pricing_regions"]["international"]
assert international["base_fee"] is None
assert international["currency"] is None
assert "Do not substitute Indian pricing" in international["quote_policy"]

# 16. Offering registration
offering = kb.get_offering(DEVOPS_OFFERING_ID)
assert offering is not None
assert offering.pricing_regions["india"]["base_fee"] == 45000
assert offering.pricing_regions["international"]["base_fee"] is None

# 17. Previous courses and safety layers remain intact
assert kb.get_course("SE-DSP-001") is not None
assert kb.get_course("SE-DA-001") is not None
assert kb.get_course("SE-AIGEN-001") is not None
assert kb.get_course("SE-PY-001") is not None
assert kb.get_course("SE-LINUX-001") is not None
assert kb.get_common_knowledge("conflict_control")["enabled"] is True
assert kb.get_common_knowledge("safety_contract")["execution_allowed"] is False

# 18. Defensive copy
copy_knowledge = get_devops_knowledge()
copy_knowledge["duration_hours"] = 999
assert get_devops_knowledge()["duration_hours"] == 60

print("MASTER KB BATCH 15: 18/18 PASSED")
