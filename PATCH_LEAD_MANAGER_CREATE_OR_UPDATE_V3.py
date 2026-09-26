from pathlib import Path

TARGET = Path("app/leads/lead_manager.py")

FUNCTION = '# ---------------------------------------------------------------------------\n# AI Agent compatibility API\n# ---------------------------------------------------------------------------\n\ndef create_or_update_lead(\n    name: str = "",\n    phone: str = "",\n    email: str = "",\n    country: str = "",\n    preferred_language: str = "",\n    course_interest: str = "",\n    education: str = "",\n    message: str = "",\n    source: str = "AI Agent",\n) -> dict:\n    """Create a new CRM lead or update an exact existing phone/email match."""\n    name = str(name or "").strip()\n    phone = str(phone or "").strip()\n    email = str(email or "").strip()\n    country = str(country or "").strip()\n    preferred_language = str(preferred_language or "").strip()\n    course_interest = str(course_interest or "").strip()\n    education = str(education or "").strip()\n    message = str(message or "").strip()\n    source = str(source or "AI Agent").strip() or "AI Agent"\n\n    duplicate = find_duplicate_lead(phone=phone, email=email)\n\n    if duplicate:\n        lead_id = str(duplicate.get("lead_id", "")).strip()\n        if not lead_id:\n            return duplicate\n\n        supplied = {\n            "name": name,\n            "phone": phone,\n            "email": email,\n            "country": country,\n            "preferred_language": preferred_language,\n            "course_interest": course_interest,\n            "education": education,\n            "message": message,\n            "source": source,\n        }\n        updates = {key: value for key, value in supplied.items() if value}\n\n        if not updates:\n            return duplicate\n\n        updated = update_lead(lead_id, **updates)\n        return updated if isinstance(updated, dict) else duplicate\n\n    return create_lead(\n        name=name,\n        phone=phone,\n        email=email,\n        country=country,\n        preferred_language=preferred_language,\n        course_interest=course_interest,\n        education=education,\n        message=message,\n        source=source,\n    )\n'

def main():
    if not TARGET.exists():
        raise FileNotFoundError(TARGET)

    text = TARGET.read_text(encoding="utf-8")

    if "def create_or_update_lead(" in text:
        print("create_or_update_lead already exists. No changes made.")
        return

    marker = "\ndef get_lead("
    position = text.find(marker)
    if position == -1:
        raise RuntimeError("Could not locate def get_lead() insertion point.")

    patched = text[:position] + "\n" + FUNCTION + text[position:]
    TARGET.write_text(patched, encoding="utf-8")

    print("PATCH V3 APPLIED")
    print("Added create_or_update_lead() before get_lead().")
    print("Existing create_lead/update_lead logic preserved.")
    print("No leads.json changes were made by this patch.")

if __name__ == "__main__":
    main()
