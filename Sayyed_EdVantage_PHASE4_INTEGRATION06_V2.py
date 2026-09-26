from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge

def build_master_kb_commercial_bridge(project_root: Optional[str] = None):
    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parent
    bridge = build_authoritative_live_bridge(project_root=str(root), require_offerings=True)
    if getattr(bridge, "status", None) != "BRIDGE_READY":
        errors = getattr(bridge, "errors", None) or ["unknown bridge error"]
        raise RuntimeError("AUTHORITATIVE_MASTER_KB_UNAVAILABLE: " + "; ".join(map(str, errors)))
    return bridge

def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())

def get_master_kb_course(course_name: str, project_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    bridge = build_master_kb_commercial_bridge(project_root)
    q = _norm(course_name)
    for course in getattr(bridge, "courses", []) or []:
        if not isinstance(course, dict):
            continue
        values = [course.get("course_id"), course.get("official_name"), course.get("course_name")]
        aliases = course.get("aliases", [])
        if isinstance(aliases, list):
            values.extend(aliases)
        if any(_norm(v) == q for v in values if v):
            return dict(course)
    return None

def _fee(pricing: Dict[str, Any]):
    for key in ("fee_inr", "final_fee_inr", "price_inr", "amount_inr"):
        value = pricing.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None

def get_master_kb_offering(course_name: str, region: str = "India",
                           project_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    bridge = build_master_kb_commercial_bridge(project_root)
    q, r = _norm(course_name), _norm(region)
    for offering in getattr(bridge, "offerings", []) or []:
        if not isinstance(offering, dict):
            continue
        vals = [offering.get("offering_id"), offering.get("name"), offering.get("course_id")]
        if not any(q == _norm(v) or (q and q in _norm(v)) for v in vals if v):
            continue
        regions = offering.get("pricing_regions", {})
        if not isinstance(regions, dict):
            continue
        for region_name, pricing in regions.items():
            if _norm(region_name) == r and isinstance(pricing, dict):
                result = dict(pricing)
                result["_offering_id"] = offering.get("offering_id")
                result["_offering_name"] = offering.get("name")
                result["_source_ids"] = list(offering.get("source_ids", []) or [])
                fee = _fee(result)
                if fee is not None:
                    result["fee_inr"] = fee
                return result
    return None

def get_master_kb_pricing(course_name: str, international: bool = False,
                          region: str = "India",
                          project_root: Optional[str] = None):
    if international:
        if _norm(region) == "india":
            return None
        return get_master_kb_offering(course_name, region, project_root)
    return get_master_kb_offering(course_name, "India", project_root)

def validate_no_legacy_pricing_path(source_text: str) -> list[str]:
    errors = []
    if "from app.ai.knowledge import get_course_pricing" in source_text:
        errors.append("legacy pricing import remains")
    if "get_course_pricing(" in source_text:
        errors.append("legacy pricing call remains")
    return errors
