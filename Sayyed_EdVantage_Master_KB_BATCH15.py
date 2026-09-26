from copy import deepcopy
from typing import Any, Dict, List

DEVOPS_COURSE_ID = "SE-DEVOPS-001"
DEVOPS_SOURCE_ID = "DEVOPS-CURRICULUM-SOURCE-001"
DEVOPS_OFFERING_ID = "DEVOPS-OFFERING-INDIA-001"

DEVOPS_KNOWLEDGE: Dict[str, Any] = {
    "course_id": DEVOPS_COURSE_ID,
    "official_name": "DevOps Professional Program",
    "category": "DevOps",
    "status": "active",
    "duration_hours": 60,
    "level": "Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "recommended": [
            "Basic Linux",
            "Basic Git",
            "Programming / scripting familiarity",
        ],
        "linux_recommended": True,
        "git_helpful": True,
        "programming_scripting_helpful": True,
    },
    "modules": [
        {"number": 1, "title": "DevOps Foundations & Software Delivery Lifecycle", "hours": 3},
        {"number": 2, "title": "Linux for DevOps & Shell Automation", "hours": 5},
        {"number": 3, "title": "Git/GitHub/SCM", "hours": 4},
        {"number": 4, "title": "CI/CD Fundamentals & Pipeline Design", "hours": 5},
        {"number": 5, "title": "Jenkins & GitLab CI/CD", "hours": 5},
        {"number": 6, "title": "Docker & Containerization", "hours": 6},
        {"number": 7, "title": "Kubernetes & Container Orchestration", "hours": 7},
        {"number": 8, "title": "Terraform", "hours": 5},
        {"number": 9, "title": "Ansible", "hours": 4},
        {"number": 10, "title": "Cloud Infrastructure for DevOps", "hours": 5},
        {"number": 11, "title": "Monitoring/Logging/Observability", "hours": 4},
        {"number": 12, "title": "DevSecOps/Reliability/Production Troubleshooting", "hours": 4},
        {"number": 13, "title": "End-to-End DevOps Project & Career Lab", "hours": 3},
    ],
    "projects": [
        "Linux automation project",
        "Git workflow project",
        "CI/CD pipeline project",
        "Dockerized application",
        "Kubernetes project",
        "Terraform infrastructure project",
        "Ansible automation project",
        "Cloud deployment project",
        "Monitoring dashboard project",
        "Production troubleshooting project",
        "Final end-to-end DevOps platform",
    ],
    "assessment": {
        "quizzes_and_assignments_percent": 15,
        "hands_on_labs_percent": 25,
        "mini_projects_percent": 15,
        "case_study_problem_solving_percent": 10,
        "capstone_percent": 10,
        "presentation_and_viva_percent": 15,
        "career_lab_percent": 10,
        "total_percent": 100,
    },
    "tools": [
        "Linux",
        "Bash",
        "Git/GitHub",
        "Jenkins",
        "GitLab CI/CD",
        "Docker/Compose",
        "Kubernetes/kubectl",
        "Terraform",
        "Ansible",
        "AWS/Azure/GCP",
        "Prometheus/Grafana",
    ],
    "learning_outcomes": [
        "Understand DevOps principles and the software delivery lifecycle.",
        "Use Linux and shell automation in DevOps workflows.",
        "Apply Git and GitHub source-control practices.",
        "Design CI/CD pipelines.",
        "Work with Jenkins and GitLab CI/CD.",
        "Build and manage Docker containers.",
        "Deploy and manage workloads with Kubernetes.",
        "Provision infrastructure with Terraform.",
        "Automate configuration and administration with Ansible.",
        "Understand cloud infrastructure for DevOps.",
        "Use monitoring, logging and observability practices.",
        "Apply DevSecOps, reliability and production troubleshooting concepts.",
        "Complete an end-to-end DevOps project and career lab.",
    ],
    "career": {
        "preparation_areas": [
            "DevOps",
            "CI/CD",
            "Containerization",
            "Kubernetes",
            "Infrastructure as Code",
            "Configuration automation",
            "Cloud infrastructure",
            "Monitoring and observability",
            "Production troubleshooting",
        ],
        "guarantees": {
            "employment": False,
            "placement": False,
            "salary": False,
            "income": False,
        },
    },
    "boundaries": {
        "note": (
            "This is the dedicated DevOps program. Linux administration "
            "foundations are covered in the Linux program, while advanced AI "
            "and Generative AI belong to the dedicated AI + Generative AI program."
        ),
        "not_core": [
            "Advanced AI",
            "Generative AI",
            "LLM application development",
            "RAG",
            "Agentic AI",
        ],
    },
    "eligibility": {
        "recommended": [
            "Basic Linux",
            "Basic Git",
            "Programming / scripting familiarity",
        ],
        "unspecified": [
            "Minimum academic qualification",
            "Minimum age",
            "Work experience requirement",
            "English-language requirement",
            "Entrance examination",
        ],
    },
    "certification": {
        "status": "unknown",
        "certificate_title": None,
        "issuer": None,
        "accreditation": None,
        "conditions": None,
        "validity": None,
        "verification": None,
    },
}

DEVOPS_COMMERCIAL_KNOWLEDGE: Dict[str, Any] = {
    "offering_id": DEVOPS_OFFERING_ID,
    "name": "DevOps",
    "offering_type": "course",
    "pricing_regions": {
        "india": {
            "status": "verified_user_supplied",
            "currency": "INR",
            "base_fee": 45000,
            "tax_note": "GST/tax applicability and final payable amount should be confirmed by admissions.",
            "discount": None,
            "payment_plan": None,
            "final_fee": None,
            "quote_policy": "Admissions/team confirms final fee and applicable options.",
        },
        "international": {
            "status": "unknown",
            "currency": None,
            "base_fee": None,
            "tax_note": None,
            "discount": None,
            "payment_plan": None,
            "final_fee": None,
            "quote_policy": "Do not substitute Indian pricing; admissions/team provides applicable international fee/details.",
        },
    },
    "commercial_safety": {
        "india_only_verified": True,
        "never_substitute_india_for_international": True,
        "no_invention": True,
    },
}


def validate_devops_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    modules = DEVOPS_KNOWLEDGE["modules"]
    assessment = DEVOPS_KNOWLEDGE["assessment"]
    components = [
        assessment["quizzes_and_assignments_percent"],
        assessment["hands_on_labs_percent"],
        assessment["mini_projects_percent"],
        assessment["case_study_problem_solving_percent"],
        assessment["capstone_percent"],
        assessment["presentation_and_viva_percent"],
        assessment["career_lab_percent"],
    ]

    if len(modules) != 13:
        errors.append("DevOps must contain 13 modules.")
    if sum(m["hours"] for m in modules) != 60:
        errors.append("Module hours must total 60.")
    if DEVOPS_KNOWLEDGE["duration_hours"] != 60:
        errors.append("Duration must be 60 hours.")
    if sum(components) != 100:
        errors.append("Assessment component percentages must total 100.")
    if assessment["total_percent"] != 100:
        errors.append("Assessment total_percent must be 100.")
    if len(DEVOPS_KNOWLEDGE["tools"]) != 11:
        errors.append("Tool list must contain 11 entries.")
    if DEVOPS_KNOWLEDGE["certification"]["status"] != "unknown":
        errors.append("Certification must remain unknown because source details are unspecified.")
    if DEVOPS_COMMERCIAL_KNOWLEDGE["pricing_regions"]["india"]["base_fee"] != 45000:
        errors.append("India DevOps fee must be ₹45,000.")
    if DEVOPS_COMMERCIAL_KNOWLEDGE["pricing_regions"]["international"]["base_fee"] is not None:
        errors.append("International DevOps fee must remain unknown.")

    return {"valid": not errors, "errors": errors}


def add_devops_to_master_kb(kb):
    report = validate_devops_knowledge()
    if not report["valid"]:
        raise ValueError(report["errors"])

    from Sayyed_EdVantage_Master_KB_BATCH01 import CourseRecord, CommercialOffering, SourceRecord

    kb.register_source(SourceRecord(
        source_id=DEVOPS_SOURCE_ID,
        title="DevOps Professional Program Curriculum",
        source_type="course_curriculum",
        version="1.0",
        status="approved",
        course_id=DEVOPS_COURSE_ID,
        notes="Source-derived DevOps curriculum record.",
    ))

    kb.register_course(CourseRecord(
        course_id=DEVOPS_COURSE_ID,
        official_name=DEVOPS_KNOWLEDGE["official_name"],
        category=DEVOPS_KNOWLEDGE["category"],
        status="active",
        knowledge=deepcopy(DEVOPS_KNOWLEDGE),
        source_ids=[DEVOPS_SOURCE_ID],
    ))

    kb.register_offering(CommercialOffering(
        offering_id=DEVOPS_OFFERING_ID,
        name="DevOps",
        offering_type="course",
        pricing_regions=deepcopy(DEVOPS_COMMERCIAL_KNOWLEDGE["pricing_regions"]),
        source_ids=[DEVOPS_SOURCE_ID],
    ))

    return kb


def get_devops_knowledge() -> Dict[str, Any]:
    return deepcopy(DEVOPS_KNOWLEDGE)


def get_devops_commercial_knowledge() -> Dict[str, Any]:
    return deepcopy(DEVOPS_COMMERCIAL_KNOWLEDGE)


def build_master_kb_with_devops():
    from Sayyed_EdVantage_Master_KB_BATCH14 import build_master_kb_with_linux
    return add_devops_to_master_kb(build_master_kb_with_linux())
