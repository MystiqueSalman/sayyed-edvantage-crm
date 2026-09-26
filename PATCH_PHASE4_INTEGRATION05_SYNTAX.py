from pathlib import Path

AGENT_FILE = Path("app/ai/agent.py")

if not AGENT_FILE.exists():
    raise FileNotFoundError(f"Could not find {AGENT_FILE}")

original = AGENT_FILE.read_text(encoding="utf-8")
text = original

# Path is used by the Phase 4 Integration 05 Master KB bridge helper.
if "from pathlib import import Path" not in text and "from pathlib import Path" not in text:
    text = text.replace("import re\n", "import re\nfrom pathlib import Path\n", 1)

bad = """from app.ai.currency import (
from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge
    get_currency_for_country,
    convert_inr_to_country_currency,
)"""

good = """from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge
from app.ai.currency import (
    get_currency_for_country,
    convert_inr_to_country_currency,
)"""

if bad in text:
    text = text.replace(bad, good, 1)
else:
    marker = "from app.ai.currency import (\nfrom Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge"
    if marker in text:
        text = text.replace(
            marker,
            "from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge\nfrom app.ai.currency import (",
            1,
        )
    else:
        raise RuntimeError("Malformed Integration 05 import block was not found.")

backup = AGENT_FILE.with_suffix(".py.phase4int05_syntax_backup")
backup.write_text(original, encoding="utf-8")
AGENT_FILE.write_text(text, encoding="utf-8")

print("PHASE 4 INTEGRATION 05 SYNTAX PATCH APPLIED")
print(f"BACKUP: {backup}")
print("Fixed bridge/currency import ordering.")
print("Ensured pathlib.Path is imported.")
