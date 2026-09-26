
"""
Sayyed EdVantage AI Agent — AI Core 15
CRM Read Integration Contract

Read-only adapter for the existing Sayyed EdVantage CRM.
The adapter reads leads.json and exposes a defensive, normalized snapshot.

Safety:
- CRM writes: disabled
- Messaging: disabled
- External actions: disabled
- Autonomous execution: disabled
- Missing/invalid CRM data fails closed.
- Lead isolation is mandatory.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


CRM_READ_READY = "CRM_READ_READY"
CRM_READ_NOT_FOUND = "CRM_READ_NOT_FOUND"
CRM_READ_INVALID = "CRM_READ_INVALID"
CRM_READ_ERROR = "CRM_READ_ERROR"
CRM_READ_CLARIFICATION = "CRM_READ_CLARIFICATION"

PIPELINE_STAGES = {
    "New", "Contacted", "Counselling", "Interested",
    "Application", "Payment Pending", "Enrolled", "Lost",
}


@dataclass
class CRMLeadSnapshot:
    lead_id: str
    name: str = ""
    phone: str = ""
    email: str = ""
    course_id: Optional[str] = None
    pipeline_stage: Optional[str] = None
    source: Optional[str] = None
    region: Optional[str] = None
    counselling_history: List[Dict[str, Any]] = field(default_factory=list)
    follow_up_history: List[Dict[str, Any]] = field(default_factory=list)
    fees: Dict[str, Any] = field(default_factory=dict)
    payments: Dict[str, Any] = field(default_factory=dict)
    activity_timeline: List[Dict[str, Any]] = field(default_factory=list)
    pending_items: List[str] = field(default_factory=list)
    raw_fields_present: List[str] = field(default_factory=list)


@dataclass
class CRMReadResult:
    status: str
    lead_id: Optional[str] = None
    snapshot: Optional[CRMLeadSnapshot] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_path: Optional[str] = None
    read_only: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


def _as_list(value):
    return value if isinstance(value, list) else []


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _normalize_lead(raw: Dict[str, Any], lead_id: str) -> CRMLeadSnapshot:
    # Support common field spellings without changing the underlying CRM.
    course_id = raw.get("course_id") or raw.get("course")
    stage = raw.get("pipeline_stage") or raw.get("stage") or raw.get("status")

    return CRMLeadSnapshot(
        lead_id=lead_id,
        name=str(raw.get("name") or raw.get("full_name") or ""),
        phone=str(raw.get("phone") or raw.get("mobile") or ""),
        email=str(raw.get("email") or ""),
        course_id=course_id,
        pipeline_stage=stage,
        source=raw.get("source"),
        region=raw.get("region") or raw.get("country"),
        counselling_history=_as_list(
            raw.get("counselling_history") or raw.get("counselling")
        ),
        follow_up_history=_as_list(
            raw.get("follow_up_history") or raw.get("follow_ups")
        ),
        fees=_as_dict(raw.get("fees") or raw.get("fee")),
        payments=_as_dict(raw.get("payments") or raw.get("payment")),
        activity_timeline=_as_list(
            raw.get("activity_timeline") or raw.get("activities")
        ),
        pending_items=_as_list(raw.get("pending_items") or raw.get("pending")),
        raw_fields_present=list(raw.keys()),
    )


def _load_json(source_path: Path) -> Any:
    with source_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _lead_collection(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("leads", "data", "records"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        # A dict keyed by lead ID is also supported.
        if all(isinstance(v, dict) for v in data.values()):
            result = []
            for key, value in data.items():
                item = dict(value)
                item.setdefault("lead_id", key)
                result.append(item)
            return result
    return []


def read_crm_lead(
    lead_id: str,
    source_path: str = "data/leads.json",
) -> CRMReadResult:
    if not lead_id or not str(lead_id).strip():
        return CRMReadResult(
            status=CRM_READ_CLARIFICATION,
            errors=["lead_id is required."],
            source_path=source_path,
        )

    path = Path(source_path)
    if not path.exists():
        return CRMReadResult(
            status=CRM_READ_ERROR,
            lead_id=lead_id,
            errors=[f"CRM source file not found: {source_path}"],
            source_path=source_path,
        )

    try:
        data = _load_json(path)
    except json.JSONDecodeError as exc:
        return CRMReadResult(
            status=CRM_READ_INVALID,
            lead_id=lead_id,
            errors=[f"CRM JSON is invalid: {exc.msg}"],
            source_path=source_path,
        )
    except OSError as exc:
        return CRMReadResult(
            status=CRM_READ_ERROR,
            lead_id=lead_id,
            errors=[f"CRM source could not be read: {exc}"],
            source_path=source_path,
        )

    leads = _lead_collection(data)
    matches = []
    for raw in leads:
        candidate = raw.get("lead_id") or raw.get("id") or raw.get("leadId")
        if str(candidate) == str(lead_id):
            matches.append(raw)

    if not matches:
        return CRMReadResult(
            status=CRM_READ_NOT_FOUND,
            lead_id=lead_id,
            errors=["Requested lead was not found in the CRM source."],
            source_path=source_path,
        )

    if len(matches) > 1:
        return CRMReadResult(
            status=CRM_READ_INVALID,
            lead_id=lead_id,
            errors=["Lead ID is not unique in the CRM source."],
            source_path=source_path,
        )

    raw = matches[0]
    snapshot = _normalize_lead(raw, str(lead_id))
    warnings = []

    if snapshot.pipeline_stage and snapshot.pipeline_stage not in PIPELINE_STAGES:
        warnings.append("CRM pipeline stage is not in the known pipeline-stage set.")
    if not snapshot.name:
        warnings.append("Lead name is missing from the CRM snapshot.")
    if not snapshot.course_id:
        warnings.append("Course is not established in the CRM snapshot.")

    return CRMReadResult(
        status=CRM_READ_READY,
        lead_id=str(lead_id),
        snapshot=snapshot,
        warnings=warnings,
        source_path=str(path),
    )


def read_crm_leads(
    source_path: str = "data/leads.json",
) -> Dict[str, CRMReadResult]:
    path = Path(source_path)
    if not path.exists():
        return {
            "_error": CRMReadResult(
                status=CRM_READ_ERROR,
                errors=[f"CRM source file not found: {source_path}"],
                source_path=source_path,
            )
        }
    try:
        data = _load_json(path)
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "_error": CRMReadResult(
                status=CRM_READ_INVALID,
                errors=[f"CRM source could not be parsed: {exc}"],
                source_path=source_path,
            )
        }

    results = {}
    for raw in _lead_collection(data):
        lid = raw.get("lead_id") or raw.get("id") or raw.get("leadId")
        if lid is None:
            continue
        lid = str(lid)
        if lid in results:
            results[lid] = CRMReadResult(
                status=CRM_READ_INVALID,
                lead_id=lid,
                errors=["Duplicate lead ID detected."],
                source_path=source_path,
            )
        else:
            results[lid] = CRMReadResult(
                status=CRM_READ_READY,
                lead_id=lid,
                snapshot=_normalize_lead(raw, lid),
                source_path=source_path,
            )
    return results


def compare_crm_snapshot_with_context(
    snapshot: CRMLeadSnapshot,
    context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Returns discrepancy diagnostics only. It does not overwrite either source.
    """
    context = context or {}
    discrepancies = []

    context_course = context.get("course_id")
    if context_course and snapshot.course_id and context_course != snapshot.course_id:
        discrepancies.append(
            f"Course discrepancy: conversation/context={context_course}, CRM={snapshot.course_id}."
        )

    context_stage = context.get("pipeline_stage")
    if context_stage and snapshot.pipeline_stage and context_stage != snapshot.pipeline_stage:
        discrepancies.append(
            f"Pipeline-stage discrepancy: conversation/context={context_stage}, CRM={snapshot.pipeline_stage}."
        )

    return discrepancies


def validate_crm_read_result(result: CRMReadResult) -> Dict[str, Any]:
    errors = []

    valid_statuses = {
        CRM_READ_READY, CRM_READ_NOT_FOUND, CRM_READ_INVALID,
        CRM_READ_ERROR, CRM_READ_CLARIFICATION,
    }
    if result.status not in valid_statuses:
        errors.append("Invalid CRM read status.")
    if result.read_only is not True:
        errors.append("read_only must remain True.")
    if result.execution_enabled is not False:
        errors.append("execution_enabled must remain False.")
    if result.messaging_enabled is not False:
        errors.append("messaging_enabled must remain False.")
    if result.external_actions_enabled is not False:
        errors.append("external_actions_enabled must remain False.")
    if result.crm_writes_enabled is not False:
        errors.append("crm_writes_enabled must remain False.")

    if result.status == CRM_READ_READY and result.snapshot is None:
        errors.append("READY result requires a snapshot.")
    if result.status != CRM_READ_READY and result.snapshot is not None:
        errors.append("Non-ready result must not expose a snapshot.")
    if result.status == CRM_READ_CLARIFICATION and not result.errors:
        errors.append("Clarification result requires an error/question reason.")

    return {"valid": not errors, "errors": errors}


def crm_snapshot_to_dict(snapshot: CRMLeadSnapshot) -> Dict[str, Any]:
    return {
        "lead_id": snapshot.lead_id,
        "name": snapshot.name,
        "phone": snapshot.phone,
        "email": snapshot.email,
        "course_id": snapshot.course_id,
        "pipeline_stage": snapshot.pipeline_stage,
        "source": snapshot.source,
        "region": snapshot.region,
        "counselling_history": list(snapshot.counselling_history),
        "follow_up_history": list(snapshot.follow_up_history),
        "fees": dict(snapshot.fees),
        "payments": dict(snapshot.payments),
        "activity_timeline": list(snapshot.activity_timeline),
        "pending_items": list(snapshot.pending_items),
        "raw_fields_present": list(snapshot.raw_fields_present),
    }


def crm_read_result_to_dict(result: CRMReadResult) -> Dict[str, Any]:
    return {
        "status": result.status,
        "lead_id": result.lead_id,
        "snapshot": crm_snapshot_to_dict(result.snapshot) if result.snapshot else None,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "source_path": result.source_path,
        "read_only": result.read_only,
        "execution_enabled": result.execution_enabled,
        "messaging_enabled": result.messaging_enabled,
        "external_actions_enabled": result.external_actions_enabled,
        "crm_writes_enabled": result.crm_writes_enabled,
    }
