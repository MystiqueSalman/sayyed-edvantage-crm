
from pathlib import Path
import shutil
from datetime import datetime

AGENT = Path("app/ai/agent.py")

BRIDGE_IMPORT = (
    "from Sayyed_EdVantage_PHASE4_INTEGRATION06_V2 "
    "import get_master_kb_pricing\n"
)

WRAPPER = r"""
def _get_authoritative_pricing(course_name, international=False, region="India"):
    """ + '"""' + r"""Single commercial-pricing gateway: authoritative Master KB only.""" + '"""' + r"""
    return get_master_kb_pricing(
        course_name=course_name,
        international=international,
        region=region,
    )

"""


def main():
    if not AGENT.exists():
        raise SystemExit("agent.py not found. Run this from the project root.")

    original = AGENT.read_text(encoding="utf-8")
    text = original

    text = text.replace(
        "from app.ai.knowledge import get_course_pricing\n",
        ""
    )

    if BRIDGE_IMPORT not in text:
        marker = "from app.ai.memory import save_message, load_memory\n"
        if marker not in text:
            raise SystemExit(
                "Safe import insertion point not found. No changes written."
            )
        text = text.replace(marker, marker + BRIDGE_IMPORT, 1)

    if "def _get_authoritative_pricing(" not in text:
        marker = "SYSTEM_PROMPT = "
        pos = text.find(marker)
        if pos < 0:
            raise SystemExit(
                "SYSTEM_PROMPT marker not found. No changes written."
            )
        text = text[:pos] + WRAPPER + "\n" + text[pos:]

    text = text.replace(
        "get_course_pricing(",
        "_get_authoritative_pricing("
    )

    if "from app.ai.knowledge import get_course_pricing" in text:
        raise SystemExit("Legacy pricing import remains. No changes written.")

    if "get_course_pricing(" in text:
        raise SystemExit("Legacy pricing call remains. No changes written.")

    if text == original:
        print("NO CHANGES NEEDED")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = AGENT.with_name(
        AGENT.name + f".phase4i06v4_backup_{stamp}"
    )
    shutil.copy2(AGENT, backup)
    AGENT.write_text(text, encoding="utf-8")

    print("PHASE 4 INTEGRATION 06 V4 PATCH APPLIED")
    print(f"BACKUP: {backup}")
    print("ACTIVE COMMERCIAL SOURCE: MASTER_KB")
    print("LEGACY PRICING IMPORT/CALLS: REMOVED")


if __name__ == "__main__":
    main()
