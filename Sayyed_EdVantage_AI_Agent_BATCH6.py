from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "leads.json"


def _text(value: Any, default: str = "") -> str:
    return default if value is None else str(value).strip()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_leads() -> List[Dict[str, Any]]:
    """Load leads without ever modifying leads.json.

    Supports the actual Sayyed EdVantage format:
        {"SE-000001": {...}, "SE-000002": {...}}
    """
    if not DATA_FILE.exists():
        return []

    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    if not isinstance(raw, dict):
        return []

    # Wrapped formats, if ever used.
    for key in ("leads", "data", "records"):
        value = raw.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            return [
                dict(item, lead_id=str(item_id))
                for item_id, item in value.items()
                if isinstance(item, dict)
            ]

    # Actual current format: lead ID is the dictionary key.
    return [
        dict(item, lead_id=str(item_id))
        for item_id, item in raw.items()
        if isinstance(item, dict)
    ]


def _stage(lead: Dict[str, Any]) -> str:
    return _text(lead.get("stage") or lead.get("status"), "New")


def _score(lead: Dict[str, Any]) -> int:
    if lead.get("score") is not None:
        return int(max(0, min(100, _number(lead.get("score")))))

    stage = _stage(lead).lower()
    if stage == "enrolled":
        return 100
    if stage == "interested":
        return 70
    if stage in {"contacted", "follow-up", "followup"}:
        return 50
    return 25


def _risk_value(analysis: Dict[str, Any]) -> float:
    """Safely read risk from all supported representations."""
    values = [
        analysis.get("risk_conversion"),
        analysis.get("risk"),
        analysis.get("risk_score"),
    ]

    nested = analysis.get("risk_conversation")
    if isinstance(nested, dict):
        values.extend([nested.get("score"), nested.get("value")])

    for value in values:
        if value is not None:
            return max(0.0, min(100.0, _number(value)))

    return 0.0


def _blocker_map(analysis: Dict[str, Any]) -> Dict[str, Any]:
    blocker = analysis.get("conversion_blocker_map")
    if isinstance(blocker, dict):
        return blocker
    return {
        "severity": "Low",
        "blocker": "No major blocker detected",
    }


def escalation_engine(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Batch 6 escalation engine; never assumes optional keys exist."""
    blocker = _blocker_map(analysis)
    risk = _risk_value(analysis)

    workflow = analysis.get("workflow_intelligence")
    if not isinstance(workflow, dict):
        workflow = {}

    follow_up = workflow.get("follow_up_timing")
    if not isinstance(follow_up, dict):
        follow_up = {}

    urgency = _text(follow_up.get("urgency"), "Normal")
    severity = _text(blocker.get("severity"), "Low")

    triggers: List[str] = []

    if severity.lower() == "high":
        triggers.append("High-severity conversion blocker")

    if urgency.lower() == "immediate":
        triggers.append("Immediate follow-up required")

    if risk >= 70:
        triggers.append("High conversion risk")

    if not triggers:
        level = "None"
        action = "Continue normal counselling workflow"
    elif severity.lower() == "high" or risk >= 70:
        level = "High"
        action = "Escalate to senior counsellor"
    else:
        level = "Medium"
        action = "Priority counsellor review"

    return {
        "level": level,
        "risk": round(risk),
        "urgency": urgency,
        "triggers": triggers,
        "recommended_action": action,
        "requires_human": level in {"Medium", "High"},
    }


def analyze_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    lead_id = _text(lead.get("lead_id") or lead.get("id"), "UNKNOWN")
    name = _text(lead.get("name") or lead.get("student_name"), "Unknown")
    stage = _stage(lead)
    score = _score(lead)

    # Conservative derived conversion-risk score.
    risk = max(0, min(100, 100 - score))

    if stage.lower() == "interested":
        risk = max(15, risk - 10)
    elif stage.lower() == "enrolled":
        risk = 0

    urgency = (
        "Immediate" if score >= 85
        else "High" if score >= 50
        else "Normal"
    )

    if score >= 85:
        blocker = {
            "severity": "High",
            "blocker": "Decision or fee discussion requires active handling",
        }
    elif score >= 50:
        blocker = {
            "severity": "Medium",
            "blocker": "Further counselling required",
        }
    else:
        blocker = {
            "severity": "Low",
            "blocker": "No major blocker detected",
        }

    analysis: Dict[str, Any] = {
        "lead_id": lead_id,
        "name": name,
        "stage": stage,
        "score": score,
        "risk_conversion": risk,
        "risk": risk,
        "conversion_blocker_map": blocker,
        "workflow_intelligence": {
            "follow_up_timing": {
                "urgency": urgency,
            }
        },
    }

    analysis["escalation"] = escalation_engine(analysis)
    analysis["human_handoff"] = {
        "required": analysis["escalation"]["requires_human"],
        "priority": analysis["escalation"]["level"],
        "reason": (
            "; ".join(analysis["escalation"]["triggers"])
            if analysis["escalation"]["triggers"]
            else "No escalation trigger"
        ),
    }

    return analysis


def analyze_all() -> List[Dict[str, Any]]:
    return [analyze_lead(lead) for lead in load_leads()]


if __name__ == "__main__":
    leads = load_leads()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 1 / BATCH 6")
    print("=" * 78)
    print(f"Data file: {DATA_FILE}")
    print(f"Leads loaded: {len(leads)}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 78)

    for result in analyze_all():
        print(
            f'{result["lead_id"]:<10} '
            f'{result["name"]:<24} '
            f'Score={result["score"]:<3} '
            f'Risk={result["risk_conversion"]:<3} '
            f'Escalation={result["escalation"]["level"]:<6} '
            f'Action={result["escalation"]["recommended_action"]}'
        )

    print("=" * 78)
