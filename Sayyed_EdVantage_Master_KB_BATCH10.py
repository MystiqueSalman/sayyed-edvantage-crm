from copy import deepcopy
from typing import Any, Dict, List


CONFLICT_POLICIES = {
    "source_priority": [
        "approved_current_source",
        "draft_source",
        "deprecated_or_superseded_source",
        "unsupported_or_unknown",
    ],
    "same_priority_conflict": "do_not_invent; flag_for_human_review",
    "missing_information": "return_unknown_or_admissions_handoff",
    "commercial_conflict": "use_verified_region_specific_value_only",
    "international_pricing": "never_substitute_india_pricing",
}


SAFETY_INVARIANTS = {
    "no_invention": True,
    "provenance_required": True,
    "course_isolation": True,
    "execution_allowed": False,
    "message_sending_allowed": False,
    "external_actions_allowed": False,
    "crm_write_allowed": False,
}


def get_conflict_policies() -> Dict[str, Any]:
    return deepcopy(CONFLICT_POLICIES)


def get_safety_invariants() -> Dict[str, Any]:
    return deepcopy(SAFETY_INVARIANTS)


def classify_source_status(status: str) -> str:
    if status == "approved":
        return "approved_current_source"
    if status == "draft":
        return "draft_source"
    if status in {"deprecated", "superseded"}:
        return "deprecated_or_superseded_source"
    return "unsupported_or_unknown"


def rank_source_status(status: str) -> int:
    classification = classify_source_status(status)
    return {
        "approved_current_source": 0,
        "draft_source": 1,
        "deprecated_or_superseded_source": 2,
        "unsupported_or_unknown": 3,
    }[classification]


def validate_source_conflicts(kb) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    for course in kb.courses.values():
        seen = {}
        for source_id in course.source_ids:
            source = kb.sources.get(source_id)
            if source is None:
                errors.append(
                    f"{course.course_id}: missing source {source_id}"
                )
                continue

            # A current course should not directly rely on deprecated/superseded
            # sources without an approved current source.
            if source.status in {"deprecated", "superseded"}:
                warnings.append(
                    f"{course.course_id}: deprecated/superseded source {source_id} is referenced"
                )

            key = (source.title, source.course_id)
            seen.setdefault(key, []).append(source)

        # Multiple approved sources with the same title are a potential conflict.
        for key, sources in seen.items():
            approved = [s for s in sources if s.status == "approved"]
            if len(approved) > 1:
                versions = {s.version for s in approved}
                if len(versions) > 1:
                    errors.append(
                        f"{course.course_id}: multiple approved versions for {key[0]}"
                    )
                else:
                    warnings.append(
                        f"{course.course_id}: duplicate approved source records for {key[0]}"
                    )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def validate_commercial_safety(kb) -> Dict[str, Any]:
    errors: List[str] = []

    for offering in kb.offerings.values():
        india = offering.pricing_regions.get("india", {})
        international = offering.pricing_regions.get("international", {})

        # International pricing must not silently inherit India.
        if international.get("base_fee") is not None and international.get("currency") == "INR":
            errors.append(
                f"{offering.offering_id}: international pricing must not silently use Indian INR pricing"
            )

        # If an international amount exists, it must have a currency.
        if international.get("base_fee") is not None and not international.get("currency"):
            errors.append(
                f"{offering.offering_id}: international fee has no currency"
            )

        # India values must be explicit rather than inferred.
        if india.get("base_fee") is not None and not india.get("currency"):
            errors.append(
                f"{offering.offering_id}: India fee has no currency"
            )

    return {"valid": not errors, "errors": errors}


def validate_safety_contract(kb) -> Dict[str, Any]:
    errors = []

    if SAFETY_INVARIANTS["execution_allowed"]:
        errors.append("Execution must remain disabled.")
    if SAFETY_INVARIANTS["message_sending_allowed"]:
        errors.append("Message sending must remain disabled.")
    if SAFETY_INVARIANTS["external_actions_allowed"]:
        errors.append("External actions must remain disabled.")
    if SAFETY_INVARIANTS["crm_write_allowed"]:
        errors.append("CRM writes must remain disabled.")

    # Retrieval metadata from Batch 08 must remain safe.
    for course in kb.courses.values():
        metadata = course.knowledge.get("retrieval_metadata", {})
        if metadata.get("enabled") is True:
            if metadata.get("execution_allowed") is not False:
                errors.append(
                    f"{course.course_id}: retrieval execution_allowed must be False"
                )

    return {"valid": not errors, "errors": errors}


def validate_batch10(kb) -> Dict[str, Any]:
    source_report = validate_source_conflicts(kb)
    commercial_report = validate_commercial_safety(kb)
    safety_report = validate_safety_contract(kb)

    return {
        "valid": (
            source_report["valid"]
            and commercial_report["valid"]
            and safety_report["valid"]
        ),
        "source_conflicts": source_report,
        "commercial_safety": commercial_report,
        "safety_contract": safety_report,
        "policies": get_conflict_policies(),
        "safety_invariants": get_safety_invariants(),
    }


def add_batch10_to_master_kb(kb):
    report = validate_batch10(kb)
    if not report["valid"]:
        raise ValueError(report)

    kb.set_common_knowledge("conflict_control", {
        "enabled": True,
        "policies": get_conflict_policies(),
        "last_validation": "passed",
    })
    kb.set_common_knowledge("safety_contract", get_safety_invariants())
    return kb


def build_master_kb_with_batch10():
    from Sayyed_EdVantage_Master_KB_BATCH09 import build_master_kb_with_batch09
    return add_batch10_to_master_kb(build_master_kb_with_batch09())
