from copy import deepcopy
from typing import Any, Dict, List

DATA_SCIENCE_COURSE_ID = "SE-DSP-001"

CERTIFICATION_KNOWLEDGE = {
    "course_id": DATA_SCIENCE_COURSE_ID,
    "status": "unknown",
    "certificate_title": None,
    "certificate_type": None,
    "issuing_body": None,
    "accrediting_body": None,
    "award_conditions": None,
    "validity": None,
    "verification_method": None,
    "source_note": (
        "The supplied Data Science curriculum does not specify certificate "
        "title, certificate type, issuing body, accrediting body, award "
        "conditions, validity, or verification method."
    ),
    "agent_rule": (
        "Do not invent, infer, or present certification details as facts. "
        "If asked for certification details not present in the approved "
        "knowledge, state that the available course source does not specify "
        "them and route the student to admissions/team for confirmation."
    ),
}

PROGRAM_INFORMATION = {
    "course_id": DATA_SCIENCE_COURSE_ID,
    "official_name": "Data Science – Professional Program",
    "course_status": "Current Professional Program Curriculum",
    "duration_hours": 60,
    "level": "Beginner to Intermediate",
    "mode": "Instructor-Led / Online Live",
    "prerequisites": (
        "Basic computer knowledge and logical thinking. "
        "No prior programming experience required."
    ),
    "program_positioning": (
        "A practical Data Science program covering the workflow from "
        "problem definition and data understanding through modeling, "
        "evaluation, deployment and communication."
    ),
    "relationship_to_ai_program": (
        "Data Science provides the foundation; advanced AI and Generative AI "
        "content belongs to the dedicated AI + Generative AI program."
    ),
}

ANSWER_SAFETY_RULES = {
    "source_grounding": True,
    "no_invention": True,
    "certification_unknown": True,
    "no_job_guarantee": True,
    "no_salary_guarantee": True,
    "no_placement_guarantee": True,
    "commercial_region_awareness": True,
    "international_fee_no_india_fallback": True,
    "execution_allowed": False,
    "message_send_allowed": False,
    "external_action_allowed": False,
    "crm_write_allowed": False,
}

def get_certification_knowledge() -> Dict[str, Any]:
    return deepcopy(CERTIFICATION_KNOWLEDGE)

def get_program_information() -> Dict[str, Any]:
    return deepcopy(PROGRAM_INFORMATION)

def get_answer_safety_rules() -> Dict[str, Any]:
    return deepcopy(ANSWER_SAFETY_RULES)

def validate_batch07() -> Dict[str, Any]:
    errors: List[str] = []

    if CERTIFICATION_KNOWLEDGE["course_id"] != DATA_SCIENCE_COURSE_ID:
        errors.append("Certification course ID mismatch.")
    if CERTIFICATION_KNOWLEDGE["status"] != "unknown":
        errors.append("Certification status must remain unknown.")
    for field in (
        "certificate_title", "certificate_type", "issuing_body",
        "accrediting_body", "award_conditions", "validity",
        "verification_method"
    ):
        if CERTIFICATION_KNOWLEDGE[field] is not None:
            errors.append(f"Unsupported certification field populated: {field}.")

    if PROGRAM_INFORMATION["duration_hours"] != 60:
        errors.append("Program duration must be 60 hours.")
    if PROGRAM_INFORMATION["level"] != "Beginner to Intermediate":
        errors.append("Program level mismatch.")
    if PROGRAM_INFORMATION["mode"] != "Instructor-Led / Online Live":
        errors.append("Program mode mismatch.")

    required_safety = (
        "source_grounding", "no_invention", "certification_unknown",
        "no_job_guarantee", "no_salary_guarantee", "no_placement_guarantee",
        "commercial_region_awareness", "international_fee_no_india_fallback",
        "execution_allowed", "message_send_allowed",
        "external_action_allowed", "crm_write_allowed"
    )
    for key in required_safety:
        if key not in ANSWER_SAFETY_RULES:
            errors.append(f"Safety rule missing: {key}")

    if ANSWER_SAFETY_RULES["execution_allowed"] is not False:
        errors.append("Execution must remain disabled.")
    if ANSWER_SAFETY_RULES["message_send_allowed"] is not False:
        errors.append("Message sending must remain disabled.")

    return {
        "valid": not errors,
        "errors": errors,
        "certification_status": CERTIFICATION_KNOWLEDGE["status"],
        "program_duration_hours": PROGRAM_INFORMATION["duration_hours"],
        "safety_rule_count": len(ANSWER_SAFETY_RULES),
    }

def add_batch07_to_master_kb(kb):
    report = validate_batch07()
    if not report["valid"]:
        raise ValueError(report["errors"])

    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None:
        raise KeyError("Data Science course is missing from Master KB.")

    knowledge = deepcopy(course.knowledge)
    knowledge["certification_knowledge"] = get_certification_knowledge()
    knowledge["program_information"] = get_program_information()
    knowledge["answer_safety_rules"] = get_answer_safety_rules()
    course.knowledge = knowledge
    kb.register_course(course)
    return kb

def build_master_kb_with_batch07():
    from Sayyed_EdVantage_Master_KB_BATCH06 import build_master_kb_with_batch06
    return add_batch07_to_master_kb(build_master_kb_with_batch06())
