from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from app.agentic.models import AgentContext, Task
from app.leads.lead_manager import get_all_leads


FUNNEL = ("New", "Contacted", "Counselling", "Interested", "Application", "Payment Pending", "Enrolled", "Lost")


def _metric(name: str, value: Any, evidence: str = "CALCULATED_METRIC") -> dict[str, Any]:
    return {"name": name, "value": value, "evidence_type": evidence}


def analytics_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    leads = get_all_leads()
    statuses = Counter(str(lead.get("status", "New")) for lead in leads if isinstance(lead, dict))
    courses = Counter(str(lead.get("course_interest", "Unknown")) for lead in leads if isinstance(lead, dict) and lead.get("course_interest"))
    sources = Counter(str(lead.get("source", "Unknown")) for lead in leads if isinstance(lead, dict))
    total = len(leads)
    enrolled = statuses.get("Enrolled", 0)
    metrics = [_metric("total_leads", total, "OBSERVED_DATA")]
    metrics.extend(_metric(f"leads_{status.lower().replace(' ', '_')}", statuses.get(status, 0), "OBSERVED_DATA") for status in FUNNEL)
    if total:
        metrics.append(_metric("enrollment_conversion_rate", round(enrolled / total * 100, 2)))
    else:
        metrics.append(_metric("enrollment_conversion_rate", None, "UNKNOWN"))
    previous = task.input.get("previous_metrics", {})
    trends = []
    for key in ("total_leads", "enrollment_conversion_rate"):
        if key in previous and isinstance(previous[key], (int, float)) and isinstance(next((m["value"] for m in metrics if m["name"] == key), None), (int, float)):
            current = next(m["value"] for m in metrics if m["name"] == key)
            direction = "increase" if current > previous[key] else "decrease" if current < previous[key] else "stable"
            trends.append({"metric": key, "description": f"Observed {direction}", "evidence_type": "CALCULATED_METRIC"})
    anomalies = []
    if total and not courses:
        anomalies.append({"description": "No course-interest values are available", "evidence_type": "OBSERVED_DATA"})
    observations = [{"description": f"{total} lead records were observed in the existing CRM store", "evidence_type": "OBSERVED_DATA"}]
    if statuses.get("Lost", 0) > statuses.get("Enrolled", 0):
        observations.append({"description": "Lost leads exceed enrolled leads in the observed snapshot", "evidence_type": "OBSERVED_DATA"})
    return {
        "agent": "ANALYTICS", "agent_id": "ANALYTICS", "status": "completed", "analysis_type": task.input.get("analysis_type", "lead_funnel"),
        "period": task.input.get("period", "current CRM snapshot"), "data_sources": ["existing CRM read"],
        "observations": observations, "metrics": metrics, "trends": trends, "anomalies": anomalies,
        "course_interest_distribution": [{"course": course, "count": count, "evidence_type": "OBSERVED_DATA"} for course, count in courses.items()],
        "source_attribution": [{"source": source, "count": count, "evidence_type": "OBSERVED_DATA"} for source, count in sources.items()],
        "inferences": [{"description": "The funnel may benefit from stage-specific follow-up review", "evidence_type": "INFERENCE"}] if statuses.get("Lost", 0) > statuses.get("Enrolled", 0) else [],
        "unknowns": ["Platform campaign metrics are unavailable without a connected provider", "Causation for changes is not established from this snapshot"],
        "recommendations": ["Review follow-up coverage by stage", "Collect period-over-period snapshots before making trend claims"],
        "authorization_required": False, "execution_performed": False, "crm_mutation_performed": False,
    }