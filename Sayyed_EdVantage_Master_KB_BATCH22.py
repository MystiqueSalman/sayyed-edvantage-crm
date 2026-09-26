"""
Sayyed EdVantage AI Agent — Master KB Batch 22
Unified Commercial Knowledge & Region-Aware Fee Layer

Purpose:
- Add the verified Indian commercial offerings to the unified Master KB.
- Keep international pricing explicitly undefined.
- Prevent Indian pricing from being substituted for international students.
- Provide deterministic, region-aware commercial lookup.
- Preserve no-invention and admissions handoff rules.
- Never send messages, execute actions, call external systems, or write CRM data.

Verified Indian base fees:
- Data Science: ₹50,000 + GST
- Data Analytics: ₹40,000 + GST
- Data Science + Data Analytics Combo: ₹80,000 + GST
- AI + Generative AI: ₹70,000 + GST
- Python: ₹35,000 + GST
- Linux: ₹25,000 + GST
- DevOps: ₹45,000 + GST
- Linux + DevOps Combo: ₹60,000 + GST
- Ethical Hacking & Cybersecurity: ₹60,000 + GST

International pricing is not currently defined.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import copy
import re

from Sayyed_EdVantage_Master_KB_BATCH21 import (
    build_master_kb_with_multi_course_answers,
)
from Sayyed_EdVantage_Master_KB_BATCH20 import (
    GroundedAnswer,
    answer_query,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import (
    build_response_plan,
)


COMMERCIAL_SOURCE_ID = "COMMERCIAL-FEE-INDIA-001"

INDIA_OFFERINGS = {
    "SE-OFFER-DS-INDIA": {
        "course_id": "SE-DS-001",
        "name": "Data Science",
        "fee": 50000,
    },
    "SE-OFFER-DA-INDIA": {
        "course_id": "SE-DA-001",
        "name": "Data Analytics",
        "fee": 40000,
    },
    "SE-OFFER-DSDA-COMBO-INDIA": {
        "course_id": None,
        "name": "Data Science + Data Analytics Combo",
        "fee": 80000,
    },
    "SE-OFFER-AIGEN-INDIA": {
        "course_id": "SE-AIGEN-001",
        "name": "AI + Generative AI",
        "fee": 70000,
    },
    "SE-OFFER-PY-INDIA": {
        "course_id": "SE-PY-001",
        "name": "Python",
        "fee": 35000,
    },
    "SE-OFFER-LINUX-INDIA": {
        "course_id": "SE-LINUX-001",
        "name": "Linux",
        "fee": 25000,
    },
    "SE-OFFER-DEVOPS-INDIA": {
        "course_id": "SE-DEVOPS-001",
        "name": "DevOps",
        "fee": 45000,
    },
    "SE-OFFER-LINUXDEVOPS-COMBO-INDIA": {
        "course_id": None,
        "name": "Linux + DevOps Combo",
        "fee": 60000,
    },
    "SE-OFFER-EHC-INDIA": {
        "course_id": "SE-EHC-001",
        "name": "Ethical Hacking & Cybersecurity",
        "fee": 60000,
    },
}


class CommercialKnowledgeLayer:
    def __init__(self):
        self.source_id = COMMERCIAL_SOURCE_ID
        self.region = "india"
        self.currency = "INR"
        self.tax_note = "GST/tax applicable"
        self.india_offerings = copy.deepcopy(INDIA_OFFERINGS)
        self.international_defined = False

    def list_offerings(self) -> List[Dict[str, Any]]:
        return [
            {
                "offering_id": offering_id,
                **copy.deepcopy(data),
                "region": self.region,
                "currency": self.currency,
                "tax_note": self.tax_note,
                "source_id": self.source_id,
            }
            for offering_id, data in self.india_offerings.items()
        ]

    def get_offering(self, offering_id: str) -> Optional[Dict[str, Any]]:
        data = self.india_offerings.get(offering_id)
        if data is None:
            return None
        result = copy.deepcopy(data)
        result.update({
            "offering_id": offering_id,
            "region": self.region,
            "currency": self.currency,
            "tax_note": self.tax_note,
            "source_id": self.source_id,
        })
        return result

    def get_india_fee(self, offering_id: str) -> Optional[int]:
        data = self.india_offerings.get(offering_id)
        return None if data is None else int(data["fee"])

    def find_india_offering_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        normalized = " ".join(str(name).lower().split())
        for offering_id, data in self.india_offerings.items():
            if normalized == " ".join(data["name"].lower().split()):
                return self.get_offering(offering_id)
        return None

    def get_international_fee(self, offering_id: str) -> None:
        # Intentionally undefined. Never fall back to an Indian fee.
        return None

    def validate(self) -> Dict[str, Any]:
        errors = []

        expected_names = {
            "Data Science",
            "Data Analytics",
            "Data Science + Data Analytics Combo",
            "AI + Generative AI",
            "Python",
            "Linux",
            "DevOps",
            "Linux + DevOps Combo",
            "Ethical Hacking & Cybersecurity",
        }

        actual_names = {x["name"] for x in self.list_offerings()}
        if actual_names != expected_names:
            errors.append("Indian commercial offering set does not match expected set.")

        for offering in self.list_offerings():
            if offering["fee"] <= 0:
                errors.append(f"Invalid fee for {offering['name']}.")
            if offering["currency"] != "INR":
                errors.append(f"Unexpected currency for {offering['name']}.")
            if offering["source_id"] != COMMERCIAL_SOURCE_ID:
                errors.append(f"Missing commercial provenance for {offering['name']}.")

        if self.international_defined is not False:
            errors.append("International pricing must remain undefined.")

        return {"valid": not errors, "errors": errors}


def add_commercial_knowledge(kb: Any) -> Any:
    layer = CommercialKnowledgeLayer()

    kb.commercial_layer = layer

    # Also register offerings using the Master KB's native offering model.
    # This does not alter course curriculum records.
    from Sayyed_EdVantage_Master_KB_BATCH20 import (
        build_master_kb_with_answer_generator,
    )
    from Sayyed_EdVantage_Master_KB_BATCH17 import (
        CommercialOffering,
        SourceRecord,
    )

    if COMMERCIAL_SOURCE_ID not in kb.sources:
        kb.register_source(SourceRecord(
            COMMERCIAL_SOURCE_ID,
            "Verified Indian Commercial Fee Source",
            "commercial_fee",
            version="1.0",
            status="approved",
            notes="User-supplied verified Indian base fee schedule; GST/tax applicable.",
        ))

    for offering_id, data in INDIA_OFFERINGS.items():
        kb.register_offering(CommercialOffering(
            offering_id=offering_id,
            name=data["name"],
            offering_type="course" if data["course_id"] else "combo",
            pricing_regions={
                "india": {
                    "base_fee": data["fee"],
                    "currency": "INR",
                    "tax_note": "GST/tax applicable",
                    "source_id": COMMERCIAL_SOURCE_ID,
                }
            },
            source_ids=[COMMERCIAL_SOURCE_ID],
        ))

    kb.set_common_knowledge(
        "commercial_source_id", COMMERCIAL_SOURCE_ID
    )
    kb.set_common_knowledge(
        "international_pricing_defined", False
    )
    kb.set_common_knowledge(
        "india_fee_tax_note", "GST/tax applicable"
    )

    return kb


def build_master_kb_with_commercial_knowledge() -> Any:
    kb = build_master_kb_with_multi_course_answers()
    return add_commercial_knowledge(kb)


def _course_aliases() -> Dict[str, List[str]]:
    return {
        "SE-DS-001": ["data science", "datascience"],
        "SE-DA-001": ["data analytics", "dataanalytics"],
        "SE-AIGEN-001": [
            "ai + generative ai",
            "ai and generative ai",
            "generative ai",
            "genai",
        ],
        "SE-PY-001": ["python"],
        "SE-LINUX-001": ["linux"],
        "SE-DEVOPS-001": ["devops"],
        "SE-EHC-001": [
            "ethical hacking",
            "cybersecurity",
            "ethical hacking & cybersecurity",
        ],
    }


def _find_matching_offering(query: str, layer: CommercialKnowledgeLayer):
    q = " ".join(query.lower().split())

    # Combo names first to prevent partial course-name ambiguity.
    combo_phrases = [
        "data science + data analytics combo",
        "data science and data analytics combo",
        "linux + devops combo",
        "linux and devops combo",
    ]

    for phrase in combo_phrases:
        if phrase in q:
            for offering in layer.list_offerings():
                if offering["name"].lower() == phrase:
                    return offering

    aliases = _course_aliases()
    candidates = []

    for offering in layer.list_offerings():
        name = offering["name"].lower()
        if name in q:
            candidates.append(offering)
            continue

        course_id = offering.get("course_id")
        if course_id:
            for alias in aliases.get(course_id, []):
                if alias in q:
                    candidates.append(offering)
                    break

    # Deterministic preference for the longest matched offering name.
    if candidates:
        candidates.sort(key=lambda x: (-len(x["name"]), x["offering_id"]))
        return candidates[0]

    return None


def get_commercial_answer(
    kb: Any,
    query: str,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return a safe commercial response record.

    Region handling:
    - india: verified Indian fee may be quoted.
    - international/non-India: fee remains undefined.
    - unspecified: no fee is quoted until region is known.
    """
    layer = getattr(kb, "commercial_layer", None)
    if layer is None:
        raise ValueError("Commercial knowledge layer is not installed.")

    q = query.lower()
    region_norm = (region or "").strip().lower()

    if not region_norm:
        if any(x in q for x in ("international", "outside india", "overseas", "abroad")):
            region_norm = "international"
        elif any(x in q for x in ("india", "indian", "inr", "₹", "rupees")):
            region_norm = "india"
        else:
            region_norm = "unknown"

    offering = _find_matching_offering(query, layer)

    if region_norm not in {"india", "international"}:
        return {
            "status": "REGION_REQUIRED",
            "offering": offering,
            "fee": None,
            "currency": None,
            "tax_note": None,
            "source_id": None,
            "message": (
                "The student's pricing region should be confirmed before "
                "quoting a fee."
            ),
            "human_handoff_required": False,
        }

    if region_norm != "india":
        return {
            "status": "INTERNATIONAL_UNDEFINED",
            "offering": offering,
            "fee": None,
            "currency": None,
            "tax_note": None,
            "source_id": COMMERCIAL_SOURCE_ID,
            "message": (
                "International pricing is not currently defined. "
                "Indian pricing must not be substituted. Admissions/team "
                "should provide the applicable fee and enrollment details."
            ),
            "human_handoff_required": True,
        }

    if offering is None:
        return {
            "status": "OFFERING_NOT_FOUND",
            "offering": None,
            "fee": None,
            "currency": None,
            "tax_note": None,
            "source_id": COMMERCIAL_SOURCE_ID,
            "message": (
                "A verified Indian fee for the requested offering could not "
                "be identified in the current commercial knowledge layer."
            ),
            "human_handoff_required": True,
        }

    return {
        "status": "VERIFIED_INDIA_FEE",
        "offering": offering,
        "fee": offering["fee"],
        "currency": "INR",
        "tax_note": offering["tax_note"],
        "source_id": COMMERCIAL_SOURCE_ID,
        "message": (
            f'{offering["name"]}: ₹{offering["fee"]:,} + GST. '
            "Admissions/team confirms the final fee, taxes, discounts, "
            "payment options, and enrollment details."
        ),
        "human_handoff_required": False,
    }


def validate_commercial_answer(record: Dict[str, Any]) -> Dict[str, Any]:
    errors = []

    valid_statuses = {
        "VERIFIED_INDIA_FEE",
        "INTERNATIONAL_UNDEFINED",
        "REGION_REQUIRED",
        "OFFERING_NOT_FOUND",
    }

    if record.get("status") not in valid_statuses:
        errors.append("Invalid commercial response status.")

    status = record.get("status")

    if status == "VERIFIED_INDIA_FEE":
        if record.get("fee") is None:
            errors.append("Verified Indian fee cannot be None.")
        if record.get("currency") != "INR":
            errors.append("Verified Indian fee must use INR.")
        if record.get("source_id") != COMMERCIAL_SOURCE_ID:
            errors.append("Verified fee must preserve commercial source ID.")
        if "Indian pricing must not be substituted" in record.get("message", ""):
            errors.append("India answer contains international fallback warning.")

    if status == "INTERNATIONAL_UNDEFINED":
        if record.get("fee") is not None:
            errors.append("International fee must remain undefined.")
        if record.get("currency") is not None:
            errors.append("International currency must remain undefined.")
        if record.get("human_handoff_required") is not True:
            errors.append("International pricing requires handoff.")
        if "Indian pricing must not be substituted" not in record.get("message", ""):
            errors.append("International no-India-fallback rule missing.")

    if status == "REGION_REQUIRED":
        if record.get("fee") is not None:
            errors.append("Fee must not be quoted before region is known.")

    return {"valid": not errors, "errors": errors}


def commercial_layer_snapshot(kb: Any) -> Dict[str, Any]:
    layer = getattr(kb, "commercial_layer", None)
    if layer is None:
        return {}
    return {
        "source_id": layer.source_id,
        "region": layer.region,
        "currency": layer.currency,
        "tax_note": layer.tax_note,
        "international_defined": layer.international_defined,
        "offerings": layer.list_offerings(),
    }


if __name__ == "__main__":
    kb = build_master_kb_with_commercial_knowledge()
    print("Commercial validation:",
          getattr(kb, "commercial_layer").validate())
    print(get_commercial_answer(
        kb, "What is the fee for Data Science in India?"
    ))
