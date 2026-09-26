from copy import deepcopy
from typing import Any, Dict, List

EHC_COURSE_ID = "SE-EHC-001"
EHC_SOURCE_ID = "EHC-CURRICULUM-SOURCE-001"
EHC_OFFERING_ID = "EHC-OFFERING-INDIA-001"

EHC_KNOWLEDGE: Dict[str, Any] = {
    "course_id": EHC_COURSE_ID,
    "official_name": "Ethical Hacking & Cybersecurity – Professional Program",
    "category": "Ethical Hacking & Cybersecurity",
    "status": "active",
    "source_program_status": "Curriculum Design / Proposed",
    "duration_hours": 60,
    "level": "Beginner to Intermediate to Advanced",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "required": ["Basic computer knowledge", "Logical thinking"],
        "prior_cybersecurity_or_ethical_hacking_required": False,
        "helpful_but_not_mandatory": ["Basic Linux", "Basic networking"],
    },
    "modules": [
        {"number": 1, "title": "Cybersecurity Foundations & Security Mindset", "hours": 3},
        {"number": 2, "title": "Networking Fundamentals", "hours": 5},
        {"number": 3, "title": "Linux & Windows Security", "hours": 4},
        {"number": 4, "title": "Cryptography/Auth/Access Control", "hours": 4},
        {"number": 5, "title": "Threats/Attacks/Defense", "hours": 4},
        {"number": 6, "title": "Recon/OSINT/Information Gathering", "hours": 4},
        {"number": 7, "title": "Vulnerability Assessment/Security Scanning", "hours": 4},
        {"number": 8, "title": "Web Application Security & OWASP", "hours": 6},
        {"number": 9, "title": "Ethical Hacking Methodology & Pen Testing", "hours": 5},
        {"number": 10, "title": "Network Security & Ethical Network Testing", "hours": 4},
        {"number": 11, "title": "System Security & Privilege Escalation Concepts", "hours": 4},
        {"number": 12, "title": "Security Tools, CTFs & Controlled Labs", "hours": 3},
        {"number": 13, "title": "Defensive Security, SOC & Incident Response", "hours": 3},
        {"number": 14, "title": "Security Monitoring, Logs & Threat Detection", "hours": 3},
        {"number": 15, "title": "Final Ethical Hacking & Cybersecurity Capstone", "hours": 4},
    ],
    "tools": [
        "Linux/Ubuntu",
        "Windows",
        "TCP/IP",
        "DNS",
        "HTTP/S",
        "SSH",
        "Firewalls",
        "Nmap",
        "Wireshark",
        "Burp",
        "OWASP ZAP",
        "Metasploit concepts",
        "CTF",
    ],
    "learning_outcomes": [
        "Understand cybersecurity foundations and a security mindset.",
        "Understand core networking concepts relevant to cybersecurity.",
        "Apply Linux and Windows security concepts.",
        "Understand cryptography, authentication and access control.",
        "Recognize common threats, attacks and defensive concepts.",
        "Perform authorized reconnaissance, OSINT and information gathering.",
        "Understand vulnerability assessment and security scanning.",
        "Understand web application security and OWASP concepts.",
        "Apply an ethical hacking and penetration-testing methodology in authorized environments.",
        "Understand ethical network security testing.",
        "Understand system security and privilege-escalation concepts.",
        "Use security tools in controlled labs and CTF environments.",
        "Understand defensive security, SOC and incident-response concepts.",
        "Understand security monitoring, logs and threat detection.",
        "Complete a final ethical hacking and cybersecurity capstone in an authorized environment.",
    ],
    "career": {
        "preparation_areas": [
            "Cybersecurity foundations",
            "Ethical hacking",
            "Penetration testing concepts",
            "Web application security",
            "Network security",
            "Defensive security",
            "SOC concepts",
            "Incident response",
            "Security monitoring",
        ],
        "guarantees": {
            "employment": False,
            "placement": False,
            "salary": False,
            "income": False,
        },
    },
    "boundaries": {
        "authorized_environment_only": True,
        "allowed_environments": [
            "Authorized labs",
            "CTFs",
            "Virtual machines",
            "Systems with explicit permission",
        ],
        "prohibited": [
            "Unauthorized access",
            "Unauthorized testing",
            "Real-world systems without explicit permission",
        ],
        "note": (
            "Security testing must be limited to authorized environments, "
            "CTFs, virtual machines, or systems for which explicit permission exists."
        ),
    },
    "eligibility": {
        "required": ["Basic computer knowledge", "Logical thinking"],
        "prior_cybersecurity_or_ethical_hacking_required": False,
        "helpful_but_not_mandatory": ["Basic Linux", "Basic networking"],
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
    "assessment": {
        "status": "not_specified_in_source",
        "details": None,
    },
    "project_detail": {
        "status": "not_fully_specified_in_source",
        "capstone_present": True,
        "capstone_title": "Final Ethical Hacking & Cybersecurity Capstone",
    },
}

EHC_COMMERCIAL_KNOWLEDGE: Dict[str, Any] = {
    "offering_id": EHC_OFFERING_ID,
    "name": "Ethical Hacking & Cybersecurity",
    "offering_type": "course",
    "pricing_regions": {
        "india": {
            "status": "verified_user_supplied",
            "currency": "INR",
            "base_fee": 60000,
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


def validate_ehc_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    modules = EHC_KNOWLEDGE["modules"]

    if len(modules) != 15:
        errors.append("Ethical Hacking & Cybersecurity must contain 15 modules.")
    if sum(m["hours"] for m in modules) != 60:
        errors.append("Module hours must total 60.")
    if EHC_KNOWLEDGE["duration_hours"] != 60:
        errors.append("Duration must be 60 hours.")
    if len(EHC_KNOWLEDGE["tools"]) != 13:
        errors.append("Tool list must contain 13 entries.")
    if EHC_KNOWLEDGE["certification"]["status"] != "unknown":
        errors.append("Certification must remain unknown because source details are unspecified.")
    if EHC_KNOWLEDGE["assessment"]["status"] != "not_specified_in_source":
        errors.append("Assessment must remain unspecified where the source does not provide an assessment structure.")
    if EHC_COMMERCIAL_KNOWLEDGE["pricing_regions"]["india"]["base_fee"] != 60000:
        errors.append("India Ethical Hacking & Cybersecurity fee must be ₹60,000.")
    if EHC_COMMERCIAL_KNOWLEDGE["pricing_regions"]["international"]["base_fee"] is not None:
        errors.append("International Ethical Hacking & Cybersecurity fee must remain unknown.")
    if not EHC_KNOWLEDGE["boundaries"]["authorized_environment_only"]:
        errors.append("Authorized-environment safety must remain enabled.")

    return {"valid": not errors, "errors": errors}


def add_ehc_to_master_kb(kb):
    report = validate_ehc_knowledge()
    if not report["valid"]:
        raise ValueError(report["errors"])

    from Sayyed_EdVantage_Master_KB_BATCH01 import CourseRecord, CommercialOffering, SourceRecord

    kb.register_source(SourceRecord(
        source_id=EHC_SOURCE_ID,
        title="Ethical Hacking & Cybersecurity Professional Program Curriculum",
        source_type="course_curriculum",
        version="1.0",
        status="approved",
        course_id=EHC_COURSE_ID,
        notes=(
            "Source-derived curriculum. Source program status is Curriculum Design / Proposed."
        ),
    ))

    kb.register_course(CourseRecord(
        course_id=EHC_COURSE_ID,
        official_name=EHC_KNOWLEDGE["official_name"],
        category=EHC_KNOWLEDGE["category"],
        status="active",
        knowledge=deepcopy(EHC_KNOWLEDGE),
        source_ids=[EHC_SOURCE_ID],
    ))

    kb.register_offering(CommercialOffering(
        offering_id=EHC_OFFERING_ID,
        name="Ethical Hacking & Cybersecurity",
        offering_type="course",
        pricing_regions=deepcopy(EHC_COMMERCIAL_KNOWLEDGE["pricing_regions"]),
        source_ids=[EHC_SOURCE_ID],
    ))

    return kb


def get_ehc_knowledge() -> Dict[str, Any]:
    return deepcopy(EHC_KNOWLEDGE)


def get_ehc_commercial_knowledge() -> Dict[str, Any]:
    return deepcopy(EHC_COMMERCIAL_KNOWLEDGE)


def build_master_kb_with_ehc():
    from Sayyed_EdVantage_Master_KB_BATCH15 import build_master_kb_with_devops
    return add_ehc_to_master_kb(build_master_kb_with_devops())
