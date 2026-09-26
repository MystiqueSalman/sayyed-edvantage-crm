"""
Sayyed EdVantage AI Agent — AI Core 05
Prospect Profile & Qualification Evidence Contract

Purpose:
- Extract only prospect facts explicitly stated in the conversation.
- Maintain a structured, session-scoped qualification profile.
- Separate known facts from unknown/unstated facts.
- Support course recommendation without inventing background, goals,
  experience, education, budget, or eligibility.
- Keep the profile tied to conversation evidence.
- No CRM writes, messaging, external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import copy
import re

from Sayyed_EdVantage_AI_CORE02 import ConversationContext
from Sayyed_EdVantage_AI_CORE03 import normalize_message


PROFILE_READY = "PROFILE_READY"
PROFILE_EMPTY = "PROFILE_EMPTY"
PROFILE_CLARIFICATION = "PROFILE_CLARIFICATION"


@dataclass
class ProfileField:
    value: Optional[str] = None
    status: str = "unknown"
    evidence: List[str] = field(default_factory=list)


@dataclass
class ProspectProfile:
    session_id: str
    education: ProfileField = field(default_factory=ProfileField)
    experience: ProfileField = field(default_factory=ProfileField)
    technical_background: ProfileField = field(default_factory=ProfileField)
    learning_goal: ProfileField = field(default_factory=ProfileField)
    career_goal: ProfileField = field(default_factory=ProfileField)
    current_role: ProfileField = field(default_factory=ProfileField)
    region: ProfileField = field(default_factory=ProfileField)
    budget: ProfileField = field(default_factory=ProfileField)
    profile_status: str = PROFILE_EMPTY


@dataclass
class QualificationResult:
    profile: ProspectProfile
    newly_extracted_fields: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_reason: str = ""
    evidence: List[str] = field(default_factory=list)
    no_invention: bool = True


FIELD_NAMES = (
    "education",
    "experience",
    "technical_background",
    "learning_goal",
    "career_goal",
    "current_role",
    "region",
    "budget",
)


def _field(profile, name):
    return getattr(profile, name)


def _set_field(profile, name, value, evidence):
    f = _field(profile, name)
    if f.status == "known":
        return False
    f.value = value
    f.status = "known"
    f.evidence.append(evidence)
    return True


def create_prospect_profile(session_id: str) -> ProspectProfile:
    return ProspectProfile(session_id=session_id)


def _extract(message: str, profile: ProspectProfile):
    text = str(message).strip()
    normalized = normalize_message(text)
    extracted = []

    # Experience
    if re.search(r"\b(i am|i'm|im)\s+(a\s+)?fresher\b", normalized):
        if _set_field(profile, "experience", "fresher", text):
            extracted.append("experience")
    elif "no experience" in normalized or "no prior experience" in normalized:
        if _set_field(profile, "experience", "no prior experience", text):
            extracted.append("experience")
    elif "years of experience" in normalized:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s+of\s+experience", normalized)
        if match:
            if _set_field(profile, "experience", f"{match.group(1)} years", text):
                extracted.append("experience")

    # Education
    education_patterns = [
        (r"\b(b\.?\s*tech|btech)\b", "B.Tech"),
        (r"\b(m\.?\s*tech|mtech)\b", "M.Tech"),
        (r"\b(b\.?\s*sc|bsc)\b", "B.Sc"),
        (r"\b(m\.?\s*sc|msc)\b", "M.Sc"),
        (r"\b(b\.?\s*com|bcom)\b", "B.Com"),
        (r"\b(m\.?\s*com|mcom)\b", "M.Com"),
        (r"\b(bachelor'?s degree)\b", "Bachelor's degree"),
        (r"\b(master'?s degree)\b", "Master's degree"),
        (r"\b(12th|higher secondary)\b", "12th"),
    ]
    for pattern, value in education_patterns:
        if re.search(pattern, normalized):
            if _set_field(profile, "education", value, text):
                extracted.append("education")
            break

    # Technical background
    tech_terms = [
        "python", "sql", "excel", "linux", "git", "programming",
        "machine learning", "data analysis", "cloud", "docker",
    ]
    found_tech = [term for term in tech_terms if term in normalized]
    if found_tech and (
        "know" in normalized
        or "experience with" in normalized
        or "worked with" in normalized
        or "background in" in normalized
        or "familiar with" in normalized
    ):
        value = ", ".join(found_tech)
        if _set_field(profile, "technical_background", value, text):
            extracted.append("technical_background")

    # Learning goal
    goal_patterns = [
        (r"learn\s+python", "learn Python"),
        (r"learn\s+data science", "learn Data Science"),
        (r"learn\s+data analytics", "learn Data Analytics"),
        (r"learn\s+devops", "learn DevOps"),
        (r"learn\s+linux", "learn Linux"),
        (r"learn\s+(?:ai|artificial intelligence|generative ai|gen ai)", "learn AI / Generative AI"),
        (r"learn\s+(?:ethical hacking|cybersecurity|cyber security)", "learn Ethical Hacking & Cybersecurity"),
        (r"switch\s+(?:my\s+)?career", "career switch"),
        (r"upskill", "upskill"),
        (r"improve\s+(?:my\s+)?skills", "improve skills"),
    ]
    for pattern, value in goal_patterns:
        if re.search(pattern, normalized):
            if _set_field(profile, "learning_goal", value, text):
                extracted.append("learning_goal")
            break

    # Career goal
    career_patterns = [
        (r"become\s+a\s+data scientist", "become a Data Scientist"),
        (r"become\s+a\s+data analyst", "become a Data Analyst"),
        (r"become\s+a\s+devops engineer", "become a DevOps Engineer"),
        (r"become\s+a\s+cybersecurity professional", "become a Cybersecurity Professional"),
        (r"get\s+a\s+job", "get a job"),
        (r"career\s+in\s+data science", "career in Data Science"),
        (r"career\s+in\s+data analytics", "career in Data Analytics"),
        (r"career\s+in\s+devops", "career in DevOps"),
        (r"career\s+in\s+cybersecurity", "career in Cybersecurity"),
    ]
    for pattern, value in career_patterns:
        if re.search(pattern, normalized):
            if _set_field(profile, "career_goal", value, text):
                extracted.append("career_goal")
            break

    # Current role
    role_patterns = [
        (r"\b(i am|i'm|im)\s+(a\s+)?student\b", "student"),
        (r"\b(i am|i'm|im)\s+(a\s+)?developer\b", "developer"),
        (r"\b(i am|i'm|im)\s+(a\s+)?engineer\b", "engineer"),
        (r"\b(i am|i'm|im)\s+(a\s+)?analyst\b", "analyst"),
        (r"\b(i am|i'm|im)\s+(a\s+)?working professional\b", "working professional"),
    ]
    for pattern, value in role_patterns:
        if re.search(pattern, normalized):
            if _set_field(profile, "current_role", value, text):
                extracted.append("current_role")
            break

    # Region — only explicit geographic/market statements. Do not infer it.
    if re.search(r"\b(i am|i'm|im)\s+from\s+india\b", normalized) or "in india" in normalized:
        if _set_field(profile, "region", "India", text):
            extracted.append("region")
    elif "outside india" in normalized or "international" in normalized:
        if _set_field(profile, "region", "International", text):
            extracted.append("region")

    # Budget — preserve the user's stated amount without interpreting
    # affordability or converting currencies.
    budget_match = re.search(
        r"(?:budget|can spend|willing to spend|my budget)\D{0,20}"
        r"(₹\s?[\d,]+|\b\d+(?:\.\d+)?\s?(?:inr|usd|dollars?)\b)",
        normalized,
    )
    if budget_match:
        value = budget_match.group(1)
        if _set_field(profile, "budget", value, text):
            extracted.append("budget")

    return extracted


def update_prospect_profile(
    profile: ProspectProfile,
    user_message: str,
) -> QualificationResult:
    before = {
        name: getattr(profile, name).status
        for name in FIELD_NAMES
    }
    extracted = _extract(user_message, profile)

    known_count = sum(
        1 for name in FIELD_NAMES if getattr(profile, name).status == "known"
    )
    profile.profile_status = PROFILE_READY if known_count else PROFILE_EMPTY

    return QualificationResult(
        profile=copy.deepcopy(profile),
        newly_extracted_fields=[
            name for name in FIELD_NAMES
            if before[name] == "unknown" and getattr(profile, name).status == "known"
        ],
        evidence=[
            f"{name} explicitly stated by the user"
            for name in extracted
        ],
        no_invention=True,
    )


def identify_missing_fields(
    profile: ProspectProfile,
    required_fields: Optional[List[str]] = None,
) -> List[str]:
    fields = required_fields or ["learning_goal", "experience"]
    return [
        name for name in fields
        if name in FIELD_NAMES and getattr(profile, name).status != "known"
    ]


def qualify_for_recommendation(
    profile: ProspectProfile,
) -> QualificationResult:
    missing = identify_missing_fields(profile)

    if missing:
        return QualificationResult(
            profile=copy.deepcopy(profile),
            clarification_needed=True,
            clarification_reason=(
                "More student context is needed before making a narrowed "
                "course recommendation: " + ", ".join(missing)
            ),
            evidence=["required recommendation fields remain unknown"],
        )

    return QualificationResult(
        profile=copy.deepcopy(profile),
        clarification_needed=False,
        evidence=["required recommendation context is explicitly available"],
    )


def validate_prospect_profile(
    profile: ProspectProfile,
) -> Dict[str, Any]:
    errors = []

    if not profile.session_id.strip():
        errors.append("Profile session ID cannot be empty.")

    if profile.profile_status not in {
        PROFILE_READY,
        PROFILE_EMPTY,
        PROFILE_CLARIFICATION,
    }:
        errors.append("Invalid profile status.")

    for name in FIELD_NAMES:
        field = getattr(profile, name)
        if field.status not in {"unknown", "known"}:
            errors.append(f"Invalid status for {name}.")
        if field.status == "unknown" and field.value is not None:
            errors.append(f"Unknown field {name} cannot have a value.")
        if field.status == "known" and not field.value:
            errors.append(f"Known field {name} must have a value.")

    return {"valid": not errors, "errors": list(dict.fromkeys(errors))}


def profile_to_dict(profile: ProspectProfile) -> Dict[str, Any]:
    return {
        "session_id": profile.session_id,
        "profile_status": profile.profile_status,
        **{
            name: {
                "value": getattr(profile, name).value,
                "status": getattr(profile, name).status,
                "evidence": list(getattr(profile, name).evidence),
            }
            for name in FIELD_NAMES
        },
    }


def qualification_to_dict(
    result: QualificationResult,
) -> Dict[str, Any]:
    return {
        "profile": profile_to_dict(result.profile),
        "newly_extracted_fields": list(result.newly_extracted_fields),
        "clarification_needed": result.clarification_needed,
        "clarification_reason": result.clarification_reason,
        "evidence": list(result.evidence),
        "no_invention": result.no_invention,
    }


def build_prospect_qualification_layer() -> Any:
    from Sayyed_EdVantage_AI_CORE04 import build_recommendation_layer
    return build_recommendation_layer()
