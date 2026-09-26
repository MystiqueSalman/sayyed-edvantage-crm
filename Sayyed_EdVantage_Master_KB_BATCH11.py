from copy import deepcopy
from typing import Any, Dict, List

DATA_ANALYTICS_COURSE_ID = "SE-DA-001"
DATA_ANALYTICS_SOURCE_ID = "DA-CURRICULUM-SOURCE-001"
DATA_ANALYTICS_OFFERING_ID = "DA-OFFERING-INDIA-001"

DATA_ANALYTICS_KNOWLEDGE: Dict[str, Any] = {
    "course_id": DATA_ANALYTICS_COURSE_ID,
    "official_name": "Data Analytics – Professional Program",
    "category": "Data Analytics",
    "status": "active",
    "duration_hours": 60,
    "level": "Beginner to Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "required": [
            "Basic computer knowledge",
            "Logical thinking",
        ],
        "prior_programming_required": False,
    },
    "primary_goal": (
        "Build practical skills to collect, clean, analyze, visualize and "
        "communicate data for business and reporting use cases."
    ),
    "core_learning_flow": [
        "Analytics foundations",
        "Excel",
        "Data cleaning and preparation",
        "SQL",
        "Statistics",
        "EDA and analytical thinking",
        "Visualization and business storytelling",
        "Power BI",
        "Data modeling and DAX",
        "Dashboard development and BI",
        "MIS reporting and KPIs",
        "Real-world analytics projects and capstone",
    ],
    "modules": [
        {"number": 1, "title": "Data Analytics Foundations & Business Thinking", "hours": 3},
        {"number": 2, "title": "Advanced Excel", "hours": 10},
        {"number": 3, "title": "Data Cleaning, Preparation & Power Query", "hours": 5},
        {"number": 4, "title": "SQL for Data Analytics", "hours": 8},
        {"number": 5, "title": "Statistics", "hours": 5},
        {"number": 6, "title": "EDA & Analytical Thinking", "hours": 4},
        {"number": 7, "title": "Data Visualization & Business Storytelling", "hours": 4},
        {"number": 8, "title": "Power BI Fundamentals", "hours": 5},
        {"number": 9, "title": "Power BI Data Modeling & DAX", "hours": 6},
        {"number": 10, "title": "Dashboard Development & BI", "hours": 4},
        {"number": 11, "title": "MIS Reporting, KPIs & Business Analysis", "hours": 3},
        {"number": 12, "title": "Real-World Analytics Projects & Capstone", "hours": 3},
    ],
    "projects": [
        "Excel-based analytical and reporting work",
        "Data cleaning and preparation project using Power Query",
        "SQL-based business data analysis",
        "Exploratory data analysis and analytical investigation",
        "Business visualization and storytelling work",
        "Power BI dashboard project",
        "MIS/KPI reporting work",
        "Final real-world analytics capstone",
    ],
    "assessment": {
        "quizzes_and_assignments_percent": 15,
        "hands_on_labs_percent": 20,
        "mini_projects_percent": 20,
        "case_study_problem_solving_percent": 10,
        "capstone_percent": 25,
        "presentation_and_viva_percent": 10,
        "total_percent": 100,
    },
    "tools": [
        "Microsoft Excel",
        "Power Query",
        "SQL",
        "Power BI",
        "DAX",
    ],
    "learning_outcomes": [
        "Understand data analytics foundations and business-oriented problem solving.",
        "Use Excel for practical analysis and reporting.",
        "Clean and prepare data using Power Query.",
        "Write SQL queries for analytical data extraction and analysis.",
        "Apply core statistics in analytics contexts.",
        "Perform exploratory data analysis and identify meaningful patterns.",
        "Create useful data visualizations.",
        "Communicate findings through business storytelling.",
        "Use Power BI for business intelligence workflows.",
        "Build data models and use DAX.",
        "Develop dashboards for reporting and decision support.",
        "Work with MIS reports and KPIs.",
        "Complete a real-world analytics capstone and present the work.",
    ],
    "career": {
        "preparation_areas": [
            "Data analysis",
            "Business intelligence",
            "Reporting and MIS",
            "Power BI",
            "Dashboard development",
            "Analytical communication",
        ],
        "example_roles": [
            "Data Analyst",
            "BI Analyst",
            "Reporting / MIS Analyst",
            "Power BI Analyst",
        ],
        "guarantees": {
            "employment": False,
            "placement": False,
            "salary": False,
            "income": False,
        },
    },
    "boundaries": {
        "python_is_not_core": True,
        "excluded_as_core": [
            "Machine Learning",
            "Deep Learning",
            "Generative AI",
            "LLMs",
            "LangChain",
            "LangGraph",
            "RAG",
            "Agentic AI",
            "LLMOps",
        ],
        "note": (
            "Data Analytics is focused on analytics, reporting, BI, "
            "visualization, SQL, Excel, Power Query, Power BI and DAX."
        ),
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


DATA_ANALYTICS_COMMERCIAL_KNOWLEDGE: Dict[str, Any] = {
    "offering_id": DATA_ANALYTICS_OFFERING_ID,
    "name": "Data Analytics",
    "offering_type": "course",
    "pricing_regions": {
        "india": {
            "status": "verified_user_supplied",
            "currency": "INR",
            "base_fee": 40000,
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


def validate_data_analytics_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    modules = DATA_ANALYTICS_KNOWLEDGE["modules"]

    if sum(m["hours"] for m in modules) != 60:
        errors.append("Module hours must total 60.")
    if len(modules) != 12:
        errors.append("Data Analytics must contain 12 modules.")
    if DATA_ANALYTICS_KNOWLEDGE["duration_hours"] != 60:
        errors.append("Duration must be 60 hours.")
    assessment = DATA_ANALYTICS_KNOWLEDGE["assessment"]
    assessment_components = [
        assessment["quizzes_and_assignments_percent"],
        assessment["hands_on_labs_percent"],
        assessment["mini_projects_percent"],
        assessment["case_study_problem_solving_percent"],
        assessment["capstone_percent"],
        assessment["presentation_and_viva_percent"],
    ]
    if sum(assessment_components) != 100:
        errors.append("Assessment component percentages must total 100.")
    if assessment["total_percent"] != 100:
        errors.append("Assessment total_percent must be 100.")
    if len(DATA_ANALYTICS_KNOWLEDGE["tools"]) != 5:
        errors.append("Tool list must contain 5 tools.")
    if DATA_ANALYTICS_KNOWLEDGE["certification"]["status"] != "unknown":
        errors.append("Certification must remain unknown because source details are unspecified.")
    if DATA_ANALYTICS_COMMERCIAL_KNOWLEDGE["pricing_regions"]["india"]["base_fee"] != 40000:
        errors.append("India Data Analytics fee must be ₹40,000.")
    if DATA_ANALYTICS_COMMERCIAL_KNOWLEDGE["pricing_regions"]["international"]["base_fee"] is not None:
        errors.append("International Data Analytics fee must remain unknown.")
    return {"valid": not errors, "errors": errors}


def add_data_analytics_to_master_kb(kb):
    report = validate_data_analytics_knowledge()
    if not report["valid"]:
        raise ValueError(report["errors"])

    from Sayyed_EdVantage_Master_KB_BATCH01 import CourseRecord, CommercialOffering, SourceRecord

    kb.register_source(SourceRecord(
        source_id=DATA_ANALYTICS_SOURCE_ID,
        title="Data Analytics Professional Program Curriculum",
        source_type="course_curriculum",
        version="1.0",
        status="approved",
        course_id=DATA_ANALYTICS_COURSE_ID,
        notes="Source-derived Data Analytics curriculum record.",
    ))

    kb.register_course(CourseRecord(
        course_id=DATA_ANALYTICS_COURSE_ID,
        official_name=DATA_ANALYTICS_KNOWLEDGE["official_name"],
        category=DATA_ANALYTICS_KNOWLEDGE["category"],
        status="active",
        knowledge=deepcopy(DATA_ANALYTICS_KNOWLEDGE),
        source_ids=[DATA_ANALYTICS_SOURCE_ID],
    ))

    kb.register_offering(CommercialOffering(
        offering_id=DATA_ANALYTICS_OFFERING_ID,
        name="Data Analytics",
        offering_type="course",
        pricing_regions=deepcopy(DATA_ANALYTICS_COMMERCIAL_KNOWLEDGE["pricing_regions"]),
        source_ids=[DATA_ANALYTICS_SOURCE_ID],
    ))

    return kb


def get_data_analytics_knowledge() -> Dict[str, Any]:
    return deepcopy(DATA_ANALYTICS_KNOWLEDGE)


def get_data_analytics_commercial_knowledge() -> Dict[str, Any]:
    return deepcopy(DATA_ANALYTICS_COMMERCIAL_KNOWLEDGE)


def build_master_kb_with_data_analytics():
    from Sayyed_EdVantage_Master_KB_BATCH10 import build_master_kb_with_batch10
    return add_data_analytics_to_master_kb(build_master_kb_with_batch10())
