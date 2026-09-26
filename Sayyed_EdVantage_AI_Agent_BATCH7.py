"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 7

Memory + adaptive decision layer.

Capabilities:
1. Persistent conversation memory
2. Lead history accumulation
3. Previous-objection memory
4. Counselling outcome memory
5. Lead-state transition intelligence
6. Adaptive next-best-action engine

Production safety:
- data/leads.json is READ-ONLY.
- Memory is stored separately in data/agent_memory.json.
- The memory file is created/updated only through explicit record methods.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "leads.json"
MEMORY_FILE = BASE_DIR / "data" / "agent_memory.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, default: str = "") -> str:
    return default if value is None else str(value).strip()


class MemoryStore:
    """Small JSON-backed persistent memory store, independent of leads.json."""

    def __init__(self, path: Path = MEMORY_FILE):
        self.path = Path(path)
        self.data: Dict[str, Any] = {
            "version": 1,
            "leads": {},
        }
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data.update(raw)
                if not isinstance(self.data.get("leads"), dict):
                    self.data["leads"] = {}
        except (OSError, json.JSONDecodeError):
            # Corrupt/missing memory must never break the agent.
            self.data = {"version": 1, "leads": {}}

    def _lead(self, lead_id: str) -> Dict[str, Any]:
        lead_id = _text(lead_id, "UNKNOWN")
        leads = self.data.setdefault("leads", {})
        record = leads.setdefault(
            lead_id,
            {
                "conversation_memory": [],
                "history": [],
                "objections": [],
                "outcomes": [],
                "state_transitions": [],
            },
        )

        for key in (
            "conversation_memory",
            "history",
            "objections",
            "outcomes",
            "state_transitions",
        ):
            if not isinstance(record.get(key), list):
                record[key] = []

        return record

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def remember_conversation(
        self,
        lead_id: str,
        message: str,
        channel: str = "unknown",
    ) -> Dict[str, Any]:
        item = {
            "timestamp": now_iso(),
            "channel": _text(channel, "unknown"),
            "message": _text(message),
        }
        self._lead(lead_id)["conversation_memory"].append(item)
        self.save()
        return item

    def record_history(
        self,
        lead_id: str,
        event: str,
        stage: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        item = {
            "timestamp": now_iso(),
            "event": _text(event),
            "stage": _text(stage),
            "note": _text(note),
        }
        self._lead(lead_id)["history"].append(item)
        self.save()
        return item

    def remember_objection(
        self,
        lead_id: str,
        objection: str,
        severity: str = "Medium",
    ) -> Dict[str, Any]:
        item = {
            "timestamp": now_iso(),
            "objection": _text(objection),
            "severity": _text(severity, "Medium"),
        }
        self._lead(lead_id)["objections"].append(item)
        self.save()
        return item

    def record_outcome(
        self,
        lead_id: str,
        outcome: str,
        result: str = "",
    ) -> Dict[str, Any]:
        item = {
            "timestamp": now_iso(),
            "outcome": _text(outcome),
            "result": _text(result),
        }
        self._lead(lead_id)["outcomes"].append(item)
        self.save()
        return item

    def record_transition(
        self,
        lead_id: str,
        old_stage: str,
        new_stage: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        item = {
            "timestamp": now_iso(),
            "from": _text(old_stage, "Unknown"),
            "to": _text(new_stage, "Unknown"),
            "reason": _text(reason),
        }
        self._lead(lead_id)["state_transitions"].append(item)
        self.save()
        return item

    def get(self, lead_id: str) -> Dict[str, Any]:
        return self._lead(lead_id)

    def summary(self, lead_id: str) -> Dict[str, Any]:
        record = self.get(lead_id)
        return {
            "conversations": len(record["conversation_memory"]),
            "history_events": len(record["history"]),
            "objections": len(record["objections"]),
            "outcomes": len(record["outcomes"]),
            "state_transitions": len(record["state_transitions"]),
            "latest_objection": (
                record["objections"][-1]["objection"]
                if record["objections"]
                else None
            ),
            "latest_outcome": (
                record["outcomes"][-1]["outcome"]
                if record["outcomes"]
                else None
            ),
        }


def load_leads() -> List[Dict[str, Any]]:
    """Load current leads without modifying leads.json."""
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

    return [
        dict(item, lead_id=str(item_id))
        for item_id, item in raw.items()
        if isinstance(item, dict)
    ]


def lead_id(lead: Dict[str, Any]) -> str:
    return _text(
        lead.get("lead_id") or lead.get("id"),
        "UNKNOWN",
    )


def lead_name(lead: Dict[str, Any]) -> str:
    return _text(
        lead.get("name") or lead.get("student_name"),
        "Unknown",
    )


def stage_of(lead: Dict[str, Any]) -> str:
    return _text(
        lead.get("stage") or lead.get("status"),
        "New",
    )


def state_transition_intelligence(
    lead: Dict[str, Any],
    memory: MemoryStore,
) -> Dict[str, Any]:
    """Infer current state and recent movement from stored history."""
    lid = lead_id(lead)
    current = stage_of(lead)
    record = memory.get(lid)
    transitions = record["state_transitions"]

    previous = transitions[-1]["to"] if transitions else None
    changed = previous is not None and previous != current

    return {
        "lead_id": lid,
        "current_stage": current,
        "previous_recorded_stage": previous,
        "stage_changed": changed,
        "transition_count": len(transitions),
        "latest_transition": transitions[-1] if transitions else None,
    }


def adaptive_next_best_action(
    lead: Dict[str, Any],
    memory: MemoryStore,
) -> Dict[str, Any]:
    """
    Select a practical next action using current stage plus remembered
    objections, outcomes, and conversation activity.
    """
    lid = lead_id(lead)
    stage = stage_of(lead).lower()
    record = memory.get(lid)

    objections = record["objections"]
    outcomes = record["outcomes"]
    conversations = record["conversation_memory"]

    if stage == "enrolled":
        action = "Confirm onboarding and maintain student-success follow-up"
        priority = "Low"
    elif objections:
        latest = _text(objections[-1].get("objection")).lower()

        if any(word in latest for word in ("fee", "fees", "budget", "price", "cost")):
            action = "Address fee concern with a personalized value and payment-plan discussion"
        elif any(word in latest for word in ("time", "schedule", "timing")):
            action = "Resolve schedule concern and offer suitable study options"
        elif any(word in latest for word in ("parent", "family", "guardian")):
            action = "Engage the decision-maker and prepare a family-focused counselling follow-up"
        else:
            action = "Resolve the latest remembered objection before advancing the admission"
        priority = "High"
    elif stage == "interested":
        action = "Conduct a conversion-focused counselling follow-up"
        priority = "High"
    elif conversations:
        action = "Continue personalized follow-up using the latest conversation context"
        priority = "Medium"
    elif outcomes:
        action = "Review the latest counselling outcome and schedule the next contact"
        priority = "Medium"
    else:
        action = "Establish contact and qualify the admission requirement"
        priority = "Medium"

    return {
        "lead_id": lid,
        "action": action,
        "priority": priority,
        "memory_signals": {
            "conversations": len(conversations),
            "objections": len(objections),
            "outcomes": len(outcomes),
        },
    }


def analyze_lead(
    lead: Dict[str, Any],
    memory: Optional[MemoryStore] = None,
) -> Dict[str, Any]:
    memory = memory or MemoryStore()
    lid = lead_id(lead)

    return {
        "lead_id": lid,
        "name": lead_name(lead),
        "stage": stage_of(lead),
        "memory": memory.summary(lid),
        "state_transition": state_transition_intelligence(lead, memory),
        "next_best_action": adaptive_next_best_action(lead, memory),
    }


def analyze_all(
    memory: Optional[MemoryStore] = None,
) -> List[Dict[str, Any]]:
    memory = memory or MemoryStore()
    return [analyze_lead(lead, memory) for lead in load_leads()]


if __name__ == "__main__":
    leads = load_leads()
    memory = MemoryStore()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 2 / BATCH 7")
    print("=" * 78)
    print(f"Data file: {DATA_FILE}")
    print(f"Leads loaded: {len(leads)}")
    print(f"Memory file: {MEMORY_FILE}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 78)

    for result in analyze_all(memory):
        m = result["memory"]
        print(
            f'{result["lead_id"]:<10} '
            f'{result["name"]:<24} '
            f'Stage={result["stage"]:<12} '
            f'Memory={m["conversations"]}/{m["objections"]}/{m["outcomes"]} '
            f'Action={result["next_best_action"]["action"]}'
        )

    print("=" * 78)
