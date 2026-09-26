from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge

def _project_root(project_root: Optional[str] = None) -> Path:
    return Path(project_root).resolve() if project_root else Path(__file__).resolve().parent

def build_master_kb_commercial_bridge(project_root: Optional[str] = None):
    root = _project_root(project_root)
    bridge = build_authoritative_live_bridge(project_root=str(root), require_offerings=True)
    if getattr(bridge, "status", None) != "BRIDGE_READY":
        errors = getattr(bridge, "errors", None) or ["unknown bridge error"]
        raise RuntimeError("AUTHORITATIVE_MASTER_KB_UNAVAILABLE: " + "; ".join(map(str, errors)))
    return bridge

def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())

def _course_matches(query: str, course: Dict[str, Any]) -> bool:
    q = _normalize(query)
    names = [course.get("course_id"), course.get("official_name"), course.get("course_name")]
    aliases = course.get("aliases", [])
    if isinstance(aliases, list):
        names.extend(aliases)
    return bool(q) and any(_normalize(x) == q for x in names if x)

def get_master_kb_course(course_name: str, project_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    bridge = build_master_kb_commercial_bridge(project_root)
    courses = getattr(bridge, "courses", []) or []
    for course in courses:
        if isinstance(course, dict) and _course_matches(course_name, course):
            return dict(course)
    q = _normalize(course_name)
    for course in courses:
        if not isinstance(course, dict):
            continue
        names = [_normalize(course.get("official_name")), _normalize(course.get("course_name"))]
        if q and any(q in n or n in q for n in names if n):
            return dict(course)
    return None

def get_master_kb_offering(course_name: str, region: str = "India",
                           project_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    bridge = build_master_kb_commercial_bridge(project_root)
    q, region_key = _normalize(course_name), _normalize(region)
    for offering in getattr(bridge, "offerings", []) or []:
        if not isinstance(offering, dict):
            continue
        name = _normalize(offering.get("name"))
        oid = _normalize(offering.get("offering_id"))
        cid = _normalize(offering.get("course_id"))
        if not (q == name or q == oid or q == cid or (q and (q in name or q in oid))):
            continue
        regions = offering.get("pricing_regions", {})
        if not isinstance(regions, dict):
            continue
        for key, pricing in regions.items():
            if _normalize(key) == region_key and isinstance(pricing, dict):
                result = dict(pricing)
                result["_offering_id"] = offering.get("offering_id")
                result["_offering_name"] = offering.get("name")
                result["_source_ids"] = list(offering.get("source_ids", []) or [])
                return result
    return None

def get_master_kb_pricing(course_name: str, international: bool = False,
                          region: str = "India",
                          project_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if international:
        if _normalize(region) == "india":
            return None
        return get_master_kb_offering(course_name, region, project_root)
    return get_master_kb_offering(course_name, "India", project_root)

def validate_no_legacy_pricing_path(source_text: str) -> list[str]:
    errors = []
    if "get_course_pricing(" in source_text:
        errors.append("legacy get_course_pricing call remains")
    if "from app.ai.knowledge import get_course_pricing" in source_text:
        errors.append("legacy get_course_pricing import remains")
    return errors
