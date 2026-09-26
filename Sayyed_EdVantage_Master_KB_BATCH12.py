from copy import deepcopy
from typing import Any, Dict, List

AI_GENAI_COURSE_ID = "SE-AIGEN-001"
AI_GENAI_SOURCE_ID = "AIGEN-CURRICULUM-SOURCE-001"
AI_GENAI_OFFERING_ID = "AIGEN-OFFERING-INDIA-001"

AI_GENAI_KNOWLEDGE: Dict[str, Any] = {
    "course_id": AI_GENAI_COURSE_ID,
    "official_name": "AI + Generative AI – Professional Program",
    "category": "Artificial Intelligence / Generative AI",
    "status": "planned",
    "duration_hours": 60,
    "level": "Intermediate to Advanced",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": {
        "recommended": [
            "Basic Python programming knowledge",
            "Basic understanding of Data Science and Machine Learning is strongly recommended",
        ],
        "prior_programming_required": True,
    },
    "modules": [
        {"number": 1, "title": "AI Foundations & Modern AI Ecosystem", "hours": 3},
        {"number": 2, "title": "Deep Learning for AI", "hours": 5},
        {"number": 3, "title": "NLP", "hours": 4},
        {"number": 4, "title": "Transformers & Modern Language Models", "hours": 4},
        {"number": 5, "title": "Generative AI Fundamentals", "hours": 4},
        {"number": 6, "title": "Prompt Engineering & LLM Interaction", "hours": 4},
        {"number": 7, "title": "LLM Application Development & APIs", "hours": 4},
        {"number": 8, "title": "LangChain & AI Application Frameworks", "hours": 3},
        {"number": 9, "title": "Embeddings & Vector Databases", "hours": 3},
        {"number": 10, "title": "RAG", "hours": 5},
        {"number": 11, "title": "LangGraph & Agentic AI", "hours": 5},
        {"number": 12, "title": "AI Tools, Function Calling & Automation", "hours": 3},
        {"number": 13, "title": "AI Evaluation, Safety & Reliability", "hours": 3},
        {"number": 14, "title": "LLMOps & Production AI", "hours": 3},
        {"number": 15, "title": "AI Application Deployment", "hours": 3},
        {"number": 16, "title": "AI Product Development, Portfolio & Career Lab", "hours": 3},
    ],
    "projects": [
        "AI foundations / ecosystem project",
        "Deep learning project",
        "NLP project",
        "Transformer / language-model project",
        "Generative AI application",
        "Prompt engineering project",
        "LLM application using APIs",
        "LangChain AI application",
        "Embeddings and vector database project",
        "RAG application",
        "LangGraph / Agentic AI application",
        "AI tools, function calling and automation project",
        "End-to-End AI Product",
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
        "Python",
        "TensorFlow",
        "Keras",
        "PyTorch",
        "Hugging Face",
        "OpenAI APIs",
        "LangChain",
        "LangGraph",
        "ChromaDB",
        "FAISS",
        "FastAPI",
        "Flask",
        "Streamlit",
        "Docker",
        "Git",
        "GitHub",
        "MLflow concepts",
        "LangSmith",
        "W&B concepts",
        "OpenTelemetry concepts",
    ],
    "career": {
        "preparation_areas": [
            "AI application development",
            "Generative AI",
            "LLM applications",
            "RAG",
            "Agentic AI",
            "AI evaluation and reliability",
            "Production AI",
            "AI application deployment",
            "AI product development",
        ],
        "guarantees": {
            "employment": False,
            "placement": False,
            "salary": False,
            "income": False,
        },
    },
    "boundaries": {
        "note": "This is the dedicated advanced AI + Generative AI program and contains topics excluded from the Data Science program.",
        "advanced_topics": [
            "Generative AI",
            "LLM application development",
            "LangChain",
            "Embeddings",
            "Vector databases",
            "RAG",
            "LangGraph",
            "Agentic AI",
            "Function calling",
            "LLMOps",
        ],
    },
    "eligibility": {
        "required": ["Python", "Data Science foundation"],
        "prior_programming_required": True,
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
    "source_consistency": {
        "declared_total_hours": 60,
        "module_hours_total": 59,
        "status": "documented_source_inconsistency",
        "action": "Do not invent or silently rebalance module hours; route conflicting duration questions to the appropriate admissions/faculty source.",
    },
}

AI_GENAI_COMMERCIAL_KNOWLEDGE: Dict[str, Any] = {
    "offering_id": AI_GENAI_OFFERING_ID,
    "name": "AI + Generative AI",
    "offering_type": "course",
    "pricing_regions": {
        "india": {
            "status": "verified_user_supplied",
            "currency": "INR",
            "base_fee": 70000,
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


def validate_ai_genai_knowledge() -> Dict[str, Any]:
    errors: List[str] = []
    modules = AI_GENAI_KNOWLEDGE["modules"]
    assessment = AI_GENAI_KNOWLEDGE["assessment"]
    assessment_components = [
        assessment["quizzes_and_assignments_percent"],
        assessment["hands_on_labs_percent"],
        assessment["mini_projects_percent"],
        assessment["case_study_problem_solving_percent"],
        assessment["capstone_percent"],
        assessment["presentation_and_viva_percent"],
    ]

    declared_total = AI_GENAI_KNOWLEDGE["duration_hours"]
    module_hours_total = sum(m["hours"] for m in modules)

    # The supplied source explicitly declares TOTAL_DURATION = 60 Hours,
    # while its per-module hour table sums to 59. Do not invent a missing
    # hour or silently alter a module. Preserve and document the source
    # inconsistency instead.
    if declared_total != 60:
        errors.append("Declared total duration must remain 60 hours.")
    if module_hours_total != 59:
        errors.append("The source-derived module hour table must total 59 hours as supplied.")
    AI_GENAI_KNOWLEDGE["source_consistency"] = {
        "declared_total_hours": declared_total,
        "module_hours_total": module_hours_total,
        "status": "documented_source_inconsistency",
        "action": "Do not invent or silently rebalance module hours; route conflicting duration questions to the appropriate admissions/faculty source.",
    }
    if len(modules) != 16:
        errors.append("AI + Generative AI must contain 16 modules.")
    if AI_GENAI_KNOWLEDGE["duration_hours"] != 60:
        errors.append("Duration must be 60 hours.")
    if sum(assessment_components) != 100:
        errors.append("Assessment component percentages must total 100.")
    if assessment["total_percent"] != 100:
        errors.append("Assessment total_percent must be 100.")
    if len(AI_GENAI_KNOWLEDGE["tools"]) != 20:
        errors.append("Tool list must contain 20 entries.")
    if AI_GENAI_KNOWLEDGE["certification"]["status"] != "unknown":
        errors.append("Certification must remain unknown because source details are unspecified.")
    if AI_GENAI_COMMERCIAL_KNOWLEDGE["pricing_regions"]["india"]["base_fee"] != 70000:
        errors.append("India AI + Generative AI fee must be ₹70,000.")
    if AI_GENAI_COMMERCIAL_KNOWLEDGE["pricing_regions"]["international"]["base_fee"] is not None:
        errors.append("International AI + Generative AI fee must remain unknown.")

    return {"valid": not errors, "errors": errors}


def add_ai_genai_to_master_kb(kb):
    report = validate_ai_genai_knowledge()
    if not report["valid"]:
        raise ValueError(report["errors"])

    from Sayyed_EdVantage_Master_KB_BATCH01 import CourseRecord, CommercialOffering, SourceRecord

    kb.register_source(SourceRecord(
        source_id=AI_GENAI_SOURCE_ID,
        title="AI + Generative AI Professional Program Curriculum",
        source_type="course_curriculum",
        version="1.0",
        status="approved",
        course_id=AI_GENAI_COURSE_ID,
        notes="Source-derived AI + Generative AI curriculum record.",
    ))

    kb.register_course(CourseRecord(
        course_id=AI_GENAI_COURSE_ID,
        official_name=AI_GENAI_KNOWLEDGE["official_name"],
        category=AI_GENAI_KNOWLEDGE["category"],
        status="active",
        knowledge=deepcopy(AI_GENAI_KNOWLEDGE),
        source_ids=[AI_GENAI_SOURCE_ID],
    ))

    kb.register_offering(CommercialOffering(
        offering_id=AI_GENAI_OFFERING_ID,
        name="AI + Generative AI",
        offering_type="course",
        pricing_regions=deepcopy(AI_GENAI_COMMERCIAL_KNOWLEDGE["pricing_regions"]),
        source_ids=[AI_GENAI_SOURCE_ID],
    ))

    return kb


def get_ai_genai_knowledge() -> Dict[str, Any]:
    return deepcopy(AI_GENAI_KNOWLEDGE)


def get_ai_genai_commercial_knowledge() -> Dict[str, Any]:
    return deepcopy(AI_GENAI_COMMERCIAL_KNOWLEDGE)


def build_master_kb_with_ai_genai():
    from Sayyed_EdVantage_Master_KB_BATCH11 import build_master_kb_with_data_analytics
    return add_ai_genai_to_master_kb(build_master_kb_with_data_analytics())
