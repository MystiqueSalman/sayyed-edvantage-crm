from pathlib import Path
from Sayyed_EdVantage_PHASE4_INTEGRATION06_V2 import (
    build_master_kb_commercial_bridge, get_master_kb_course,
    get_master_kb_offering, get_master_kb_pricing,
    validate_no_legacy_pricing_path,
)
ROOT = Path(__file__).resolve().parent
def check(name, condition):
    if not condition:
        print("FAIL:", name)
        raise SystemExit(1)
    print("PASS:", name)
def main():
    bridge = build_master_kb_commercial_bridge(str(ROOT))
    check("Master KB bridge ready", bridge.status == "BRIDGE_READY")
    check("courses come from Master KB bridge", isinstance(bridge.courses, list) and len(bridge.courses) >= 1)
    check("commercial offerings come from Master KB bridge", isinstance(bridge.offerings, list) and len(bridge.offerings) >= 1)
    check("Data Science resolved from Master KB", isinstance(get_master_kb_course("Data Science", str(ROOT)), dict))
    india = get_master_kb_pricing("Data Science", False, "India", str(ROOT))
    check("India pricing resolved from Master KB", isinstance(india, dict))
    check("India fee is 50000", india.get("fee_inr") == 50000)
    offer = get_master_kb_offering("Data Science", "India", str(ROOT))
    check("India offering resolved", isinstance(offer, dict))
    check("commercial provenance retained", bool(offer.get("_source_ids")))
    check("international does not substitute India", get_master_kb_pricing("Data Science", True, "India", str(ROOT)) is None)
    check("unconfigured USA pricing fails closed", get_master_kb_pricing("Data Science", True, "USA", str(ROOT)) is None)
    old = "from app.ai.knowledge import get_course_pricing\npricing = get_course_pricing(course_name, international=True)"
    check("legacy detector catches old import and call", len(validate_no_legacy_pricing_path(old)) == 2)
    print("\nPHASE 4 INTEGRATION 06 V2 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")
if __name__ == "__main__":
    main()
