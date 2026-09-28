"""Phase 12 §21.6 — virtual labs (fully simulated, browser-side).

No real infra, no containers, no SSH: scenarios are faculty-authored JSON
(a canned filesystem + ordered tasks) and the terminal emulator is pure
JavaScript in vlab_terminal.html. This module only validates scenario JSON
and records completion.
"""
import json
from datetime import datetime

from . import db
from .models import VLabProgress, VLabScenario

EXAMPLE_SCENARIO = {
    "fs": {
        "home": {"student": {"notes.txt": "Welcome to the Linux lab!",
                             "todo.txt": "1. explore\n2. practice"}},
        "var": {"log": {}},
    },
    "tasks": [
        {"instruction": "Print the current directory",
         "validate": {"command": "pwd"}},
        {"instruction": "List the files in your home directory",
         "validate": {"command": "ls", "contains": ["notes.txt"]}},
        {"instruction": "Show the contents of notes.txt",
         "validate": {"contains": ["Welcome to the Linux lab!"]}},
    ],
}


def example_json():
    return json.dumps(EXAMPLE_SCENARIO, indent=2)


def validate_scenario_json(raw):
    """Returns (ok, data_or_error)."""
    try:
        data = json.loads(raw or "{}")
    except Exception as exc:
        return False, f"Invalid JSON: {exc}"
    if not isinstance(data, dict):
        return False, "Top level must be an object"
    fs = data.get("fs", {})
    tasks = data.get("tasks", [])
    if not isinstance(fs, dict):
        return False, "'fs' must be an object"
    if not isinstance(tasks, list) or not tasks:
        return False, "'tasks' must be a non-empty list"
    for i, t in enumerate(tasks, 1):
        if not isinstance(t, dict) or not t.get("instruction"):
            return False, f"task {i}: needs an 'instruction'"
    return True, data


def mark_complete(scenario_id, user_id, log=""):
    """Idempotent completion record. Returns the VLabProgress row."""
    prog = VLabProgress.query.filter_by(scenario_id=scenario_id,
                                        user_id=user_id).first()
    if not prog:
        prog = VLabProgress(scenario_id=scenario_id, user_id=user_id)
        db.session.add(prog)
    prog.completed = True
    prog.log = (log or "")[-5000:]
    prog.completed_at = datetime.utcnow()
    db.session.commit()
    return prog
