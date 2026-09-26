from pathlib import Path
import re, shutil
from datetime import datetime
AGENT = Path("app/ai/agent.py")

def main():
    if not AGENT.exists():
        raise SystemExit("agent.py not found")
    original = AGENT.read_text(encoding="utf-8")
    text = original
    text = text.replace("from app.ai.knowledge import get_course_pricing\n", "")
    imp = "from Sayyed_EdVantage_PHASE4_INTEGRATION06_V2 import get_master_kb_pricing\n"
    if imp not in text:
        marker = "from app.ai.memory import save_message, load_memory\n"
        if marker not in text:
            raise SystemExit("Safe import insertion point not found. No changes written.")
        text = text.replace(marker, marker + imp, 1)

    # Handles the multiline formatting visible in the current agent.py.
    pattern = re.compile(
        r"(?m)^(?P<i>[ \\t]*)pricing\\s*=\\s*get_course_pricing\\(\\s*"
        r"(?P<a>[^,\\n\\)]+)\\s*,\\s*international\\s*=\\s*True\\s*\\)"
    )
    m = pattern.search(text)
    if m:
        i, a = m.group("i"), m.group("a").strip()
        repl = (f"{i}pricing = get_master_kb_pricing(\n"
                f"{i}    {a},\n"
                f"{i}    international=True,\n"
                f"{i}    region=detected_country,\n"
                f"{i})")
        text = text[:m.start()] + repl + text[m.end():]
    elif "get_course_pricing(" in text:
        raise SystemExit("Legacy pricing remains in an unsupported format. No changes written.")

    if text == original:
        print("NO CHANGES NEEDED")
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(str(AGENT) + f".phase4i06v2_backup_{stamp}")
    shutil.copy2(AGENT, backup)
    AGENT.write_text(text, encoding="utf-8")
    if "get_course_pricing(" in text or "from app.ai.knowledge import get_course_pricing" in text:
        AGENT.write_text(original, encoding="utf-8")
        raise SystemExit("PATCH ROLLED BACK: legacy pricing path remains")
    print("PHASE 4 INTEGRATION 06 V2 PATCH APPLIED")
    print("BACKUP:", backup)
    print("ACTIVE COMMERCIAL SOURCE: MASTER_KB")
    print("LEGACY PRICING FALLBACK: DISABLED")
if __name__ == "__main__":
    main()
