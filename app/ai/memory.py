import json
from pathlib import Path
from typing import Any


MEMORY_FILE = Path("data") / "conversations.json"


def _ensure_memory_file() -> None:
    """Create the memory folder and file if they don't exist."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("{}", encoding="utf-8")


def load_memory(session_id: str) -> list[dict[str, Any]]:
    """Load conversation history for one session."""
    _ensure_memory_file()

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    return data.get(session_id, [])


def save_message(
    session_id: str,
    role: str,
    content: str,
) -> None:
    """Save one conversation message."""
    _ensure_memory_file()

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    if session_id not in data:
        data[session_id] = []

    data[session_id].append(
        {
            "role": role,
            "content": content,
        }
    )

    MEMORY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_memory(session_id: str) -> None:
    """Clear the conversation history for one session."""
    _ensure_memory_file()

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    data.pop(session_id, None)

    MEMORY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )