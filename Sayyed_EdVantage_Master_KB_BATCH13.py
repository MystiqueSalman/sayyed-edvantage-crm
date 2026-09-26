from copy import deepcopy
from typing import Any, Dict, List

PYTHON_COURSE_ID = "SE-PY-001"
PYTHON_SOURCE_ID = "PY-CURRICULUM-SOURCE-001"
PYTHON_OFFERING_ID = "PY-OFFERING-INDIA-001"

PYTHON_KNOWLEDGE: Dict[str, Any] = {
    "course_id": PYTHON_COURSE_ID,
    "official_name": "Python – Professional Program",
    "category": "Python",
    "status": "active",
    "duration_hours": 40,
    "level": "Beginner to Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "required": ["Basic computer knowledge", "Logical thinking"],
        "prior_programming_required": False,
    },
    "primary_goal": (
        "Build practical Python programming, problem-solving, automation, "
        "file/data handling and testing skills."
    ),
    "modules": [
        {"number": 1, "title": "Programming Mindset & Python Foundations", "hours": 4},
        {"number": 2, "title": "Data Types & Control Flow", "hours": 5},
        {"number": 3, "title": "Data Structures", "hours": 5},
        {"number": 4, "title": "Functions, Modules & Problem Solving", "hours": 5},
        {"number": 5, "title": "Object-Oriented Programming", "hours": 5},
        {"number": 6, "title": "Files, Exceptions, Data & Debugging", "hours": 5},
        {"number": 7, "title": "APIs, Automation & Professional Python", "hours": 4},
        {"number": 8, "title": "Testing, Debugging, Projects & Career Lab", "hours": 7},
    ],
    "projects": [
        "Interactive Python programs",
        "Logic challenge project",
        "Student records application",
        "Utility toolkit",
        "Library / inventory application",
        "File data application",
        "Automation tool",
        "Testing and debugging project",
        "Final real-world Python application",
    ],
    "assessment": {
        "quizzes_and_assignments_percent": 20,
        "hands_on_labs_percent": 20,
        "mini_projects_percent": 20,
        "case_study_problem_solving_percent": 10,
        "capstone_percent": 20,
        "presentation_and_viva_percent": 10,
        "total_percent": 100,
    },
    "tools": [
        "Python",
        "Python Standard Library",
        "pip",
        "venv",
        "CSV",
        "JSON",
        "REST APIs",
        "Git",
        "GitHub",
        "VS Code / IDE",
        "Terminal",
    ],
    "learning_outcomes": [
        "Understand programming fundamentals and Python syntax.",
        "Work with Python data types and control flow.",
        "Use Python data structures effectively.",
        "Write reusable functions and organize code into modules.",
        "Apply structured problem-solving techniques.",
        "Build classes and use object-oriented programming concepts.",
        "Read and write files and structured data.",
        "Handle exceptions and debug Python programs.",
        "Work with APIs and automate practical tasks.",
        "Use Python environments and packages professionally.",
        "Apply testing and debugging practices.",
        "Build and present a practical Python project.",
    ],
    "career": {
        "preparation_areas": [
            "Python programming",
            "Problem solving",
            "Automation",
            "API integration",
            "File/data processing",
            "Testing and debugging",
        ],
        "example_roles": [
            "Python Developer",
            "Automation Developer",
            "Junior Software Developer",
            "Backend Development Trainee",
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
            "This program focuses on Python programming and practical software "
            "development foundations; it is not a complete Data Science, AI or "
            "Generative AI program."
        ),
        "not_core": [
            "Complete Data Science curriculum",
            "Advanced Machine Learning",
            "Deep Learning",
            "Generative AI",
            "LLM application development",
            "RAG",
            "Agentic AI",
        ],
    },
    "eligibility": {
        "required": ["Basic computer knowledge", "Logical thinking"],
        "prior_programming_required": False,
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

PYTHON_COMMERCIAL_KNOWLEDGE: Dict[str, Any] = {
    "offering_id": PYTHON_OFFERING_ID,
    "name": "Python",
    "offering_type": "course",
    "pricing_regions": {
        "india": {
            "status": "verified_user_supplied",
            "currency": "INR",
            "base_fee": 35000,
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


def validate_python_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    modules = PYTHON_KNOWLEDGE["modules"]
    assessment = PYTHON_KNOWLEDGE["assessment"]
    components = [
        assessment["quizzes_and_assignments_percent"],
        assessment["hands_on_labs_percent"],
        assessment["mini_projects_percent"],
        assessment["case_study_problem_solving_percent"],
        assessment["capstone_percent"],
        assessment["presentation_and_viva_percent"],
    ]

    if sum(m["hours"] for m in modules) != 40:
        errors.append("Module hours must total 40.")
    if len(modules) != 8:
        errors.append("Python must contain 8 modules.")
    if PYTHON_KNOWLEDGE["duration_hours"] != 40:
        errors.append("Duration must be 40 hours.")
    if sum(components) != 100:
        errors.append("Assessment component percentages must total 100.")
    if assessment["total_percent"] != 100:
        errors.append("Assessment total_percent must be 100.")
    if len(PYTHON_KNOWLEDGE["tools"]) != 11:
        errors.append("Tool list must contain 11 entries.")
    if PYTHON_KNOWLEDGE["certification"]["status"] != "unknown":
        errors.append("Certification must remain unknown because source details are unspecified.")
    if PYTHON_COMMERCIAL_KNOWLEDGE["pricing_regions"]["india"]["base_fee"] != 35000:
        errors.append("India Python fee must be ₹35,000.")
    if PYTHON_COMMERCIAL_KNOWLEDGE["pricing_regions"]["international"]["base_fee"] is not None:
        errors.append("International Python fee must remain unknown.")

    return {"valid": not errors, "errors": errors}


def add_python_to_master_kb(kb):
    report = validate_python_knowledge()
    if not report["valid"]:
        raise ValueError(report["errors"])

    from Sayyed_EdVantage_Master_KB_BATCH01 import CourseRecord, CommercialOffering, SourceRecord

    kb.register_source(SourceRecord(
        source_id=PYTHON_SOURCE_ID,
        title="Python Professional Program Curriculum",
        source_type="course_curriculum",
        version="1.0",
        status="approved",
        course_id=PYTHON_COURSE_ID,
        notes="Source-derived Python curriculum record.",
    ))

    kb.register_course(CourseRecord(
        course_id=PYTHON_COURSE_ID,
        official_name=PYTHON_KNOWLEDGE["official_name"],
        category=PYTHON_KNOWLEDGE["category"],
        status="active",
        knowledge=deepcopy(PYTHON_KNOWLEDGE),
        source_ids=[PYTHON_SOURCE_ID],
    ))

    kb.register_offering(CommercialOffering(
        offering_id=PYTHON_OFFERING_ID,
        name="Python",
        offering_type="course",
        pricing_regions=deepcopy(PYTHON_COMMERCIAL_KNOWLEDGE["pricing_regions"]),
        source_ids=[PYTHON_SOURCE_ID],
    ))

    return kb


def get_python_knowledge() -> Dict[str, Any]:
    return deepcopy(PYTHON_KNOWLEDGE)


def get_python_commercial_knowledge() -> Dict[str, Any]:
    return deepcopy(PYTHON_COMMERCIAL_KNOWLEDGE)


def build_master_kb_with_python():
    from Sayyed_EdVantage_Master_KB_BATCH12 import build_master_kb_with_ai_genai
    return add_python_to_master_kb(build_master_kb_with_ai_genai())
