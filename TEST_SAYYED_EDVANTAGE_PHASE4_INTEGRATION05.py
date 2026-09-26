from pathlib import Path
import importlib.util
import tempfile

PATCH = Path(__file__).with_name("PATCH_PHASE4_INTEGRATION05.py")
spec = importlib.util.spec_from_file_location("i05", PATCH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)

def main():
    total = passed = 0
    def t(label, condition):
        nonlocal total, passed
        total += 1
        check(label, condition)
        passed += 1

    original = '''import json
from app.ai.client import ask_ai
from app.ai.knowledge import get_course_knowledge, get_course_pricing
from app.ai.memory import save_message, load_memory

SYSTEM_PROMPT = "Sayyed EdVantage"

def ask_agent(user_message: str, session_id: str = "default_student") -> str:
    history = load_memory(session_id)
    course_knowledge = get_course_knowledge()
    prompt = f"{SYSTEM_PROMPT} {course_knowledge} {user_message}"
    save_message(session_id, "user", user_message)
    response = ask_ai(prompt)
    save_message(session_id, "assistant", response)
    return response
'''

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app" / "ai").mkdir(parents=True)
        agent = root / "app" / "ai" / "agent.py"
        agent.write_text(original, encoding="utf-8")
        old_a, old_b = mod.AGENT_FILE, mod.BRIDGE_FILE
        mod.AGENT_FILE = agent
        mod.BRIDGE_FILE = root / "Sayyed_EdVantage_PHASE4_INTEGRATION04.py"
        mod.BRIDGE_FILE.write_text("# bridge", encoding="utf-8")

        patched = mod.apply_patch_to_text(original)

        t("bridge import added", "build_authoritative_live_bridge" in patched)
        t("Master KB helper added", "_get_authoritative_master_kb_knowledge" in patched)
        t("ask_agent uses Master KB helper",
          "course_knowledge = _get_authoritative_master_kb_knowledge()" in patched)
        t("legacy course loader removed",
          "course_knowledge = get_course_knowledge()" not in patched)
        t("pricing compatibility retained", "get_course_pricing" in patched)
        t("session_id retained", 'session_id: str = "default_student"' in patched)
        t("memory loading retained", "load_memory(session_id)" in patched)
        t("user save retained", 'save_message(session_id, "user", user_message)' in patched)
        t("assistant save retained", 'save_message(session_id, "assistant", response)' in patched)
        compile(patched, str(agent), "exec")
        t("patched agent syntax valid", True)

        mod.AGENT_FILE, mod.BRIDGE_FILE = old_a, old_b

    print()
    print(f"PHASE 4 INTEGRATION 05 TEST RESULT: {passed}/{total} PASSED")
    print("RETURN CODE: 0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
