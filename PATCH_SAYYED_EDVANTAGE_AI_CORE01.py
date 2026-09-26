from pathlib import Path

target = Path(__file__).resolve().parent / "Sayyed_EdVantage_AI_CORE01.py"

text = target.read_text(encoding="utf-8")

old = """    elif answer.integration_status == "INTEGRATION_HANDOFF":
        runtime_status = RUNTIME_HANDOFF
        response = ""
        handoff = True
    else:
"""

new = """    elif answer.integration_status == "INTEGRATION_HANDOFF":
        runtime_status = RUNTIME_HANDOFF
        response = ""
        handoff = True
        # Preserve the upstream handoff diagnostics so the Agent runtime
        # does not lose the reason normal delivery was blocked.
        errors.extend(answer.gate_errors)
    else:
"""

if old not in text:
    raise RuntimeError(
        "Expected AI Core 01 handoff block was not found. No file was changed."
    )

target.write_text(text.replace(old, new, 1), encoding="utf-8")
print("AI Core 01 patch applied successfully.")
