from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / "Sayyed_EdVantage_PHASE4_INTEGRATION09.py"
TEST = ROOT / "TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION09.py"

if not MODULE.exists():
    raise FileNotFoundError(f"Missing: {MODULE}")
if not TEST.exists():
    raise FileNotFoundError(f"Missing: {TEST}")

backup = MODULE.with_suffix(".py.phase4i09_backup")
shutil.copy2(MODULE, backup)

text = MODULE.read_text(encoding="utf-8")
old = "    lead_id: Optional[str]\n    response_text: str = \"\""
new = "    lead_id: Optional[str] = None\n    response_text: str = \"\""

if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError("LiveConversationResult lead_id declaration not found.")

MODULE.write_text(text, encoding="utf-8")

test = TEST.read_text(encoding="utf-8")
test = test.replace(
    'status=LIVE_API_BLOCKED,\n        session_id="TEST_SESSION_09",\n        response_allowed=False,',
    'status=LIVE_API_BLOCKED,\n        session_id="TEST_SESSION_09",\n        lead_id=None,\n        response_allowed=False,'
)
test = test.replace(
    'status=LIVE_API_CLARIFICATION,\n        session_id="TEST_SESSION_09",',
    'status=LIVE_API_CLARIFICATION,\n        session_id="TEST_SESSION_09",\n        lead_id=None,'
)
test = test.replace(
    'status=LIVE_API_UNKNOWN,\n        session_id="TEST_SESSION_09",',
    'status=LIVE_API_UNKNOWN,\n        session_id="TEST_SESSION_09",\n        lead_id=None,'
)
TEST.write_text(test, encoding="utf-8")

print("PHASE 4 INTEGRATION 09 CORRECTION APPLIED")
print(f"BACKUP: {backup.name}")
print("No leads.json changes were made.")
