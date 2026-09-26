import json
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[2]
LEADS_FILE = BASE_DIR / "data" / "leads.json"


# Counselling configuration used by the CRM UI.
COUNSELLING_OUTCOMES = [
    "Pending",
    "Interested",
    "Not Interested",
    "Call Back",
    "Application",
    "Payment Pending",
    "Enrolled",
    "Lost",
]

COUNSELLING_MODES = [
    "Phone",
    "WhatsApp",
    "Video Call",
    "In Person",
    "Email",
]


def _ensure_leads_file() -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not LEADS_FILE.exists():
        LEADS_FILE.write_text("{}", encoding="utf-8")
        return

    try:
        data = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Leads file must contain a JSON object.")
    except (json.JSONDecodeError, OSError, ValueError):
        LEADS_FILE.write_text("{}", encoding="utf-8")


def load_leads() -> dict:
    _ensure_leads_file()

    try:
        data = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_leads(leads: dict) -> None:
    _ensure_leads_file()
    LEADS_FILE.write_text(
        json.dumps(leads, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_lead_id(leads: dict) -> str:
    highest_number = 0

    for lead_id in leads:
        if not isinstance(lead_id, str) or not lead_id.startswith("SE-"):
            continue

        number_part = lead_id[3:]
        if number_part.isdigit():
            highest_number = max(highest_number, int(number_part))

    return f"SE-{highest_number + 1:05d}"


def _normalize_phone(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def find_duplicate_lead(
    phone: str = "",
    email: str = "",
    exclude_lead_id: str = "",
):
    """
    Find an existing lead by exact normalized phone or email.
    Returns the lead dict or None.
    """

    phone_key = _normalize_phone(phone)
    email_key = _normalize_email(email)

    if not phone_key and not email_key:
        return None

    for lead_id, lead in load_leads().items():
        if lead_id == exclude_lead_id or not isinstance(lead, dict):
            continue

        existing_phone = _normalize_phone(lead.get("phone", ""))
        existing_email = _normalize_email(lead.get("email", ""))

        if phone_key and existing_phone and phone_key == existing_phone:
            return lead

        if email_key and existing_email and email_key == existing_email:
            return lead

    return None


def create_lead(
    name: str = "",
    phone: str = "",
    email: str = "",
    country: str = "",
    preferred_language: str = "",
    course_interest: str = "",
    education: str = "",
    message: str = "",
    source: str = "AI Agent",
) -> dict:
    leads = load_leads()

    duplicate = find_duplicate_lead(phone=phone, email=email)
    if duplicate:
        return duplicate

    now = datetime.now().isoformat(timespec="seconds")
    lead_id = generate_lead_id(leads)

    lead = {
        "lead_id": lead_id,
        "name": name,
        "phone": phone,
        "email": email,
        "country": country,
        "preferred_language": preferred_language,
        "course_interest": course_interest,
        "education": education,
        "message": message,
        "source": source,
        "status": "New",
        "follow_up_date": "",
        "follow_up_time": "",
        "follow_up_notes": "",
        "last_contacted_at": "",
        "assigned_counsellor": "",
        "payment_status": "Not Started",
        "international_student": (
            str(country or "").strip().lower()
            not in ("", "india", "indian")
        ),
        "counselling_history": [],
        "follow_up_history": [],
        "created_at": now,
        "updated_at": now,
    }

    leads[lead_id] = lead
    save_leads(leads)
    return lead


def get_lead(lead_id: str):
    return load_leads().get(lead_id)


def get_all_leads() -> list:
    return list(load_leads().values())


def update_lead(lead_id: str, **updates):
    leads = load_leads()

    if lead_id not in leads:
        return None

    allowed_fields = {
        "name",
        "phone",
        "email",
        "country",
        "preferred_language",
        "course_interest",
        "education",
        "message",
        "source",
        "status",
        "follow_up_date",
        "follow_up_time",
        "follow_up_notes",
        "last_contacted_at",
        "assigned_counsellor",
        "payment_status",
        "international_student",
        "counselling_history",
        "follow_up_history",
    }

    for field, value in updates.items():
        if field in allowed_fields:
            leads[lead_id][field] = value

    country = str(leads[lead_id].get("country", "")).strip().lower()
    leads[lead_id]["international_student"] = country not in ("", "india", "indian")
    leads[lead_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")

    save_leads(leads)
    return leads[lead_id]



def _ensure_follow_up_history(lead: dict) -> list:
    history = lead.get("follow_up_history", [])
    if not isinstance(history, list):
        history = []
        lead["follow_up_history"] = history
    return history


def add_follow_up_action(
    lead_id: str,
    outcome: str = "Contacted",
    notes: str = "",
    next_follow_up_date: str = "",
    next_follow_up_time: str = "",
    counsellor: str = "",
) -> dict | None:
    """Record a completed follow-up action and optionally schedule the next one."""
    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    outcome = str(outcome or "Contacted").strip()
    notes = str(notes or "").strip()
    next_follow_up_date = str(next_follow_up_date or "").strip()
    next_follow_up_time = str(next_follow_up_time or "").strip()
    counsellor = str(counsellor or lead.get("assigned_counsellor", "")).strip()

    allowed_outcomes = {
        "Contacted", "No Answer", "Call Back", "Interested",
        "Not Interested", "Application", "Payment Pending",
        "Enrolled", "Lost",
    }
    if outcome not in allowed_outcomes:
        outcome = "Contacted"

    now = datetime.now().isoformat(timespec="seconds")
    history = _ensure_follow_up_history(lead)

    previous_date = str(lead.get("follow_up_date", ""))
    previous_time = str(lead.get("follow_up_time", ""))

    status_map = {
        "Contacted": "Contacted",
        "No Answer": "Contacted",
        "Call Back": "Contacted",
        "Interested": "Interested",
        "Not Interested": "Lost",
        "Application": "Application",
        "Payment Pending": "Payment Pending",
        "Enrolled": "Enrolled",
        "Lost": "Lost",
    }

    if outcome in {"Enrolled", "Lost", "Not Interested"}:
        next_follow_up_date = ""
        next_follow_up_time = ""

    action = {
        "action_id": f"FU-{len(history) + 1:05d}",
        "action_at": now,
        "counsellor": counsellor,
        "outcome": outcome,
        "notes": notes,
        "previous_follow_up_date": previous_date,
        "previous_follow_up_time": previous_time,
        "next_follow_up_date": next_follow_up_date,
        "next_follow_up_time": next_follow_up_time,
        "status_after": status_map.get(outcome, lead.get("status", "New")),
    }

    history.append(action)
    lead["follow_up_history"] = history
    lead["last_contacted_at"] = now

    if counsellor:
        lead["assigned_counsellor"] = counsellor

    lead["status"] = status_map.get(outcome, lead.get("status", "New"))
    lead["follow_up_date"] = next_follow_up_date
    lead["follow_up_time"] = next_follow_up_time

    if notes:
        lead["follow_up_notes"] = notes

    lead["updated_at"] = now
    save_leads(leads)
    return action


def get_follow_up_history(lead_id: str) -> list:
    lead = get_lead(lead_id)
    if not isinstance(lead, dict):
        return []
    history = lead.get("follow_up_history", [])
    return history if isinstance(history, list) else []

def delete_lead(lead_id: str) -> bool:
    leads = load_leads()

    if lead_id not in leads:
        return False

    del leads[lead_id]
    save_leads(leads)
    return True


# ---------------------------------------------------------------------------
# Counselling Manager
# ---------------------------------------------------------------------------

def _ensure_counselling_history(lead: dict) -> list:
    history = lead.get("counselling_history", [])
    if not isinstance(history, list):
        history = []
        lead["counselling_history"] = history
    return history


def add_counselling_session(
    lead_id: str,
    counsellor: str = "",
    counselling_date: str = "",
    counselling_time: str = "",
    mode: str = "Phone",
    outcome: str = "Pending",
    notes: str = "",
    next_follow_up_date: str = "",
    next_follow_up_time: str = "",
) -> dict | None:
    """Add one counselling session to an existing lead."""
    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    if mode not in COUNSELLING_MODES:
        mode = "Phone"

    if outcome not in COUNSELLING_OUTCOMES:
        outcome = "Pending"

    now = datetime.now().isoformat(timespec="seconds")
    history = _ensure_counselling_history(lead)

    session = {
        "session_id": f"CS-{len(history) + 1:05d}",
        "counsellor": str(counsellor or "").strip(),
        "counselling_date": str(counselling_date or "").strip(),
        "counselling_time": str(counselling_time or "").strip(),
        "mode": mode,
        "outcome": outcome,
        "notes": str(notes or "").strip(),
        "next_follow_up_date": str(next_follow_up_date or "").strip(),
        "next_follow_up_time": str(next_follow_up_time or "").strip(),
        "created_at": now,
        "updated_at": now,
    }

    history.append(session)

    # Keep the main CRM fields synchronized with the latest counselling action.
    lead["counselling_history"] = history
    lead["assigned_counsellor"] = session["counsellor"] or lead.get("assigned_counsellor", "")
    lead["follow_up_date"] = session["next_follow_up_date"]
    lead["follow_up_time"] = session["next_follow_up_time"]
    lead["follow_up_notes"] = session["notes"]
    lead["last_contacted_at"] = now

    outcome_to_status = {
        "Interested": "Interested",
        "Application": "Application",
        "Payment Pending": "Payment Pending",
        "Enrolled": "Enrolled",
        "Lost": "Lost",
        "Not Interested": "Lost",
        "Call Back": "Contacted",
        "Pending": "Counselling",
    }
    lead["status"] = outcome_to_status.get(outcome, lead.get("status", "Counselling"))
    lead["updated_at"] = now

    save_leads(leads)
    return session


def get_counselling_history(lead_id: str) -> list:
    lead = get_lead(lead_id)
    if not isinstance(lead, dict):
        return []

    history = lead.get("counselling_history", [])
    return history if isinstance(history, list) else []


def get_latest_counselling(lead_id: str):
    history = get_counselling_history(lead_id)
    return history[-1] if history else None


def update_counselling_session(lead_id: str, session_id: str, **updates):
    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    history = _ensure_counselling_history(lead)

    allowed_fields = {
        "counsellor",
        "counselling_date",
        "counselling_time",
        "mode",
        "outcome",
        "notes",
        "next_follow_up_date",
        "next_follow_up_time",
    }

    for session in history:
        if not isinstance(session, dict) or session.get("session_id") != session_id:
            continue

        for field, value in updates.items():
            if field in allowed_fields:
                session[field] = value

        if session.get("mode") not in COUNSELLING_MODES:
            session["mode"] = "Phone"
        if session.get("outcome") not in COUNSELLING_OUTCOMES:
            session["outcome"] = "Pending"

        session["updated_at"] = datetime.now().isoformat(timespec="seconds")
        lead["counselling_history"] = history
        lead["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_leads(leads)
        return session

    return None


def delete_counselling_session(lead_id: str, session_id: str) -> bool:
    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return False

    history = _ensure_counselling_history(lead)
    original_length = len(history)
    history = [
        session
        for session in history
        if not isinstance(session, dict) or session.get("session_id") != session_id
    ]

    if len(history) == original_length:
        return False

    lead["counselling_history"] = history
    lead["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_leads(leads)
    return True


def get_counselling_statistics(leads=None) -> dict:
    """Return summary statistics for the Counselling Manager dashboard."""
    leads = leads if leads is not None else get_all_leads()

    total_sessions = 0
    total_students = 0
    outcome_counts = {outcome: 0 for outcome in COUNSELLING_OUTCOMES}

    for lead in leads:
        if not isinstance(lead, dict):
            continue

        history = lead.get("counselling_history", [])
        if not isinstance(history, list) or not history:
            continue

        total_students += 1
        total_sessions += len(history)

        for session in history:
            if not isinstance(session, dict):
                continue
            outcome = str(session.get("outcome", "Pending"))
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

    return {
        "total_sessions": total_sessions,
        "total_students_counselled": total_students,
        "outcome_counts": outcome_counts,
    }