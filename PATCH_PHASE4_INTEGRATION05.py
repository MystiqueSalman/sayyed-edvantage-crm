from pathlib import Path
from datetime import datetime
import re
import shutil

ROOT = Path(__file__).resolve().parent
AGENT_FILE = ROOT / "app" / "ai" / "agent.py"
BRIDGE_FILE = ROOT / "Sayyed_EdVantage_PHASE4_INTEGRATION04.py"

BRIDGE_IMPORT = (
    "from Sayyed_EdVantage_PHASE4_INTEGRATION04 import "
    "build_authoritative_live_bridge"
)

HELPER = r'''
# ---------------------------------------------------------------------------
# Phase 4 Integration 05 — authoritative Master KB knowledge bridge
# ---------------------------------------------------------------------------

def _get_authoritative_master_kb_knowledge() -> str:
    """Get prompt-ready knowledge from the authoritative Master KB only."""
    project_root = Path(__file__).resolve().parents[2]
    bridge = build_authoritative_live_bridge(
        project_root=str(project_root),
        require_offerings=True,
    )
    if bridge.status != "BRIDGE_READY":
        reason = "; ".join(bridge.errors) if bridge.errors else "unknown bridge error"
        raise RuntimeError("AUTHORITATIVE_MASTER_KB_UNAVAILABLE: " + reason)

    sections = []
    for course in bridge.courses:
        lines = [
            f"Course ID: {course.get('course_id', '')}",
            f"Course Name: {course.get('official_name', '')}",
            f"Category: {course.get('category', '')}",
            f"Status: {course.get('status', '')}",
        ]
        knowledge = course.get("knowledge", {})
        if isinstance(knowledge, dict):
            for key, value in knowledge.items():
                lines.append(f"{key}: {value}")
        if course.get("source_ids"):
            lines.append(f"Source IDs: {course.get('source_ids')}")
        sections.append("\n".join(lines))

    offerings = []
    for item in bridge.offerings:
        offerings.append("\n".join([
            f"Offering ID: {item.get('offering_id', '')}",
            f"Offering Name: {item.get('name', '')}",
            f"Offering Type: {item.get('offering_type', '')}",
            f"Pricing Regions: {item.get('pricing_regions', {})}",
            f"Source IDs: {item.get('source_ids', [])}",
        ]))

    return (
        "AUTHORITATIVE SAYYED EDVANTAGE MASTER KNOWLEDGE BASE\n"
        "SOURCE OF TRUTH: MASTER_KB\n"
        "LEGACY courses.json FALLBACK: DISABLED\n\n"
        "COURSES\n" + "\n\n".join(sections)
        + "\n\nCOMMERCIAL OFFERINGS\n"
        + "\n\n".join(offerings)
    )
'''

def apply_patch_to_text(source: str) -> str:
    if "build_authoritative_live_bridge" not in source:
        marker = "from app.ai.knowledge import "
        if marker not in source:
            raise RuntimeError("Expected app.ai.knowledge import not found.")
        lines = source.splitlines()
        insert = 0
        while insert < len(lines) and (
            lines[insert].startswith("import ")
            or lines[insert].startswith("from ")
            or not lines[insert].strip()
        ):
            insert += 1
        lines.insert(insert, BRIDGE_IMPORT)
        source = "\n".join(lines) + "\n"

    if "_get_authoritative_master_kb_knowledge" not in source:
        marker = "\nSYSTEM_PROMPT ="
        if marker not in source:
            raise RuntimeError("SYSTEM_PROMPT marker not found.")
        source = source.replace(marker, HELPER + marker, 1)

    source, count = re.subn(
        r"course_knowledge\s*=\s*get_course_knowledge\(\)",
        "course_knowledge = _get_authoritative_master_kb_knowledge()",
        source,
    )
    if count == 0 and "course_knowledge = _get_authoritative_master_kb_knowledge()" not in source:
        raise RuntimeError("Live course_knowledge assignment not found.")

    source = re.sub(
        r"from app\.ai\.knowledge import ([^\n]*)",
        lambda m: ", ".join(
            x.strip() for x in m.group(1).split(",")
            if x.strip() != "get_course_knowledge"
        ).join(["from app.ai.knowledge import ", ""]) if False else (
            "from app.ai.knowledge import " + ", ".join(
                x.strip() for x in m.group(1).split(",")
                if x.strip() != "get_course_knowledge"
            )
        ),
        source,
    )
    return source

def apply_patch() -> None:
    if not AGENT_FILE.is_file():
        raise FileNotFoundError(AGENT_FILE)
    if not BRIDGE_FILE.is_file():
        raise FileNotFoundError(BRIDGE_FILE)

    original = AGENT_FILE.read_text(encoding="utf-8")
    patched = apply_patch_to_text(original)

    if patched == original:
        print("PATCH STATUS: ALREADY APPLIED")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = AGENT_FILE.with_name(f"agent.py.backup_{stamp}")
    shutil.copy2(AGENT_FILE, backup)
    AGENT_FILE.write_text(patched, encoding="utf-8")

    print("PHASE 4 INTEGRATION 05 PATCH APPLIED")
    print(f"BACKUP: {backup}")
    print("SOURCE OF TRUTH: MASTER_KB")
    print("LEGACY courses.json FALLBACK: DISABLED")

if __name__ == "__main__":
    apply_patch()
