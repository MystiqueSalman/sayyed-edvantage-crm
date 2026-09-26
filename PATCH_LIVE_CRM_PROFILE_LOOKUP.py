from pathlib import Path
import re

AGENT_FILE = Path("app/ai/agent.py")
if not AGENT_FILE.exists():
    raise FileNotFoundError(f"Could not find {AGENT_FILE}")

original = AGENT_FILE.read_text(encoding="utf-8")
backup = AGENT_FILE.with_suffix(".py.live_crm_profile_backup")
backup.write_text(original, encoding="utf-8")
text = original

old_import = "from app.leads.lead_manager import create_or_update_lead, get_all_leads"
new_import = "from app.leads.lead_manager import create_or_update_lead, get_all_leads, get_lead"

if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif "from app.leads.lead_manager import" in text and "get_lead" not in text:
    lines = text.splitlines(True)
    for i, line in enumerate(lines):
        if line.startswith("from app.leads.lead_manager import"):
            if "get_lead" not in line:
                lines[i] = line.rstrip("\n") + ", get_lead\n"
            break
    text = "".join(lines)
elif "get_lead" not in text:
    raise RuntimeError("Could not locate lead_manager import.")

marker = "def _find_existing_lead_from_text("
start = text.find(marker)
if start == -1:
    raise RuntimeError("Could not find _find_existing_lead_from_text().")

tail = text[start + len(marker):]
m = re.search(r"\n(?=def\s+\w+\s*\()", tail)
if not m:
    raise RuntimeError("Could not determine function boundary.")
end = start + len(marker) + m.start()
block = text[start:end]

insertion = """
    # Explicit CRM lead ID has highest priority.
    lead_id_match = re.search(r"\\b(SE-\\d{5})\\b", str(current_message or ""), re.IGNORECASE)
    if lead_id_match:
        explicit_lead = get_lead(lead_id_match.group(1).upper())
        if explicit_lead:
            return explicit_lead

    lead_id_match = re.search(r"\\b(SE-\\d{5})\\b", str(conversation_history or ""), re.IGNORECASE)
    if lead_id_match:
        explicit_lead = get_lead(lead_id_match.group(1).upper())
        if explicit_lead:
            return explicit_lead

"""

if "Explicit CRM lead ID has highest priority." not in block:
    triple_quote = chr(34) * 3
    first_doc = block.find(triple_quote)
    if first_doc != -1:
        second_doc = block.find(triple_quote, first_doc + 3)
        if second_doc == -1:
            raise RuntimeError("Malformed function docstring.")
        pos = second_doc + 3
    else:
        pos = block.find("\n") + 1
    block = block[:pos] + insertion + block[pos:]
    text = text[:start] + block + text[end:]
    AGENT_FILE.write_text(text, encoding="utf-8")
    print("LIVE CRM PROFILE LOOKUP PATCH APPLIED")
else:
    print("CRM PROFILE LOOKUP PATCH ALREADY PRESENT")

print(f"BACKUP: {backup}")
print("Explicit SE-xxxxx IDs now load the verified CRM record.")
print("No leads.json changes were made.")
