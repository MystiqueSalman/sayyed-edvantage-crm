"""Phase 4 Integration 04 tests."""

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import tempfile
import sys

MODULE_PATH = Path(__file__).with_name(
    "Sayyed_EdVantage_PHASE4_INTEGRATION04.py"
)
spec = importlib.util.spec_from_file_location("phase4_i04", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@dataclass
class FakeCourse:
    course_id: str
    official_name: str
    category: str
    status: str = "active"
    knowledge: dict = None
    source_ids: list = None

    def __post_init__(self):
        self.knowledge = self.knowledge or {}
        self.source_ids = self.source_ids or ["MASTER-SOURCE"]


@dataclass
class FakeOffering:
    offering_id: str
    name: str
    offering_type: str
    pricing_regions: dict
    source_ids: list


class FakeMasterKB:
    def __init__(self):
        self.courses = {
            "SE-DS-001": FakeCourse(
                "SE-DS-001", "Data Science", "Data Science",
                knowledge={"duration_hours": 60}
            ),
            "SE-EHC-001": FakeCourse(
                "SE-EHC-001",
                "Ethical Hacking & Cybersecurity",
                "Cybersecurity",
                knowledge={"duration_hours": 60}
            ),
        }
        self.offerings = {
            "SE-OFFER-DS-INDIA": FakeOffering(
                "SE-OFFER-DS-INDIA", "Data Science", "course",
                {"India": {"fee": 50000, "currency": "INR"}},
                ["COMMERCIAL-FEE-INDIA-001"],
            ),
            "SE-OFFER-EHC-INDIA": FakeOffering(
                "SE-OFFER-EHC-INDIA",
                "Ethical Hacking & Cybersecurity",
                "course",
                {"India": {"fee": 60000, "currency": "INR"}},
                ["COMMERCIAL-FEE-INDIA-001"],
            ),
        }

    def list_courses(self):
        return list(self.courses.values())


def check(label, condition):
    if not condition:
        raise AssertionError(label)


def main():
    passed = 0
    total = 0

    def t(label, condition):
        nonlocal passed, total
        total += 1
        check(label, condition)
        passed += 1
        print(f"PASS: {label}")

    result = module.build_live_knowledge_bridge(FakeMasterKB())

    t("bridge ready", result.status == "BRIDGE_READY")
    t("Master KB source of truth", result.source_of_truth == "MASTER_KB")
    t("two courses exposed", len(result.courses) == 2)
    t("EHC course exposed", "SE-EHC-001" in result.course_ids)
    t("two offerings exposed", len(result.offerings) == 2)
    t("EHC offering exposed", "SE-OFFER-EHC-INDIA" in result.offering_ids)
    t("Master KB provenance", result.provenance == ["MASTER_KB"])
    t("legacy catalog disabled", result.legacy_catalog_allowed is False)

    t("execution disabled", result.action_flags["execution_allowed"] is False)
    t("CRM write disabled", result.action_flags["crm_write"] is False)
    t("message send disabled", result.action_flags["message_send"] is False)
    t("external action disabled", result.action_flags["external_action"] is False)
    t("bridge validation clean", module.validate_bridge(result) == [])

    ehc = module.get_live_course(result, "SE-EHC-001")
    t("EHC lookup works", ehc["official_name"] == "Ethical Hacking & Cybersecurity")

    offer = module.get_live_offering(result, "SE-OFFER-EHC-INDIA")
    t("commercial provenance preserved",
      offer["source_ids"] == ["COMMERCIAL-FEE-INDIA-001"])
    t("Indian EHC fee preserved",
      offer["pricing_regions"]["India"]["fee"] == 60000)

    found = module.find_live_courses(result, "ethical hacking")
    t("EHC search works", len(found) == 1)
    t("EHC search ID correct", found[0]["course_id"] == "SE-EHC-001")

    ehc["official_name"] = "MUTATED"
    t("course lookup defensive copy",
      module.get_live_course(result, "SE-EHC-001")["official_name"]
      != "MUTATED")

    snap = module.bridge_to_dict(result)
    snap["courses"][0]["official_name"] = "MUTATED"
    t("snapshot defensive copy",
      result.courses[0]["official_name"] != "MUTATED")
    t("serialization validates",
      module.validate_serialized_bridge(module.bridge_to_dict(result)) == [])

    class EmptyKB:
        offerings = {}
        def list_courses(self):
            return []

    blocked = module.build_live_knowledge_bridge(EmptyKB())
    t("empty KB blocks", blocked.status == "BRIDGE_BLOCKED")
    t("blocked has diagnostic", bool(blocked.errors))
    t("blocked no legacy fallback",
      blocked.legacy_catalog_allowed is False)
    t("blocked remains safe",
      all(v is False for v in blocked.action_flags.values()))

    class DuplicateKB:
        offerings = {
            "OFF": FakeOffering("OFF", "A", "course", {}, [])
        }
        def list_courses(self):
            return [
                FakeCourse("DUP", "A", "A"),
                FakeCourse("DUP", "B", "B"),
            ]

    dup = module.build_live_knowledge_bridge(DuplicateKB())
    t("duplicate IDs block", dup.status == "BRIDGE_BLOCKED")
    t("duplicate error explicit",
      any("Duplicate course_id" in e for e in dup.errors))

    class BadKB:
        offerings = {
            "OFF": FakeOffering("OFF", "A", "course", {}, [])
        }
        def list_courses(self):
            return [FakeCourse("", "Missing ID", "X")]

    bad = module.build_live_knowledge_bridge(BadKB())
    t("malformed course blocks", bad.status == "BRIDGE_BLOCKED")
    t("malformed course diagnostic", bool(bad.errors))

    source = MODULE_PATH.read_text(encoding="utf-8")
    # The bridge may mention the legacy filename only inside its static guard;
    # there must be no executable dependency on the legacy loader.
    runtime_source = source.split("def validate_no_legacy_catalog_dependency", 1)[0]
    t("bridge has no legacy runtime dependency",
      "load_courses(" not in runtime_source)
    t("bridge does not import legacy loader",
      "from app.ai.knowledge import load_courses" not in source)

    with tempfile.TemporaryDirectory() as tmp:
        wrapper = module.build_authoritative_live_bridge(
            project_root=tmp,
            module_names=("missing_master_kb_module",),
        )

    t("missing Master KB blocks", wrapper.status == "BRIDGE_BLOCKED")
    t("missing Master KB diagnostic", bool(wrapper.errors))
    t("missing Master KB no fallback",
      wrapper.legacy_catalog_allowed is False)
    t("wrapper remains safe",
      all(v is False for v in wrapper.action_flags.values()))

    print()
    print(f"PHASE 4 INTEGRATION 04 TEST RESULT: {passed}/{total} PASSED")
    print("RETURN CODE: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
