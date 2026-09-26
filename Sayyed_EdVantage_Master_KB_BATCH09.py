from copy import deepcopy
from typing import Any, Dict, List, Optional

MASTER_SOURCE_STATUS = {"draft", "approved", "deprecated", "superseded"}
DATA_SCIENCE_COURSE_ID = "SE-DSP-001"


def register_knowledge_source(
    kb,
    source_id: str,
    title: str,
    source_type: str,
    course_id: Optional[str] = None,
    version: str = "1.0",
    status: str = "approved",
    notes: str = "",
):
    from Sayyed_EdVantage_Master_KB_BATCH01 import SourceRecord

    if status not in MASTER_SOURCE_STATUS:
        raise ValueError(f"Invalid source status: {status}")
    kb.register_source(SourceRecord(
        source_id=source_id,
        title=title,
        source_type=source_type,
        version=version,
        status=status,
        course_id=course_id,
        notes=notes,
    ))
    return kb.get_common_knowledge("source_registry") or {}


def get_source(kb, source_id: str):
    source = kb.sources.get(source_id)
    return deepcopy(source) if source else None


def list_sources(kb, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sources = []
    for source in kb.sources.values():
        if course_id is None or source.course_id == course_id:
            sources.append({
                "source_id": source.source_id,
                "title": source.title,
                "source_type": source.source_type,
                "version": source.version,
                "status": source.status,
                "course_id": source.course_id,
            })
    return deepcopy(sources)


def set_source_status(kb, source_id: str, status: str, replacement_source_id: Optional[str] = None):
    if status not in MASTER_SOURCE_STATUS:
        raise ValueError(f"Invalid source status: {status}")
    source = kb.sources.get(source_id)
    if source is None:
        raise KeyError(source_id)

    updated = deepcopy(source)
    updated.status = status
    if replacement_source_id:
        updated.notes = (
            updated.notes.rstrip() +
            f" Replacement source: {replacement_source_id}."
        ).strip()
    kb.register_source(updated)
    return get_source(kb, source_id)


def validate_source_registry(kb) -> Dict[str, Any]:
    errors = []
    for source_id, source in kb.sources.items():
        if source_id != source.source_id:
            errors.append(f"Source key mismatch: {source_id}")
        if source.status not in MASTER_SOURCE_STATUS:
            errors.append(f"Invalid source status: {source_id}")
        if not source.title:
            errors.append(f"Missing source title: {source_id}")
        if not source.version:
            errors.append(f"Missing source version: {source_id}")

    # Current course knowledge must reference an existing source.
    for course in kb.courses.values():
        for source_id in course.source_ids:
            if source_id not in kb.sources:
                errors.append(
                    f"Course {course.course_id} references missing source {source_id}."
                )
            elif kb.sources[source_id].status not in {"approved", "draft"}:
                errors.append(
                    f"Course {course.course_id} references non-current source {source_id}."
                )

    return {
        "valid": not errors,
        "errors": errors,
        "source_count": len(kb.sources),
    }


def attach_source_registry_metadata(kb):
    registry = {
        "versioning_enabled": True,
        "approved_current_sources_only": True,
        "source_statuses": sorted(MASTER_SOURCE_STATUS),
        "course_isolation": True,
        "provenance_required": True,
        "no_silent_source_replacement": True,
    }
    kb.set_common_knowledge("source_registry", registry)
    return kb


def add_batch09_to_master_kb(kb):
    kb = attach_source_registry_metadata(kb)
    report = validate_source_registry(kb)
    if not report["valid"]:
        raise ValueError(report["errors"])

    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None:
        raise KeyError("Data Science course is missing from Master KB.")

    knowledge = deepcopy(course.knowledge)
    knowledge["source_version_control"] = {
        "enabled": True,
        "course_source_ids": deepcopy(course.source_ids),
        "provenance_required": True,
        "approved_current_sources_only": True,
        "no_silent_source_replacement": True,
    }
    course.knowledge = knowledge
    kb.register_course(course)
    return kb


def build_master_kb_with_batch09():
    from Sayyed_EdVantage_Master_KB_BATCH08 import build_master_kb_with_batch08
    return add_batch09_to_master_kb(build_master_kb_with_batch08())
