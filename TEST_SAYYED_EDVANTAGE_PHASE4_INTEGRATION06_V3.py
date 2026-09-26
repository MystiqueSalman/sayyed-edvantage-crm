from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
AGENT = ROOT / "app" / "ai" / "agent.py"

def check(name, condition):
    if not condition:
        print(f"FAIL: {name}")
        raise SystemExit(1)
    print(f"PASS: {name}")

def run():
    text = AGENT.read_text(encoding="utf-8")
    check("agent.py exists", AGENT.exists())
    check("Master KB pricing bridge imported",
          "Sayyed_EdVantage_PHASE4_INTEGRATION06_V2 import get_master_kb_pricing" in text)
    check("legacy pricing import removed",
          "from app.ai.knowledge import get_course_pricing" not in text)
    check("legacy pricing calls removed",
          "get_course_pricing(" not in text)
    check("authoritative pricing gateway exists",
          "def _get_authoritative_pricing(" in text)

    p = subprocess.run(
        [sys.executable, "-c",
         "from app.ai.agent import ask_agent; print('AGENT IMPORT: OK')"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    print(p.stdout.strip())
    if p.stderr.strip():
        print(p.stderr.strip())
    check("agent imports", p.returncode == 0 and "AGENT IMPORT: OK" in p.stdout)

    print("\nPHASE 4 INTEGRATION 06 V3 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")

if __name__ == "__main__":
    run()
