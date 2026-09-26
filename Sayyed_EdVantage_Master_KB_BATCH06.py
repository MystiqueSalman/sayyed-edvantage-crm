from copy import deepcopy
from typing import Any, Dict, List

DATA_SCIENCE_COURSE_ID = "SE-DSP-001"
INDIA_REGION = "india"
INTERNATIONAL_REGION = "international"

INDIA_FEE_SOURCE_ID = "COMMERCIAL-FEE-INDIA-001"

DATA_SCIENCE_INDIA_COMMERCIAL = {
    "offering_id": DATA_SCIENCE_COURSE_ID,
    "course_id": DATA_SCIENCE_COURSE_ID,
    "region": INDIA_REGION,
    "pricing_status": "verified_user_supplied",
    "currency": "INR",
    "base_fee": 50000,
    "gst": "Applicable GST / tax as applicable; exact tax amount to be confirmed by admissions.",
    "final_fee": None,
    "discount": None,
    "payment_plans": [],
    "notes": (
        "₹50,000 is the supplied Indian base fee. GST/tax, discounts, "
        "payment plans and final payable amount are not specified here."
    ),
    "audience_rule": "Indian students only.",
    "handoff": (
        "Admissions/team will connect with the student to confirm the final "
        "fee, applicable taxes and enrollment/payment details."
    ),
}

DATA_SCIENCE_INTERNATIONAL_COMMERCIAL = {
    "offering_id": DATA_SCIENCE_COURSE_ID,
    "course_id": DATA_SCIENCE_COURSE_ID,
    "region": INTERNATIONAL_REGION,
    "pricing_status": "unknown",
    "currency": None,
    "base_fee": None,
    "gst": None,
    "final_fee": None,
    "discount": None,
    "payment_plans": [],
    "notes": (
        "International pricing has not yet been supplied. Indian pricing "
        "must never be substituted or presented as international pricing."
    ),
    "audience_rule": "International students.",
    "handoff": (
        "Explain the course normally, then direct the student to the "
        "admissions/team for applicable international fee and enrollment details."
    ),
}

COMMERCIAL_RULES = {
    "india": {
        "can_quote_base_fee": True,
        "fee": 50000,
        "currency": "INR",
        "tax": "GST/tax applicable; final tax amount to be confirmed by admissions.",
        "final_fee_known": False,
    },
    "international": {
        "can_quote_india_fee": False,
        "pricing_status": "unknown",
        "fee": None,
        "currency": None,
        "fallback_to_india": False,
    },
    "global": {
        "no_invention": True,
        "no_region_fallback": True,
        "admissions_confirmation_required_for_final_details": True,
    },
}


def get_data_science_india_fee() -> Dict[str, Any]:
    return deepcopy(DATA_SCIENCE_INDIA_COMMERCIAL)


def get_data_science_international_fee() -> Dict[str, Any]:
    return deepcopy(DATA_SCIENCE_INTERNATIONAL_COMMERCIAL)


def get_commercial_rules() -> Dict[str, Any]:
    return deepcopy(COMMERCIAL_RULES)


def get_fee_for_region(region: str) -> Dict[str, Any]:
    normalized = (region or "").strip().lower()
    if normalized == INDIA_REGION:
        return get_data_science_india_fee()
    if normalized == INTERNATIONAL_REGION:
        return get_data_science_international_fee()
    return {
        "region": normalized,
        "pricing_status": "unknown",
        "currency": None,
        "base_fee": None,
        "final_fee": None,
        "note": "Region-specific pricing is not available from the current source."
    }


def validate_batch06() -> Dict[str, Any]:
    errors: List[str] = []

    india = DATA_SCIENCE_INDIA_COMMERCIAL
    international = DATA_SCIENCE_INTERNATIONAL_COMMERCIAL

    if india["course_id"] != DATA_SCIENCE_COURSE_ID:
        errors.append("India fee course ID mismatch.")
    if india["region"] != INDIA_REGION:
        errors.append("India region mismatch.")
    if india["currency"] != "INR":
        errors.append("India currency must be INR.")
    if india["base_fee"] != 50000:
        errors.append("India Data Science base fee must be 50000.")
    if india["pricing_status"] != "verified_user_supplied":
        errors.append("India pricing source status is incorrect.")

    if international["pricing_status"] != "unknown":
        errors.append("International pricing must remain unknown.")
    if international["base_fee"] is not None:
        errors.append("International base fee must not be invented.")
    if international["currency"] is not None:
        errors.append("International currency must remain unspecified.")
    if COMMERCIAL_RULES["international"]["fallback_to_india"] is not False:
        errors.append("International-to-India pricing fallback must be disabled.")

    if COMMERCIAL_RULES["global"]["no_invention"] is not True:
        errors.append("Commercial no-invention rule missing.")

    return {
        "valid": not errors,
        "errors": errors,
        "india_base_fee": india["base_fee"],
        "india_currency": india["currency"],
        "international_status": international["pricing_status"],
    }


def add_batch06_to_master_kb(kb):
    report = validate_batch06()
    if not report["valid"]:
        raise ValueError(report["errors"])

    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    offering = kb.get_offering(DATA_SCIENCE_COURSE_ID)

    if course is None or offering is None:
        raise KeyError("Data Science course/offering is missing from Master KB.")

    commercial_knowledge = {
        "india": get_data_science_india_fee(),
        "international": get_data_science_international_fee(),
        "rules": get_commercial_rules(),
    }

    course_knowledge = deepcopy(course.knowledge)
    course_knowledge["commercial_knowledge"] = commercial_knowledge
    course.knowledge = course_knowledge
    kb.register_course(course)

    offering.pricing_regions = {
        INDIA_REGION: get_data_science_india_fee(),
        INTERNATIONAL_REGION: get_data_science_international_fee(),
    }
    offering.source_ids = [INDIA_FEE_SOURCE_ID]
    kb.register_offering(offering)

    from Sayyed_EdVantage_Master_KB_BATCH01 import SourceRecord
    kb.register_source(SourceRecord(
        source_id=INDIA_FEE_SOURCE_ID,
        title="Data Science Indian Commercial Fee",
        source_type="user_supplied_commercial_fee",
        version="1.0",
        status="approved",
        course_id=DATA_SCIENCE_COURSE_ID,
        notes="Supplied Indian fee: ₹50,000 base fee; GST/tax applicable as confirmed by admissions."
    ))

    return kb


def build_master_kb_with_batch06():
    from Sayyed_EdVantage_Master_KB_BATCH05 import build_master_kb_with_batch05
    return add_batch06_to_master_kb(build_master_kb_with_batch05())
