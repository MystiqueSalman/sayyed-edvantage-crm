from pathlib import Path
import shutil
from datetime import datetime

AGENT = Path("app/ai/agent.py")

def main():
    if not AGENT.exists():
        raise SystemExit("agent.py not found")

    original = AGENT.read_text(encoding="utf-8")
    text = original

    text = text.replace("from app.ai.knowledge import get_course_pricing\n", "")

    bridge_import = (
        "from Sayyed_EdVantage_PHASE4_INTEGRATION06 import get_master_kb_pricing\n"
    )
    if bridge_import not in text:
        marker = "from app.ai.memory import save_message, load_memory\n"
        if marker not in text:
            raise SystemExit("Safe import insertion point not found. No changes written.")
        text = text.replace(marker, marker + bridge_import, 1)

    old = """pricing = get_course_pricing(
            detected_course,
            international=True
        )"""
    new = """pricing = get_master_kb_pricing(
            detected_course,
            international=True,
            region=detected_country,
        )"""

    if old in text:
        text = text.replace(old, new, 1)
    elif "get_course_pricing(" in text:
        raise SystemExit("Unexpected legacy pricing call format. No changes written.")

    if text == original:
        print("NO CHANGES NEEDED")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(str(AGENT) + f".phase4i06_backup_{stamp}")
    shutil.copy2(AGENT, backup)
    AGENT.write_text(text, encoding="utf-8")

    remaining = []
    if "from app.ai.knowledge import get_course_pricing" in text:
        remaining.append("legacy pricing import remains")
    if "get_course_pricing(" in text:
        remaining.append("legacy pricing call remains")
    if remaining:
        AGENT.write_text(original, encoding="utf-8")
        raise SystemExit("PATCH ROLLED BACK: " + "; ".join(remaining))

    print("PHASE 4 INTEGRATION 06 PATCH APPLIED")
    print(f"BACKUP: {backup}")
    print("SOURCE OF TRUTH: MASTER_KB")
    print("LEGACY PRICING FALLBACK: DISABLED")

if __name__ == "__main__":
    main()
