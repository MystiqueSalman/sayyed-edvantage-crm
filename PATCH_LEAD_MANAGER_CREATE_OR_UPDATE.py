from pathlib import Path

TARGET = Path("app/leads/lead_manager.py")

def main():
    if not TARGET.exists():
        raise FileNotFoundError(f"Missing target: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    if "def create_or_update_lead(" in text:
        print("create_or_update_lead already exists. No changes made.")
        return

    marker = "\n# Get leads\n"
    if marker not in text:
        raise RuntimeError("Could not find safe insertion point before get_lead().")

    function = r