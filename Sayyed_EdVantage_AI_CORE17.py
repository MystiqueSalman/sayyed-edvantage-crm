
"""
Sayyed EdVantage AI Agent — AI Core 17
CRM-Aware Conversation & Lead State Synchronization Intelligence

Read-only synchronization intelligence:
- compares CRM lead state with conversation/session state
- identifies aligned facts, missing facts, and discrepancies
- preserves CRM as an external source of lead state without writing to it
- never silently overwrites or invents facts
- routes material conflicts to clarification/human review
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

SYNC_READY = "SYNC_READY"
SYNC_CLARIFICATION = "SYNC_CLARIFICATION"
SYNC_REVIEW = "SYNC_REVIEW"
SYNC_INSUFFICIENT = "SYNC_INSUFFICIENT"
SYNC_UNKNOWN = "SYNC_UNKNOWN"

MATCH = "MATCH"
CRM_ONLY = "CRM_ONLY"
CONTEXT_ONLY = "CONTEXT_ONLY"
CONFLICT = "CONFLICT"
UNKNOWN = "UNKNOWN"

MATERIAL_FIELDS = (
    "lead_id",
    "course_id",
    "stage",
    "region",
    "intent",
)

OPTIONAL_FIELDS = (
    "counselling",
    "follow_up",
    "pending_items",
)

@dataclass
class SyncEvidence:
    field: str
    status: str
    crm_value: Any = None
    context_value: Any = None
    reason: str = ""

@dataclass
class LeadStateSync:
    lead_id: Optional[str]
    status: str
    evidences: List[SyncEvidence] = field(default_factory=list)
    aligned_fields: List[str] = field(default_factory=list)
    crm_only_fields: List[str] = field(default_factory=list)
    context_only_fields: List[str] = field(default_factory=list)
    conflicting_fields: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    crm_write_required: bool = False
    crm_write_allowed: bool = False
    source_provenance: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class SyncRuntimeResult:
    sync: LeadStateSync
    recommended_next_step: str = "CONTINUE_CONVERSATION"
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "crm_writes_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "execution_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })

def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return " ".join(v.strip().lower().split())
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(val) for k, val in v.items()}
    return v

def _get_context_field(context: Dict[str, Any], field: str) -> Any:
    if field == "lead_id":
        return context.get("lead_id")
    if field == "course_id":
        vals = context.get("active_course_ids")
        return vals[0] if isinstance(vals, list) and len(vals) == 1 else (
            vals if isinstance(vals, list) else context.get("course_id")
        )
    if field == "intent":
        return context.get("active_intent") or context.get("intent")
    return context.get(field)

def _get_crm_field(crm: Dict[str, Any], field: str) -> Any:
    if field == "course_id":
        return crm.get("course_id") or (
            crm.get("course_ids")[0]
            if isinstance(crm.get("course_ids"), list) and len(crm.get("course_ids")) == 1
            else crm.get("course_ids")
        )
    if field == "intent":
        return crm.get("intent")
    return crm.get(field)

def compare_lead_state(
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> LeadStateSync:
    crm = deepcopy(crm_snapshot or {})
    ctx = deepcopy(conversation_context or {})
    lead_id = crm.get("lead_id") or ctx.get("lead_id")
    evidence: List[SyncEvidence] = []
    aligned, crm_only, context_only, conflicts = [], [], [], []
    errors = []

    if not crm and not ctx:
        return LeadStateSync(
            lead_id=None, status=SYNC_UNKNOWN,
            errors=["No CRM snapshot or conversation context supplied."],
            source_provenance=[],
        )
    if not crm:
        return LeadStateSync(
            lead_id=lead_id, status=SYNC_INSUFFICIENT,
            context_only_fields=["conversation_context"],
            errors=["CRM snapshot is unavailable."],
            source_provenance=["CONVERSATION_CONTEXT"],
        )

    fields = MATERIAL_FIELDS
    for f in fields:
        cv = _get_crm_field(crm, f)
        xv = _get_context_field(ctx, f)
        if cv is None and xv is None:
            evidence.append(SyncEvidence(f, UNKNOWN, reason="Neither source provides this field."))
        elif cv is None:
            context_only.append(f)
            evidence.append(SyncEvidence(f, CONTEXT_ONLY, context_value=deepcopy(xv),
                                          reason="Conversation context has a fact not present in CRM snapshot."))
        elif xv is None:
            crm_only.append(f)
            evidence.append(SyncEvidence(f, CRM_ONLY, crm_value=deepcopy(cv),
                                          reason="CRM has a fact not present in conversation context."))
        elif _norm(cv) == _norm(xv):
            aligned.append(f)
            evidence.append(SyncEvidence(f, MATCH, deepcopy(cv), deepcopy(xv),
                                          "CRM and conversation context agree."))
        else:
            conflicts.append(f)
            evidence.append(SyncEvidence(f, CONFLICT, deepcopy(cv), deepcopy(xv),
                                          "Sources disagree; do not silently choose a value."))

    # Secondary CRM-state visibility is compared as presence only, because
    # complex histories are not safely reconstructed from arbitrary context.
    for f in OPTIONAL_FIELDS:
        cv = _get_crm_field(crm, f)
        xv = _get_context_field(ctx, f)
        if cv is not None and xv is not None and _norm(cv) != _norm(xv):
            conflicts.append(f)
            evidence.append(SyncEvidence(f, CONFLICT, deepcopy(cv), deepcopy(xv),
                                          "CRM and conversation state differ; human/clarification review is safer."))

    if conflicts:
        status = SYNC_REVIEW
        questions = [f"Please clarify the current {f.replace('_', ' ')}." for f in conflicts]
        handoff = True
    elif context_only or crm_only:
        status = SYNC_CLARIFICATION
        questions = []
        handoff = False
    else:
        status = SYNC_READY
        questions = []
        handoff = False

    provenance = []
    if crm:
        provenance.append("CRM_READ")
    if ctx:
        provenance.append("CONVERSATION_CONTEXT")

    return LeadStateSync(
        lead_id=lead_id,
        status=status,
        evidences=evidence,
        aligned_fields=aligned,
        crm_only_fields=crm_only,
        context_only_fields=context_only,
        conflicting_fields=conflicts,
        clarification_questions=questions,
        human_handoff_required=handoff,
        crm_write_required=bool(context_only or conflicts),
        crm_write_allowed=False,
        source_provenance=provenance,
        errors=errors,
    )

def run_state_synchronization(
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> SyncRuntimeResult:
    sync = compare_lead_state(crm_snapshot, conversation_context)
    if sync.status == SYNC_REVIEW:
        next_step = "HUMAN_REVIEW"
    elif sync.status == SYNC_CLARIFICATION:
        next_step = "CLARIFY_LEAD_STATE"
    elif sync.status == SYNC_INSUFFICIENT:
        next_step = "OBTAIN_CRM_STATE"
    elif sync.status == SYNC_UNKNOWN:
        next_step = "OBTAIN_LEAD_STATE"
    else:
        next_step = "CONTINUE_CONVERSATION"
    return SyncRuntimeResult(sync=sync, recommended_next_step=next_step)

def validate_sync(sync: LeadStateSync) -> List[str]:
    errors = []
    if sync.crm_write_allowed is not False:
        errors.append("CRM writes must remain disabled.")
    if sync.human_handoff_required and not sync.conflicting_fields:
        errors.append("Human handoff requires a material conflict.")
    for f in sync.conflicting_fields:
        if f not in {e.field for e in sync.evidences}:
            errors.append(f"Conflict field {f} lacks evidence.")
    return errors

def validate_sync_runtime(result: SyncRuntimeResult) -> List[str]:
    errors = validate_sync(result.sync)
    for k in ("crm_writes_enabled","messaging_enabled","external_actions_enabled","execution_enabled"):
        if result.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def sync_to_dict(sync: LeadStateSync) -> Dict[str, Any]:
    return {
        "lead_id": sync.lead_id,
        "status": sync.status,
        "evidences": [
            {"field": e.field, "status": e.status, "crm_value": deepcopy(e.crm_value),
             "context_value": deepcopy(e.context_value), "reason": e.reason}
            for e in sync.evidences
        ],
        "aligned_fields": list(sync.aligned_fields),
        "crm_only_fields": list(sync.crm_only_fields),
        "context_only_fields": list(sync.context_only_fields),
        "conflicting_fields": list(sync.conflicting_fields),
        "clarification_questions": list(sync.clarification_questions),
        "human_handoff_required": sync.human_handoff_required,
        "crm_write_required": sync.crm_write_required,
        "crm_write_allowed": sync.crm_write_allowed,
        "source_provenance": list(sync.source_provenance),
        "errors": list(sync.errors),
    }

def runtime_to_dict(result: SyncRuntimeResult) -> Dict[str, Any]:
    return {
        "sync": sync_to_dict(result.sync),
        "recommended_next_step": result.recommended_next_step,
        "safety": dict(result.safety),
    }

def build_crm_state_sync_layer() -> Dict[str, Any]:
    return {
        "layer": "AI_CORE_17",
        "name": "CRM-Aware Conversation & Lead State Synchronization Intelligence",
        "read_only": True,
        "crm_writes_enabled": False,
        "conflict_policy": "do_not_silently_choose",
        "fail_closed": True,
    }
