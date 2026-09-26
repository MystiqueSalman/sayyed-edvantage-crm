"""
Sayyed EdVantage — Phase 4 Integration 04
Master KB -> Live Agent Knowledge Bridge

The Master Knowledge Base is the authoritative source.
This bridge contains NO duplicate course catalog and never falls back to
data/knowledge/courses.json.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import copy
import importlib.util


BRIDGE_VERSION = "1.0"
SOURCE_OF_TRUTH = "MASTER_KB"

ACTION_FLAGS = {
    "execution_allowed": False,
    "executor_invoked": False,
    "crm_write": False,
    "message_send": False,
    "external_action": False,
}

DEFAULT_MASTER_KB_MODULES = (
    "app.ai.master_kb",
    "app.ai.knowledge.master_kb",
    "Sayyed_EdVantage_Master_KB_BATCH30",
    "Sayyed_EdVantage_Master_KB_BATCH29",
    "Sayyed_EdVantage_Master_KB_BATCH26",
    "Sayyed_EdVantage_Master_KB_BATCH22",
    "Sayyed_EdVantage_Master_KB_BATCH01",
)


class MasterKBBridgeError(RuntimeError):
    pass


@dataclass
class KnowledgeBridgeResult:
    status: str
    source: str = SOURCE_OF_TRUTH
    bridge_version: str = BRIDGE_VERSION
    courses: List[Dict[str, Any]] = field(default_factory=list)
    offerings: List[Dict[str, Any]] = field(default_factory=list)
    course_ids: List[str] = field(default_factory=list)
    offering_ids: List[str] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    source_of_truth: str = SOURCE_OF_TRUTH
    legacy_catalog_allowed: bool = False
    action_flags: Dict[str, bool] = field(
        default_factory=lambda: copy.deepcopy(ACTION_FLAGS)
    )

    @property
    def ready(self) -> bool:
        return self.status == "BRIDGE_READY"


def _deepcopy(value: Any) -> Any:
    return copy.deepcopy(value)


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return _deepcopy(value)
    if hasattr(value, "__dataclass_fields__"):
        return _deepcopy(asdict(value))
    if hasattr(value, "__dict__"):
        return _deepcopy(vars(value))
    raise MasterKBBridgeError(
        f"Unsupported Master KB record type: {type(value).__name__}"
    )


def _normalise_course(course: Any) -> Dict[str, Any]:
    raw = _as_dict(course)
    knowledge = raw.get("knowledge")
    if not isinstance(knowledge, dict):
        knowledge = {}

    result = dict(raw)
    result["course_id"] = (
        raw.get("course_id")
        or raw.get("id")
        or knowledge.get("course_id")
        or ""
    )
    result["official_name"] = (
        raw.get("official_name")
        or raw.get("course_name")
        or raw.get("name")
        or knowledge.get("official_name")
        or knowledge.get("course_name")
        or ""
    )
    result["category"] = raw.get("category") or knowledge.get("category") or ""
    result["status"] = raw.get("status", "active")
    result["knowledge"] = _deepcopy(knowledge)
    result["source_ids"] = _deepcopy(
        raw.get("source_ids") or knowledge.get("source_ids") or []
    )

    if not result["course_id"] or not result["official_name"]:
        raise MasterKBBridgeError(
            "Master KB contains a course without course_id or official_name."
        )
    return result


def _normalise_offering(offering: Any) -> Dict[str, Any]:
    raw = _as_dict(offering)
    result = dict(raw)
    result["offering_id"] = raw.get("offering_id") or raw.get("id") or ""
    result["name"] = raw.get("name") or raw.get("official_name") or ""
    result["offering_type"] = raw.get("offering_type") or ""
    result["pricing_regions"] = _deepcopy(raw.get("pricing_regions") or {})
    result["source_ids"] = _deepcopy(raw.get("source_ids") or [])

    if not result["offering_id"] or not result["name"]:
        raise MasterKBBridgeError(
            "Master KB contains an offering without offering_id or name."
        )
    return result


def _validate_unique(records: List[Dict[str, Any]], key: str) -> None:
    ids = [str(record[key]) for record in records]
    if len(ids) != len(set(ids)):
        raise MasterKBBridgeError(f"Duplicate {key} values detected.")


def build_live_knowledge_bridge(
    master_kb: Any,
    *,
    require_offerings: bool = True,
) -> KnowledgeBridgeResult:
    """Build a read-only snapshot from the authoritative Master KB."""
    try:
        if master_kb is None or not hasattr(master_kb, "list_courses"):
            raise MasterKBBridgeError(
                "Master KB does not expose list_courses()."
            )

        raw_courses = master_kb.list_courses()
        if not isinstance(raw_courses, (list, tuple)):
            raise MasterKBBridgeError(
                "Master KB list_courses() did not return a list."
            )
        courses = [_normalise_course(course) for course in raw_courses]

        raw_offerings = getattr(master_kb, "offerings", None)
        if isinstance(raw_offerings, dict):
            values = list(raw_offerings.values())
        elif isinstance(raw_offerings, (list, tuple)):
            values = list(raw_offerings)
        elif hasattr(master_kb, "list_offerings"):
            values = list(master_kb.list_offerings())
        else:
            values = []

        offerings = [_normalise_offering(offering) for offering in values]

        if not courses:
            raise MasterKBBridgeError(
                "Authoritative Master KB returned no courses."
            )
        if require_offerings and not offerings:
            raise MasterKBBridgeError(
                "Authoritative Master KB returned no commercial offerings."
            )

        _validate_unique(courses, "course_id")
        if offerings:
            _validate_unique(offerings, "offering_id")

        return KnowledgeBridgeResult(
            status="BRIDGE_READY",
            courses=_deepcopy(courses),
            offerings=_deepcopy(offerings),
            course_ids=[c["course_id"] for c in courses],
            offering_ids=[o["offering_id"] for o in offerings],
            provenance=["MASTER_KB"],
        )

    except Exception as exc:
        return KnowledgeBridgeResult(
            status="BRIDGE_BLOCKED",
            errors=[str(exc)],
        )


def get_live_course(
    bridge: KnowledgeBridgeResult,
    course_id: str,
) -> Optional[Dict[str, Any]]:
    if not bridge.ready:
        return None
    for course in bridge.courses:
        if course.get("course_id") == course_id:
            return _deepcopy(course)
    return None


def get_live_offering(
    bridge: KnowledgeBridgeResult,
    offering_id: str,
) -> Optional[Dict[str, Any]]:
    if not bridge.ready:
        return None
    for offering in bridge.offerings:
        if offering.get("offering_id") == offering_id:
            return _deepcopy(offering)
    return None


def find_live_courses(
    bridge: KnowledgeBridgeResult,
    query: str,
) -> List[Dict[str, Any]]:
    """Simple deterministic lookup; it is not a replacement ranking engine."""
    if not bridge.ready:
        return []

    text = str(query or "").strip().lower()
    if not text:
        return []

    tokens = [t for t in text.replace("/", " ").replace("-", " ").split() if t]
    matches = []

    for course in bridge.courses:
        haystack = " ".join(
            str(course.get(key, ""))
            for key in ("course_id", "official_name", "category", "program_type")
        ).lower()
        score = sum(token in haystack for token in tokens)
        if score:
            matches.append((score, course["course_id"], _deepcopy(course)))

    matches.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in matches]


def validate_bridge(bridge: KnowledgeBridgeResult) -> List[str]:
    errors = []

    if bridge.source_of_truth != SOURCE_OF_TRUTH:
        errors.append("Source of truth must be MASTER_KB.")
    if bridge.legacy_catalog_allowed:
        errors.append("Legacy catalog must remain disabled.")
    if bridge.action_flags != ACTION_FLAGS:
        errors.append("Safety action flags are not fail-closed.")

    if bridge.status == "BRIDGE_READY":
        if not bridge.courses:
            errors.append("READY bridge has no courses.")
        if not bridge.offerings:
            errors.append("READY bridge has no offerings.")
        if len(bridge.course_ids) != len(set(bridge.course_ids)):
            errors.append("Duplicate course IDs.")
        if len(bridge.offering_ids) != len(set(bridge.offering_ids)):
            errors.append("Duplicate offering IDs.")
        if "MASTER_KB" not in bridge.provenance:
            errors.append("MASTER_KB provenance missing.")

    return errors


def bridge_to_dict(bridge: KnowledgeBridgeResult) -> Dict[str, Any]:
    return _deepcopy(asdict(bridge))


def validate_serialized_bridge(data: Dict[str, Any]) -> List[str]:
    if not isinstance(data, dict):
        return ["Serialized bridge must be a dictionary."]
    required = {
        "status", "source", "bridge_version", "courses", "offerings",
        "course_ids", "offering_ids", "provenance", "errors",
        "source_of_truth", "legacy_catalog_allowed", "action_flags",
    }
    return sorted(required - set(data))


def discover_master_kb_module(
    project_root: Optional[str] = None,
    module_names: Iterable[str] = DEFAULT_MASTER_KB_MODULES,
) -> Any:
    """
    Discover a module exposing build_master_kb() or MasterKnowledgeBase.

    IMPORTANT: courses.json is never used as a fallback.
    """
    errors = []

    for module_name in module_names:
        try:
            module = import_module(module_name)
            if hasattr(module, "build_master_kb") or hasattr(
                module, "MasterKnowledgeBase"
            ):
                return module
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")

    if project_root:
        root = Path(project_root)
        if root.exists():
            for path in root.rglob("*.py"):
                if path.name.startswith(("TEST_", "test_")):
                    continue
                try:
                    source = path.read_text(
                        encoding="utf-8", errors="ignore"
                    )
                    if (
                        "def build_master_kb" not in source
                        and "class MasterKnowledgeBase" not in source
                    ):
                        continue
                    spec = importlib.util.spec_from_file_location(
                        f"_master_kb_discovered_{path.stem}", path
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        if hasattr(mod, "build_master_kb") or hasattr(
                            mod, "MasterKnowledgeBase"
                        ):
                            return mod
                except Exception as exc:
                    errors.append(f"{path}: {exc}")

    raise MasterKBBridgeError(
        "Authoritative Master KB could not be discovered. "
        "Legacy courses.json fallback is disabled. "
        + " | ".join(errors[:5])
    )


def load_authoritative_master_kb(
    *,
    project_root: Optional[str] = None,
    module_names: Iterable[str] = DEFAULT_MASTER_KB_MODULES,
) -> Any:
    module = discover_master_kb_module(
        project_root=project_root,
        module_names=module_names,
    )

    if hasattr(module, "build_master_kb"):
        kb = module.build_master_kb()
    elif hasattr(module, "MasterKnowledgeBase"):
        kb = module.MasterKnowledgeBase()
    else:
        raise MasterKBBridgeError(
            "Discovered module has no Master KB builder."
        )

    return kb


def build_authoritative_live_bridge(
    *,
    project_root: Optional[str] = None,
    module_names: Iterable[str] = DEFAULT_MASTER_KB_MODULES,
    require_offerings: bool = True,
) -> KnowledgeBridgeResult:
    try:
        kb = load_authoritative_master_kb(
            project_root=project_root,
            module_names=module_names,
        )
        return build_live_knowledge_bridge(
            kb,
            require_offerings=require_offerings,
        )
    except Exception as exc:
        return KnowledgeBridgeResult(
            status="BRIDGE_BLOCKED",
            errors=[str(exc)],
        )


def validate_no_legacy_catalog_dependency(source_text: str) -> List[str]:
    """
    Static guard for this bridge. The bridge must not read/import courses.json.
    """
    lowered = source_text.lower()
    forbidden = (
        "courses.json",
        "load_courses(",
        "data/knowledge/courses",
        "data\\knowledge\\courses",
    )
    return [
        f"Legacy catalog dependency detected: {item}"
        for item in forbidden
        if item in lowered
    ]
