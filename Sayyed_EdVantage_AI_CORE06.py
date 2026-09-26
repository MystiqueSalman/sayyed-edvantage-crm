"""
Sayyed EdVantage AI Agent — AI Core 06
Eligibility Evaluation & Recommendation Readiness Contract
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List
import copy

from Sayyed_EdVantage_AI_CORE05 import (
    ProspectProfile, FIELD_NAMES, validate_prospect_profile
)

ELIGIBILITY_READY = "ELIGIBILITY_READY"
ELIGIBILITY_INSUFFICIENT = "ELIGIBILITY_INSUFFICIENT"
ELIGIBILITY_CLARIFICATION = "ELIGIBILITY_CLARIFICATION"

@dataclass
class CourseEligibilityResult:
    course_id: str
    official_name: str
    status: str
    satisfied: List[str] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

@dataclass
class EligibilityEvaluation:
    session_id: str
    status: str
    course_results: List[CourseEligibilityResult] = field(default_factory=list)
    recommendation_ready: bool = False
    clarification_needed: bool = False
    clarification_reason: str = ""
    evidence: List[str] = field(default_factory=list)
    no_invention: bool = True

def _unique(values):
    return list(dict.fromkeys(values))

def _profile_value(profile, name):
    f = getattr(profile, name, None)
    return f.value if f is not None and f.status == "known" else None

def evaluate_course_eligibility(kb: Any, profile: ProspectProfile, course_id: str):
    course = kb.get_course(course_id)
    if course is None:
        return CourseEligibilityResult(
            course_id=course_id, official_name=course_id,
            status="UNKNOWN_COURSE", unknown=["course record"],
            evidence=["course record was not found in the Master KB"]
        )

    knowledge = course.knowledge or {}
    eligibility = knowledge.get("eligibility", {})
    if not isinstance(eligibility, dict):
        eligibility = {}

    requirements = eligibility.get("requirements", [])
    if not isinstance(requirements, list):
        requirements = []

    satisfied, unknown, unsupported, evidence = [], [], [], []

    # Only structured requirements explicitly present in the KB may be evaluated.
    if not requirements:
        unknown.append("documented eligibility requirements")
        evidence.append(
            "The Master KB does not expose a structured eligibility "
            "requirements list for this course."
        )
    else:
        for req in requirements:
            if not isinstance(req, dict):
                unknown.append("unstructured eligibility requirement")
                continue
            field = req.get("profile_field")
            desc = req.get("description", field or "requirement")
            required = req.get("required_value")
            if field not in FIELD_NAMES:
                unsupported.append(desc)
                continue
            actual = _profile_value(profile, field)
            if actual is None:
                unknown.append(desc)
            elif required is None or str(actual).lower() == str(required).lower():
                satisfied.append(desc)
                evidence.append(f"{desc} supported by explicit profile fact.")
            else:
                unsupported.append(desc)

    if unsupported:
        status = "NOT_ESTABLISHED"
    elif unknown:
        status = "INSUFFICIENT_INFORMATION"
    else:
        status = "SUPPORTED"

    return CourseEligibilityResult(
        course_id=course.course_id, official_name=course.official_name,
        status=status, satisfied=_unique(satisfied),
        unknown=_unique(unknown), unsupported=_unique(unsupported),
        evidence=_unique(evidence)
    )

def evaluate_eligibility(kb: Any, profile: ProspectProfile, course_ids: List[str]):
    pv = validate_prospect_profile(profile)
    if not pv["valid"]:
        return EligibilityEvaluation(
            session_id=profile.session_id,
            status=ELIGIBILITY_CLARIFICATION,
            clarification_needed=True,
            clarification_reason="Prospect profile is structurally invalid.",
            evidence=pv["errors"]
        )

    ids = _unique(course_ids)
    if not ids:
        return EligibilityEvaluation(
            session_id=profile.session_id,
            status=ELIGIBILITY_INSUFFICIENT,
            clarification_needed=True,
            clarification_reason=(
                "No course has been established. A course must be identified "
                "before course-specific eligibility can be evaluated."
            ),
            evidence=["no course ID supplied"]
        )

    results = [evaluate_course_eligibility(kb, profile, cid) for cid in ids]

    if any(r.status == "NOT_ESTABLISHED" for r in results):
        status = ELIGIBILITY_CLARIFICATION
        reason = "At least one stated eligibility condition is not established by the available profile evidence."
    elif any(r.status in {"INSUFFICIENT_INFORMATION", "UNKNOWN_COURSE"} for r in results):
        status = ELIGIBILITY_INSUFFICIENT
        reason = "More explicit student information or verified course eligibility detail is needed before eligibility can be confirmed."
    else:
        status = ELIGIBILITY_READY
        reason = ""

    return EligibilityEvaluation(
        session_id=profile.session_id, status=status, course_results=results,
        recommendation_ready=(status == ELIGIBILITY_READY),
        clarification_needed=(status != ELIGIBILITY_READY),
        clarification_reason=reason,
        evidence=_unique([e for r in results for e in r.evidence])
    )

def eligibility_to_dict(result):
    return {
        "session_id": result.session_id, "status": result.status,
        "course_results": [{
            "course_id": r.course_id, "official_name": r.official_name,
            "status": r.status, "satisfied": list(r.satisfied),
            "unknown": list(r.unknown), "unsupported": list(r.unsupported),
            "evidence": list(r.evidence)
        } for r in result.course_results],
        "recommendation_ready": result.recommendation_ready,
        "clarification_needed": result.clarification_needed,
        "clarification_reason": result.clarification_reason,
        "evidence": list(result.evidence), "no_invention": result.no_invention
    }

def validate_eligibility(result):
    errors = []
    if result.status not in {ELIGIBILITY_READY, ELIGIBILITY_INSUFFICIENT, ELIGIBILITY_CLARIFICATION}:
        errors.append("Invalid eligibility status.")
    if result.no_invention is not True:
        errors.append("Eligibility no_invention must be True.")
    ids = [r.course_id for r in result.course_results]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate course eligibility results are not allowed.")
    if result.status == ELIGIBILITY_READY:
        if not result.recommendation_ready or result.clarification_needed:
            errors.append("Ready eligibility flags are inconsistent.")
    else:
        if not result.clarification_needed or result.recommendation_ready:
            errors.append("Non-ready eligibility flags are inconsistent.")
        if not result.clarification_reason:
            errors.append("Non-ready eligibility requires a reason.")
    for r in result.course_results:
        if r.status not in {"SUPPORTED", "INSUFFICIENT_INFORMATION", "NOT_ESTABLISHED", "UNKNOWN_COURSE"}:
            errors.append(f"Invalid course eligibility status: {r.status}.")
        if set(r.satisfied) & set(r.unknown):
            errors.append("Satisfied and unknown requirements overlap.")
        if set(r.satisfied) & set(r.unsupported):
            errors.append("Satisfied and unsupported requirements overlap.")
    return {"valid": not errors, "errors": _unique(errors)}

def build_eligibility_layer():
    from Sayyed_EdVantage_AI_CORE05 import build_prospect_qualification_layer
    return build_prospect_qualification_layer()
