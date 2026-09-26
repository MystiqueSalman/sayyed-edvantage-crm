from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from copy import deepcopy

KB_VERSION = "1.0"
KB_NAME = "Sayyed EdVantage Master Knowledge Base"

@dataclass
class SourceRecord:
    source_id: str
    title: str
    source_type: str
    version: str = "1.0"
    status: str = "approved"
    course_id: Optional[str] = None
    notes: str = ""

@dataclass
class CourseRecord:
    course_id: str
    official_name: str
    category: str
    status: str = "active"
    knowledge: Dict[str, Any] = field(default_factory=dict)
    source_ids: List[str] = field(default_factory=list)

@dataclass
class CommercialOffering:
    offering_id: str
    name: str
    offering_type: str
    pricing_regions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    source_ids: List[str] = field(default_factory=list)

class MasterKnowledgeBase:
    def __init__(self, version: str = KB_VERSION):
        self.name = KB_NAME
        self.version = version
        self.courses = {}
        self.offerings = {}
        self.common_knowledge = {}
        self.sources = {}

    def register_source(self, source: SourceRecord):
        if not source.source_id.strip():
            raise ValueError("source_id is required")
        self.sources[source.source_id] = deepcopy(source)

    def register_course(self, course: CourseRecord):
        if not course.course_id.strip():
            raise ValueError("course_id is required")
        if not course.official_name.strip():
            raise ValueError("official_name is required")
        self.courses[course.course_id] = deepcopy(course)

    def register_offering(self, offering: CommercialOffering):
        if not offering.offering_id.strip():
            raise ValueError("offering_id is required")
        self.offerings[offering.offering_id] = deepcopy(offering)

    def get_course(self, course_id):
        return deepcopy(self.courses.get(course_id))

    def list_courses(self):
        return [deepcopy(c) for c in self.courses.values()]

    def get_offering(self, offering_id):
        return deepcopy(self.offerings.get(offering_id))

    def get_fee(self, offering_id, region):
        offering = self.offerings.get(offering_id)
        if not offering:
            return None
        return deepcopy(offering.pricing_regions.get(region))

    def set_common_knowledge(self, key, value):
        self.common_knowledge[key] = deepcopy(value)

    def get_common_knowledge(self, key):
        return deepcopy(self.common_knowledge.get(key))

    def validate(self):
        errors = []
        for cid, course in self.courses.items():
            if cid != course.course_id or not course.official_name:
                errors.append(f"Invalid course: {cid}")
        for oid, offering in self.offerings.items():
            if oid != offering.offering_id:
                errors.append(f"Invalid offering: {oid}")
            intl = offering.pricing_regions.get("international", {})
            if intl.get("status") == "unknown" and intl.get("amount") is not None:
                errors.append(f"International pricing invented: {oid}")
        for sid, source in self.sources.items():
            if sid != source.source_id:
                errors.append(f"Invalid source: {sid}")
        return {
            "valid": not errors, "errors": errors,
            "course_count": len(self.courses),
            "offering_count": len(self.offerings),
            "source_count": len(self.sources),
            "kb_version": self.version,
        }

    def export_snapshot(self):
        return {
            "kb_name": self.name,
            "kb_version": self.version,
            "courses": {k: asdict(v) for k, v in self.courses.items()},
            "offerings": {k: asdict(v) for k, v in self.offerings.items()},
            "common_knowledge": deepcopy(self.common_knowledge),
            "sources": {k: asdict(v) for k, v in self.sources.items()},
        }

def build_master_kb():
    kb = MasterKnowledgeBase()
    kb.set_common_knowledge("commercial_policy", {
        "india_pricing": "May be quoted only when verified for the Indian student.",
        "international_pricing": "Not currently defined. Do not quote Indian pricing to international students.",
        "unknown_pricing_action": "Explain course information normally, then hand fee/details to admissions.",
        "no_invention": True,
    })
    kb.register_course(CourseRecord(
        course_id="SE-DSP-001",
        official_name="Data Science – Professional Program",
        category="Data Science",
    ))
    kb.register_offering(CommercialOffering(
        offering_id="SE-DSP-001",
        name="Data Science – Professional Program",
        offering_type="course",
        pricing_regions={
            "india": {
                "status": "verified_user_supplied",
                "currency": "INR",
                "amount": 50000,
                "tax_note": "Applicable taxes/details to be confirmed by admissions.",
            },
            "international": {
                "status": "unknown",
                "currency": None,
                "amount": None,
                "note": "International pricing will be supplied later. Never substitute Indian pricing.",
            },
        },
    ))
    return kb

MASTER_KB = build_master_kb()
