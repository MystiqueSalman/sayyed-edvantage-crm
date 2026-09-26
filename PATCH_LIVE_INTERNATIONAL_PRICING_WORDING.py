from pathlib import Path

AGENT_FILE = Path("app/ai/agent.py")

if not AGENT_FILE.exists():
    raise FileNotFoundError(f"Could not find {AGENT_FILE}")

original = AGENT_FILE.read_text(encoding="utf-8")

# Keep a backup before changing the live agent.
backup = AGENT_FILE.with_suffix(".py.live_pricing_backup")
backup.write_text(original, encoding="utf-8")

text = original

replacements = {
    "International pricing is currently available only on request.": (
        "International pricing is not currently defined in the available course "
        "information. Our admissions team can confirm the applicable international "
        "fee and payment details."
    ),
    "International pricing is currently available on request.": (
        "International pricing is not currently defined in the available course "
        "information. Our admissions team can confirm the applicable international "
        "fee and payment details."
    ),
    "International pricing is available on request.": (
        "International pricing is not currently defined in the available course "
        "information. Our admissions team can confirm the applicable international "
        "fee and payment details."
    ),
}

changed = False
for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)
        changed = True

if not changed:
    print("NO EXACT INTERNATIONAL-PRICING PHRASE FOUND")
    print("No changes were made to agent.py.")
    print(f"Backup: {backup}")
else:
    AGENT_FILE.write_text(text, encoding="utf-8")
    print("LIVE INTERNATIONAL PRICING WORDING PATCH APPLIED")
    print(f"BACKUP: {backup}")
    print("No CRM/data files were changed.")
