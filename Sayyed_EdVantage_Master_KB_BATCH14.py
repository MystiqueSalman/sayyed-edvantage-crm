from copy import deepcopy
from typing import Any, Dict, List

LINUX_COURSE_ID = "SE-LINUX-001"
LINUX_SOURCE_ID = "LINUX-CURRICULUM-SOURCE-001"
LINUX_OFFERING_ID = "LINUX-OFFERING-INDIA-001"

LINUX_KNOWLEDGE: Dict[str, Any] = {
    "course_id": LINUX_COURSE_ID,
    "official_name": "Linux Administration – Professional Program",
    "category": "Linux",
    "status": "active",
    "declared_duration_hours": 40,
    "module_hours_total": 44,
    "source_consistency": {
        "status": "documented_source_inconsistency",
        "declared_duration_hours": 40,
        "module_hours_total": 44,
        "action": (
            "Do not silently change or rebalance the supplied curriculum. "
            "Preserve both values and route conflicting duration questions "
            "to the appropriate admissions/faculty source."
        ),
    },
    "level": "Beginner to Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "required": ["Basic computer knowledge", "Logical thinking"],
        "prior_linux_experience_required": False,
        "helpful_but_not_mandatory": [],
    },
    "modules": [
        {"number": 1, "title": "Linux Fundamentals & OS Concepts", "hours": 3},
        {"number": 2, "title": "Command Line & Filesystem", "hours": 5},
        {"number": 3, "title": "Filesystem, Links & Permissions", "hours": 4},
        {"number": 4, "title": "Users, Groups & Access", "hours": 4},
        {"number": 5, "title": "Processes, Jobs & Monitoring", "hours": 4},
        {"number": 6, "title": "Package Management", "hours": 3},
        {"number": 7, "title": "Storage & Filesystem Admin", "hours": 4},
        {"number": 8, "title": "Networking & Remote Admin", "hours": 4},
        {"number": 9, "title": "Services/Systemd/Server Admin", "hours": 3},
        {"number": 10, "title": "Shell Scripting & Automation", "hours": 4},
        {"number": 11, "title": "Security/Logs/Troubleshooting", "hours": 3},
        {"number": 12, "title": "Server Project/Portfolio/Career", "hours": 3},
    ],
    "projects": [
        "Linux server administration work",
        "Command-line and filesystem administration tasks",
        "Permissions, users and groups administration",
        "Process and system monitoring work",
        "Storage and filesystem administration work",
        "Networking and remote administration work",
        "Systemd/service administration",
        "Shell scripting and automation",
        "Security, logs and troubleshooting work",
        "Final server project / portfolio work",
    ],
    "tools": [
        "Linux",
        "Ubuntu",
        "Bash",
        "SSH",
        "Git",
        "GitHub",
        "systemd",
        "cron",
        "apt",
        "dnf/yum concepts",
        "LVM",
        "firewall concepts",
        "grep",
        "sed",
        "awk",
        "rsync",
    ],
    "learning_outcomes": [
        "Understand Linux fundamentals and operating-system concepts.",
        "Use the Linux command line effectively.",
        "Navigate and manage Linux filesystems.",
        "Apply filesystem links and permissions.",
        "Manage users, groups and access.",
        "Monitor processes and system activity.",
        "Manage software packages.",
        "Administer storage and filesystems.",
        "Configure and troubleshoot networking and remote access.",
        "Manage services and systemd.",
        "Write shell scripts and automate administrative tasks.",
        "Use logs, security practices and troubleshooting techniques.",
        "Complete a Linux server administration project and portfolio work.",
    ],
    "career": {
        "preparation_areas": [
            "Linux administration",
            "Server administration",
            "Shell scripting",
            "System troubleshooting",
            "Remote administration",
            "Infrastructure foundations",
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
            "This program focuses on Linux operating-system and server "
            "administration foundations. DevOps-specific curriculum belongs "
            "to the dedicated DevOps program."
        ),
        "devops_boundary": True,
    },
    "eligibility": {
        "required": ["Basic computer knowledge", "Logical thinking"],
        "prior_linux_experience_required": False,
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

LINUX_COMMERCIAL_KNOWLEDGE: Dict[str, Any] = {
    "offering_id": LINUX_OFFERING_ID,
    "name": "Linux",
    "offering_type": "course",
    "pricing_regions": {
        "india": {
            "status": "verified_user_supplied",
            "currency": "INR",
            "base_fee": 25000,
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


def validate_linux_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    modules = LINUX_KNOWLEDGE["modules"]
    assessment_note = "No assessment percentages were supplied in the source record."

    if len(modules) != 12:
        errors.append("Linux must contain 12 modules.")
    if sum(m["hours"] for m in modules) != 44:
        errors.append("The supplied Linux module hours must total 44.")
    if LINUX_KNOWLEDGE["declared_duration_hours"] != 40:
        errors.append("The source-declared duration must remain 40 hours.")
    if LINUX_KNOWLEDGE["module_hours_total"] != 44:
        errors.append("The documented module-hours total must remain 44.")
    if LINUX_KNOWLEDGE["source_consistency"]["status"] != "documented_source_inconsistency":
        errors.append("Linux duration inconsistency must be explicitly documented.")
    if len(LINUX_KNOWLEDGE["tools"]) != 16:
        errors.append("Tool list must contain 16 entries.")
    if LINUX_KNOWLEDGE["certification"]["status"] != "unknown":
        errors.append("Certification must remain unknown because source details are unspecified.")
    if LINUX_COMMERCIAL_KNOWLEDGE["pricing_regions"]["india"]["base_fee"] != 25000:
        errors.append("India Linux fee must be ₹25,000.")
    if LINUX_COMMERCIAL_KNOWLEDGE["pricing_regions"]["international"]["base_fee"] is not None:
        errors.append("International Linux fee must remain unknown.")

    return {
        "valid": not errors,
        "errors": errors,
        "assessment_note": assessment_note,
    }


def add_linux_to_master_kb(kb):
    report = validate_linux_knowledge()
    if not report["valid"]:
        raise ValueError(report["errors"])

    from Sayyed_EdVantage_Master_KB_BATCH01 import CourseRecord, CommercialOffering, SourceRecord

    kb.register_source(SourceRecord(
        source_id=LINUX_SOURCE_ID,
        title="Linux Administration Professional Program Curriculum",
        source_type="course_curriculum",
        version="1.0",
        status="approved",
        course_id=LINUX_COURSE_ID,
        notes=(
            "Source-derived Linux curriculum. Source declares 40 hours while "
            "the detailed module table totals 44 hours; inconsistency preserved."
        ),
    ))

    kb.register_course(CourseRecord(
        course_id=LINUX_COURSE_ID,
        official_name=LINUX_KNOWLEDGE["official_name"],
        category=LINUX_KNOWLEDGE["category"],
        status="active",
        knowledge=deepcopy(LINUX_KNOWLEDGE),
        source_ids=[LINUX_SOURCE_ID],
    ))

    kb.register_offering(CommercialOffering(
        offering_id=LINUX_OFFERING_ID,
        name="Linux",
        offering_type="course",
        pricing_regions=deepcopy(LINUX_COMMERCIAL_KNOWLEDGE["pricing_regions"]),
        source_ids=[LINUX_SOURCE_ID],
    ))

    return kb


def get_linux_knowledge() -> Dict[str, Any]:
    return deepcopy(LINUX_KNOWLEDGE)


def get_linux_commercial_knowledge() -> Dict[str, Any]:
    return deepcopy(LINUX_COMMERCIAL_KNOWLEDGE)


def build_master_kb_with_linux():
    from Sayyed_EdVantage_Master_KB_BATCH13 import build_master_kb_with_python
    return add_linux_to_master_kb(build_master_kb_with_python())
