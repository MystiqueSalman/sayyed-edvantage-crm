"""
Sayyed EdVantage — Phase 4 Integration 10
Live Agent Boundary & Smoke-Test Contract

Purpose:
- Provide one controlled boundary around the existing live `ask_agent` API.
- Preserve the user's supplied session/lead identifiers.
- Never perform CRM writes, message sends, or external actions in this layer.
- Convert exceptions and malformed agent responses into a fail-closed result.
- Keep this integration suitable for the upcoming real live-agent test.

This layer does NOT replace app.ai.agent.ask_agent.
It is a safety/normalization boundary around it.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


LIVE_BOUNDARY_READY = "LIVE_BOUNDARY_READY"
LIVE_BOUNDARY_CLARIFICATION = "LIVE_BOUNDARY_CLARIFICATION"
LIVE_BOUNDARY_REVIEW = "LIVE_BOUNDARY_REVIEW"
LIVE_BOUNDARY_BLOCKED = "LIVE_BOUNDARY_BLOCKED"
LIVE_BOUNDARY_UNKNOWN = "LIVE_BOUNDARY_UNKNOWN"

MODE_RESPOND = "RESPOND"
MODE_CLARIFY = "CLARIFY"
MODE_HUMAN_REVIEW = "HUMAN_REVIEW"
MODE_NO_RESPONSE = "NO_RESPONSE"

_TRUE = True
_FALSE = False


@dataclass
class LiveBoundaryResult:
    status: str
    mode: str
    session_id: str
    lead_id: Optional[str] = None
    user_message: str = ""
    response_text: str = ""
    response_allowed: bool = False
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    human_handoff: bool = False

    # Hard safety boundary. These remain false in this integration.
    crm_write_occurred: bool = False
    message_sent: bool = False
    external_action_occurred: bool = False
    executor_invoked: bool = False
    execution_occurred: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "session_id": self.session_id,
            "lead_id": self.lead_id,
            "user_message": self.user_message,
            "response_text": self.response_text,
            "response_allowed": self.response_allowed,
            "evidence": [dict(x) for x in self.evidence],
            "provenance": list(self.provenance),
            "conflicts": list(self.conflicts),
            "errors": list(self.errors),
            "human_handoff": self.human_handoff,
            "crm_write_occurred": self.crm_write_occurred,
            "message_sent": self.message_sent,
            "external_action_occurred": self.external_action_occurred,
            "executor_invoked": self.executor_invoked,
            "execution_occurred": self.execution_occurred,
        }


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_response_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()

    if isinstance(raw, dict):
        for key in ("response_text", "response", "answer", "text", "message"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    for key in ("response_text", "response", "answer", "text", "message"):
        try:
            value = getattr(raw, key, None)
        except Exception:
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _extract_list(raw: Any, key: str) -> List[Any]:
    if isinstance(raw, dict):
        value = raw.get(key, [])
    else:
        try:
            value = getattr(raw, key, [])
        except Exception:
            value = []

    if isinstance(value, list):
        return list(value)
    return []


def validate_live_boundary_result(result: LiveBoundaryResult) -> List[str]:
    errors: List[str] = []

    valid_statuses = {
        LIVE_BOUNDARY_READY,
        LIVE_BOUNDARY_CLARIFICATION,
        LIVE_BOUNDARY_REVIEW,
        LIVE_BOUNDARY_BLOCKED,
        LIVE_BOUNDARY_UNKNOWN,
    }
    valid_modes = {
        MODE_RESPOND,
        MODE_CLARIFY,
        MODE_HUMAN_REVIEW,
        MODE_NO_RESPONSE,
    }

    if result.status not in valid_statuses:
        errors.append("invalid live boundary status")
    if result.mode not in valid_modes:
        errors.append("invalid live boundary mode")
    if not _safe_text(result.session_id):
        errors.append("session_id is required")

    if result.status == LIVE_BOUNDARY_READY:
        if result.mode != MODE_RESPOND:
            errors.append("ready status requires RESPOND mode")
        if not result.response_allowed:
            errors.append("ready status requires response_allowed=True")
        if not result.response_text.strip():
            errors.append("ready status requires response text")

    if result.status != LIVE_BOUNDARY_READY and result.response_allowed:
        errors.append("non-ready status cannot allow response")

    if result.status == LIVE_BOUNDARY_REVIEW and not result.human_handoff:
        errors.append("review status requires human handoff")

    if result.status in {
        LIVE_BOUNDARY_CLARIFICATION,
        LIVE_BOUNDARY_REVIEW,
        LIVE_BOUNDARY_BLOCKED,
        LIVE_BOUNDARY_UNKNOWN,
    } and result.response_text.strip():
        errors.append("non-ready boundary result must not expose response text")

    # Hard safety invariant.
    if result.crm_write_occurred:
        errors.append("CRM writes are prohibited at this boundary")
    if result.message_sent:
        errors.append("message sending is prohibited at this boundary")
    if result.external_action_occurred:
        errors.append("external actions are prohibited at this boundary")
    if result.executor_invoked:
        errors.append("executor invocation is prohibited at this boundary")
    if result.execution_occurred:
        errors.append("execution is prohibited at this boundary")

    return errors


def build_live_boundary_result(
    *,
    session_id: str,
    lead_id: Optional[str] = None,
    user_message: str = "",
    raw_result: Any = None,
    provenance: Optional[List[str]] = None,
) -> LiveBoundaryResult:
    sid = _safe_text(session_id)
    msg = _safe_text(user_message)
    prov = list(provenance or [])

    if not sid:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_BLOCKED,
            mode=MODE_NO_RESPONSE,
            session_id="",
            lead_id=lead_id,
            user_message=msg,
            errors=["session_id is required"],
            provenance=prov,
        )

    if raw_result is None:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_UNKNOWN,
            mode=MODE_NO_RESPONSE,
            session_id=sid,
            lead_id=lead_id,
            user_message=msg,
            errors=["agent result is missing"],
            provenance=prov,
        )

    response_text = _extract_response_text(raw_result)
    raw_errors = [str(x) for x in _extract_list(raw_result, "errors") if str(x).strip()]
    raw_conflicts = [
        str(x) for x in _extract_list(raw_result, "conflicts") if str(x).strip()
    ]
    evidence = [
        dict(x) if isinstance(x, dict) else {"value": x}
        for x in _extract_list(raw_result, "evidence")
    ]

    if raw_conflicts:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_REVIEW,
            mode=MODE_HUMAN_REVIEW,
            session_id=sid,
            lead_id=lead_id,
            user_message=msg,
            evidence=evidence,
            provenance=prov,
            conflicts=raw_conflicts,
            errors=raw_errors,
            human_handoff=True,
        )

    if raw_errors:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_REVIEW,
            mode=MODE_HUMAN_REVIEW,
            session_id=sid,
            lead_id=lead_id,
            user_message=msg,
            evidence=evidence,
            provenance=prov,
            errors=raw_errors,
            human_handoff=True,
        )

    if not response_text:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_UNKNOWN,
            mode=MODE_NO_RESPONSE,
            session_id=sid,
            lead_id=lead_id,
            user_message=msg,
            evidence=evidence,
            provenance=prov,
            errors=["agent returned no usable response text"],
        )

    return LiveBoundaryResult(
        status=LIVE_BOUNDARY_READY,
        mode=MODE_RESPOND,
        session_id=sid,
        lead_id=lead_id,
        user_message=msg,
        response_text=response_text,
        response_allowed=True,
        evidence=evidence,
        provenance=prov,
    )


def run_live_agent_boundary(
    user_message: str,
    session_id: str,
    lead_id: Optional[str] = None,
    *,
    agent_callable: Optional[Callable[..., Any]] = None,
) -> LiveBoundaryResult:
    """
    Controlled live-agent invocation.

    The callable is injectable for testing. In production it defaults to the
    existing app.ai.agent.ask_agent. This layer itself never writes CRM data
    or sends messages.
    """
    msg = _safe_text(user_message)
    sid = _safe_text(session_id)

    if not msg:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_CLARIFICATION,
            mode=MODE_CLARIFY,
            session_id=sid,
            lead_id=lead_id,
            user_message=msg,
            errors=["user message is required"],
        )

    if not sid:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_BLOCKED,
            mode=MODE_NO_RESPONSE,
            session_id="",
            lead_id=lead_id,
            user_message=msg,
            errors=["session_id is required"],
        )

    if agent_callable is None:
        try:
            from app.ai.agent import ask_agent
            agent_callable = ask_agent
        except Exception as exc:
            return LiveBoundaryResult(
                status=LIVE_BOUNDARY_BLOCKED,
                mode=MODE_NO_RESPONSE,
                session_id=sid,
                lead_id=lead_id,
                user_message=msg,
                errors=[f"agent import failed: {exc}"],
            )

    try:
        # Preserve the established ask_agent contract:
        # ask_agent(message, session_id)
        raw = agent_callable(msg, sid)
    except Exception as exc:
        return LiveBoundaryResult(
            status=LIVE_BOUNDARY_REVIEW,
            mode=MODE_HUMAN_REVIEW,
            session_id=sid,
            lead_id=lead_id,
            user_message=msg,
            errors=[f"agent invocation failed: {exc}"],
            human_handoff=True,
        )

    return build_live_boundary_result(
        session_id=sid,
        lead_id=lead_id,
        user_message=msg,
        raw_result=raw,
        provenance=["LIVE_AGENT", "PHASE4_INTEGRATION10"],
    )


def live_boundary_query(
    user_message: str,
    session_id: str,
    lead_id: Optional[str] = None,
) -> LiveBoundaryResult:
    return run_live_agent_boundary(user_message, session_id, lead_id)


def validate_serialized_live_boundary(data: Dict[str, Any]) -> List[str]:
    if not isinstance(data, dict):
        return ["serialized result must be a dict"]

    required = {"status", "mode", "session_id", "response_allowed"}
    missing = sorted(required - set(data))
    if missing:
        return [f"missing serialized fields: {', '.join(missing)}"]

    result = LiveBoundaryResult(
        status=str(data.get("status", "")),
        mode=str(data.get("mode", "")),
        session_id=str(data.get("session_id", "")),
        lead_id=data.get("lead_id"),
        user_message=str(data.get("user_message", "")),
        response_text=str(data.get("response_text", "")),
        response_allowed=bool(data.get("response_allowed", False)),
        evidence=list(data.get("evidence", [])),
        provenance=list(data.get("provenance", [])),
        conflicts=list(data.get("conflicts", [])),
        errors=list(data.get("errors", [])),
        human_handoff=bool(data.get("human_handoff", False)),
        crm_write_occurred=bool(data.get("crm_write_occurred", False)),
        message_sent=bool(data.get("message_sent", False)),
        external_action_occurred=bool(data.get("external_action_occurred", False)),
        executor_invoked=bool(data.get("executor_invoked", False)),
        execution_occurred=bool(data.get("execution_occurred", False)),
    )
    return validate_live_boundary_result(result)
