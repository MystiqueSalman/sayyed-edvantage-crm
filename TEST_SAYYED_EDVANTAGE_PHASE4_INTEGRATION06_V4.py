
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


def main():
    check("agent.py exists", AGENT.exists())
    text = AGENT.read_text(encoding="utf-8")

    check(
        "Master KB pricing bridge imported",
        "Sayyed_EdVantage_PHASE4_INTEGRATION06_V2" in text
        and "get_master_kb_pricing" in text,
    )
    check(
        "legacy pricing import removed",
        "from app.ai.knowledge import get_course_pricing" not in text,
    )
    check(
        "legacy pricing calls removed",
        "get_course_pricing(" not in text,
    )
    check(
        "authoritative pricing gateway exists",
        "def _get_authoritative_pricing(" in text,
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.ai.agent import ask_agent; print('AGENT IMPORT: OK')",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())

    check(
        "agent imports",
        result.returncode == 0
        and "AGENT IMPORT: OK" in result.stdout,
    )

    print()
    print("PHASE 4 INTEGRATION 06 V4 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")


if __name__ == "__main__":
    main()
