import json
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[2]
LEADS_FILE = BASE_DIR / "data" / "leads.json"


# ---------------------------------------------------------------------------
# Counselling configuration
# ---------------------------------------------------------------------------

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


PAYMENT_STATUSES = [
    "Not Started",
    "Pending",
    "Partial",
    "Paid",
    "Failed",
    "Refunded",
]

PAYMENT_MODES = [
    "Cash",
    "UPI",
    "Bank Transfer",
    "Card",
    "Online",
    "Other",
]

ADMISSION_STATUSES = [
    "Not Started",
    "Application",
    "Documents Pending",
    "Payment Pending",
    "Ready for Enrollment",
    "Enrolled",
    "Cancelled",
]


# ---------------------------------------------------------------------------
# Leads file management
# ---------------------------------------------------------------------------

def _ensure_leads_file() -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not LEADS_FILE.exists():
        LEADS_FILE.write_text("{}", encoding="utf-8")
        return

    try:
        data = json.loads(
            LEADS_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            raise ValueError("Leads file must contain a JSON object.")

    except (json.JSONDecodeError, OSError, ValueError):
        LEADS_FILE.write_text("{}", encoding="utf-8")


def load_leads() -> dict:
    _ensure_leads_file()

    try:
        data = json.loads(
            LEADS_FILE.read_text(encoding="utf-8")
        )

        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        return {}


def save_leads(leads: dict) -> None:
    _ensure_leads_file()

    LEADS_FILE.write_text(
        json.dumps(
            leads,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Lead ID
# ---------------------------------------------------------------------------

def generate_lead_id(leads: dict) -> str:
    highest_number = 0

    for lead_id in leads:
        if not isinstance(lead_id, str):
            continue

        if not lead_id.startswith("SE-"):
            continue

        number_part = lead_id[3:]

        if number_part.isdigit():
            highest_number = max(
                highest_number,
                int(number_part),
            )

    return f"SE-{highest_number + 1:05d}"


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_phone(value: str) -> str:
    return "".join(
        ch
        for ch in str(value or "")
        if ch.isdigit()
    )


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


# ---------------------------------------------------------------------------
# Duplicate lead detection
# ---------------------------------------------------------------------------

def find_duplicate_lead(
    phone: str = "",
    email: str = "",
    exclude_lead_id: str = "",
):
    """
    Find an existing lead by exact normalized phone or email.

    Returns:
        lead dict or None
    """

    phone_key = _normalize_phone(phone)
    email_key = _normalize_email(email)

    if not phone_key and not email_key:
        return None

    for lead_id, lead in load_leads().items():

        if lead_id == exclude_lead_id:
            continue

        if not isinstance(lead, dict):
            continue

        existing_phone = _normalize_phone(
            lead.get("phone", "")
        )

        existing_email = _normalize_email(
            lead.get("email", "")
        )

        if (
            phone_key
            and existing_phone
            and phone_key == existing_phone
        ):
            return lead

        if (
            email_key
            and existing_email
            and email_key == existing_email
        ):
            return lead

    return None


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------

def _ensure_status_history(lead: dict) -> list:
    """
    Make sure every lead has a valid status_history list.
    """

    history = lead.get("status_history", [])

    if not isinstance(history, list):
        history = []
        lead["status_history"] = history

    return history


def _record_status_change(
    lead: dict,
    new_status: str,
    changed_at: str | None = None,
) -> None:
    """
    Record a status change while preserving the complete lead journey.

    Example:

        New
        -> Contacted
        -> Counselling
        -> Interested
        -> Application
        -> Payment Pending
        -> Enrolled
    """

    new_status = str(
        new_status or ""
    ).strip()

    if not new_status:
        return

    current_status = str(
        lead.get("status", "New") or "New"
    ).strip()

    if current_status == new_status:
        return

    changed_at = changed_at or datetime.now().isoformat(
        timespec="seconds"
    )

    history = _ensure_status_history(lead)

    # If this is an older lead which does not yet have
    # status history, preserve its current status first.
    if not history:

        history.append(
            {
                "status": current_status,
                "changed_at": str(
                    lead.get(
                        "created_at",
                        changed_at,
                    )
                ),
            }
        )

    history.append(
        {
            "status": new_status,
            "changed_at": changed_at,
        }
    )

    lead["status_history"] = history


# ---------------------------------------------------------------------------
# Create lead
# ---------------------------------------------------------------------------

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

    duplicate = find_duplicate_lead(
        phone=phone,
        email=email,
    )

    if duplicate:
        return duplicate

    now = datetime.now().isoformat(
        timespec="seconds"
    )

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

        # Fee / Payment Management
        "student_type": (
            "International"
            if str(country or "").strip().lower() not in ("", "india", "indian")
            else "Indian"
        ),
        "base_fee": 0.0,
        "discount": 0.0,
        "final_fee": 0.0,
        "total_paid": 0.0,
        "balance_amount": 0.0,
        "converted_amount": 0.0,
        "currency": "INR",
        "payment_mode": "",
        "transaction_id": "",
        "payment_date": "",
        "payment_history": [],

        # Admission Management
        "admission_status": "Not Started",
        "admission_date": "",
        "student_id": "",
        "batch": "",
        "batch_start_date": "",

        "international_student": (
            str(country or "").strip().lower()
            not in (
                "",
                "india",
                "indian",
            )
        ),

        "counselling_history": [],
        "follow_up_history": [],

        # NEW:
        # Complete status journey of the lead.
        "status_history": [
            {
                "status": "New",
                "changed_at": now,
            }
        ],

        "created_at": now,
        "updated_at": now,
    }

    leads[lead_id] = lead

    save_leads(leads)

    return lead


# ---------------------------------------------------------------------------
# Get leads
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AI Agent compatibility API
# ---------------------------------------------------------------------------

def create_or_update_lead(
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
    """Create a new CRM lead or update an exact existing phone/email match."""
    name = str(name or "").strip()
    phone = str(phone or "").strip()
    email = str(email or "").strip()
    country = str(country or "").strip()
    preferred_language = str(preferred_language or "").strip()
    course_interest = str(course_interest or "").strip()
    education = str(education or "").strip()
    message = str(message or "").strip()
    source = str(source or "AI Agent").strip() or "AI Agent"

    duplicate = find_duplicate_lead(phone=phone, email=email)

    if duplicate:
        lead_id = str(duplicate.get("lead_id", "")).strip()
        if not lead_id:
            return duplicate

        supplied = {
            "name": name,
            "phone": phone,
            "email": email,
            "country": country,
            "preferred_language": preferred_language,
            "course_interest": course_interest,
            "education": education,
            "message": message,
            "source": source,
        }
        updates = {key: value for key, value in supplied.items() if value}

        if not updates:
            return duplicate

        updated = update_lead(lead_id, **updates)
        return updated if isinstance(updated, dict) else duplicate

    return create_lead(
        name=name,
        phone=phone,
        email=email,
        country=country,
        preferred_language=preferred_language,
        course_interest=course_interest,
        education=education,
        message=message,
        source=source,
    )

def get_lead(lead_id: str):
    return load_leads().get(lead_id)


def get_all_leads() -> list:
    return list(
        load_leads().values()
    )


# ---------------------------------------------------------------------------
# Update lead
# ---------------------------------------------------------------------------

def update_lead(
    lead_id: str,
    **updates,
):
    leads = load_leads()

    if lead_id not in leads:
        return None

    lead = leads[lead_id]

    if not isinstance(lead, dict):
        return None

    old_status = str(
        lead.get("status", "New") or "New"
    ).strip()

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
        "status_history",

        # Fee / Payment
        "student_type",
        "base_fee",
        "discount",
        "final_fee",
        "total_paid",
        "balance_amount",
        "converted_amount",
        "currency",
        "payment_mode",
        "transaction_id",
        "payment_date",
        "payment_history",

        # Admission
        "admission_status",
        "admission_date",
        "student_id",
        "batch",
        "batch_start_date",
    }

    # Update only approved fields.
    for field, value in updates.items():

        if field in allowed_fields:
            lead[field] = value

    new_status = str(
        lead.get("status", old_status)
        or old_status
    ).strip()

    # -------------------------------------------------------
    # NEW STATUS HISTORY
    # -------------------------------------------------------

    if new_status != old_status:

        changed_at = datetime.now().isoformat(
            timespec="seconds"
        )

        history = _ensure_status_history(lead)

        if not history:

            history.append(
                {
                    "status": old_status,
                    "changed_at": str(
                        lead.get(
                            "created_at",
                            changed_at,
                        )
                    ),
                }
            )

        history.append(
            {
                "status": new_status,
                "changed_at": changed_at,
            }
        )

        lead["status_history"] = history

    # -------------------------------------------------------
    # International student calculation
    # -------------------------------------------------------

    country = str(
        lead.get("country", "")
    ).strip().lower()

    lead["international_student"] = (
        country not in (
            "",
            "india",
            "indian",
        )
    )

    # -------------------------------------------------------
    # Updated timestamp
    # -------------------------------------------------------

    lead["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    save_leads(leads)

    return lead


# ---------------------------------------------------------------------------
# Follow-up history
# ---------------------------------------------------------------------------

def _ensure_follow_up_history(
    lead: dict,
) -> list:

    history = lead.get(
        "follow_up_history",
        [],
    )

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

    """
    Record a completed follow-up action
    and optionally schedule the next one.
    """

    leads = load_leads()

    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    outcome = str(
        outcome or "Contacted"
    ).strip()

    notes = str(
        notes or ""
    ).strip()

    next_follow_up_date = str(
        next_follow_up_date or ""
    ).strip()

    next_follow_up_time = str(
        next_follow_up_time or ""
    ).strip()

    counsellor = str(
        counsellor
        or lead.get(
            "assigned_counsellor",
            "",
        )
    ).strip()

    allowed_outcomes = {
        "Contacted",
        "No Answer",
        "Call Back",
        "Interested",
        "Not Interested",
        "Application",
        "Payment Pending",
        "Enrolled",
        "Lost",
    }

    if outcome not in allowed_outcomes:
        outcome = "Contacted"

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    history = _ensure_follow_up_history(
        lead
    )

    previous_date = str(
        lead.get(
            "follow_up_date",
            "",
        )
    )

    previous_time = str(
        lead.get(
            "follow_up_time",
            "",
        )
    )

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

    new_status = status_map.get(
        outcome,
        lead.get(
            "status",
            "New",
        ),
    )

    # Enrolled / Lost leads do not need
    # another scheduled follow-up.
    if outcome in {
        "Enrolled",
        "Lost",
        "Not Interested",
    }:

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

        "status_after": new_status,
    }

    history.append(action)

    lead["follow_up_history"] = history

    lead["last_contacted_at"] = now

    if counsellor:
        lead["assigned_counsellor"] = counsellor

    # Record status history BEFORE changing status.
    _record_status_change(
        lead,
        new_status,
        changed_at=now,
    )

    lead["status"] = new_status

    lead["follow_up_date"] = (
        next_follow_up_date
    )

    lead["follow_up_time"] = (
        next_follow_up_time
    )

    if notes:
        lead["follow_up_notes"] = notes

    lead["updated_at"] = now

    save_leads(leads)

    return action


def get_follow_up_history(
    lead_id: str,
) -> list:

    lead = get_lead(lead_id)

    if not isinstance(lead, dict):
        return []

    history = lead.get(
        "follow_up_history",
        [],
    )

    return (
        history
        if isinstance(history, list)
        else []
    )


# ---------------------------------------------------------------------------
# Delete lead
# ---------------------------------------------------------------------------

def delete_lead(
    lead_id: str,
) -> bool:

    leads = load_leads()

    if lead_id not in leads:
        return False

    del leads[lead_id]

    save_leads(leads)

    return True


# ===========================================================================
# COUNSELLING MANAGER
# ===========================================================================

def _ensure_counselling_history(
    lead: dict,
) -> list:

    history = lead.get(
        "counselling_history",
        [],
    )

    if not isinstance(history, list):

        history = []

        lead["counselling_history"] = history

    return history


# ---------------------------------------------------------------------------
# Add counselling session
# ---------------------------------------------------------------------------

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

    """
    Add one counselling session
    to an existing lead.
    """

    leads = load_leads()

    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    if mode not in COUNSELLING_MODES:
        mode = "Phone"

    if outcome not in COUNSELLING_OUTCOMES:
        outcome = "Pending"

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    history = _ensure_counselling_history(
        lead
    )

    session = {
        "session_id": f"CS-{len(history) + 1:05d}",

        "counsellor": str(
            counsellor or ""
        ).strip(),

        "counselling_date": str(
            counselling_date or ""
        ).strip(),

        "counselling_time": str(
            counselling_time or ""
        ).strip(),

        "mode": mode,

        "outcome": outcome,

        "notes": str(
            notes or ""
        ).strip(),

        "next_follow_up_date": str(
            next_follow_up_date or ""
        ).strip(),

        "next_follow_up_time": str(
            next_follow_up_time or ""
        ).strip(),

        "created_at": now,

        "updated_at": now,
    }

    history.append(session)

    lead["counselling_history"] = history

    lead["assigned_counsellor"] = (
        session["counsellor"]
        or lead.get(
            "assigned_counsellor",
            "",
        )
    )

    lead["follow_up_date"] = (
        session["next_follow_up_date"]
    )

    lead["follow_up_time"] = (
        session["next_follow_up_time"]
    )

    lead["follow_up_notes"] = (
        session["notes"]
    )

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

    new_status = outcome_to_status.get(
        outcome,
        lead.get(
            "status",
            "Counselling",
        ),
    )

    # Record status history.
    _record_status_change(
        lead,
        new_status,
        changed_at=now,
    )

    lead["status"] = new_status

    lead["updated_at"] = now

    save_leads(leads)

    return session


# ---------------------------------------------------------------------------
# Get counselling history
# ---------------------------------------------------------------------------

def get_counselling_history(
    lead_id: str,
) -> list:

    lead = get_lead(lead_id)

    if not isinstance(lead, dict):
        return []

    history = lead.get(
        "counselling_history",
        [],
    )

    return (
        history
        if isinstance(history, list)
        else []
    )


def get_latest_counselling(
    lead_id: str,
):

    history = get_counselling_history(
        lead_id
    )

    return (
        history[-1]
        if history
        else None
    )


# ---------------------------------------------------------------------------
# Update counselling session
# ---------------------------------------------------------------------------

def update_counselling_session(
    lead_id: str,
    session_id: str,
    **updates,
):

    leads = load_leads()

    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    history = _ensure_counselling_history(
        lead
    )

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

        if not isinstance(
            session,
            dict,
        ):
            continue

        if session.get(
            "session_id"
        ) != session_id:
            continue

        old_outcome = str(
            session.get(
                "outcome",
                "Pending",
            )
        )

        for field, value in updates.items():

            if field in allowed_fields:
                session[field] = value

        if session.get(
            "mode"
        ) not in COUNSELLING_MODES:

            session["mode"] = "Phone"

        if session.get(
            "outcome"
        ) not in COUNSELLING_OUTCOMES:

            session["outcome"] = "Pending"

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        session["updated_at"] = now

        # ---------------------------------------------------
        # Synchronize main lead fields
        # ---------------------------------------------------

        lead["counselling_history"] = history

        if session.get("counsellor"):
            lead["assigned_counsellor"] = (
                session["counsellor"]
            )

        lead["follow_up_date"] = str(
            session.get(
                "next_follow_up_date",
                "",
            )
            or ""
        )

        lead["follow_up_time"] = str(
            session.get(
                "next_follow_up_time",
                "",
            )
            or ""
        )

        lead["follow_up_notes"] = str(
            session.get(
                "notes",
                "",
            )
            or ""
        )

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

        new_status = outcome_to_status.get(
            session.get(
                "outcome",
                "Pending",
            ),
            lead.get(
                "status",
                "Counselling",
            ),
        )

        current_status = str(
            lead.get(
                "status",
                "New",
            )
        )

        if (
            old_outcome
            != session.get(
                "outcome",
                "Pending",
            )
        ) or current_status != new_status:

            _record_status_change(
                lead,
                new_status,
                changed_at=now,
            )

            lead["status"] = new_status

        lead["last_contacted_at"] = now

        lead["updated_at"] = now

        save_leads(leads)

        return session

    return None


# ---------------------------------------------------------------------------
# Delete counselling session
# ---------------------------------------------------------------------------

def delete_counselling_session(
    lead_id: str,
    session_id: str,
) -> bool:

    leads = load_leads()

    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return False

    history = _ensure_counselling_history(
        lead
    )

    original_length = len(history)

    history = [
        session
        for session in history
        if not (
            isinstance(session, dict)
            and session.get(
                "session_id"
            ) == session_id
        )
    ]

    if len(history) == original_length:
        return False

    lead["counselling_history"] = history

    lead["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    save_leads(leads)

    return True


# ---------------------------------------------------------------------------
# Counselling statistics
# ---------------------------------------------------------------------------

def get_counselling_statistics(
    leads=None,
) -> dict:

    """
    Return summary statistics
    for the Counselling Manager dashboard.
    """

    leads = (
        leads
        if leads is not None
        else get_all_leads()
    )

    total_sessions = 0

    total_students = 0

    outcome_counts = {
        outcome: 0
        for outcome in COUNSELLING_OUTCOMES
    }

    for lead in leads:

        if not isinstance(
            lead,
            dict,
        ):
            continue

        history = lead.get(
            "counselling_history",
            [],
        )

        if (
            not isinstance(history, list)
            or not history
        ):
            continue

        total_students += 1

        total_sessions += len(history)

        for session in history:

            if not isinstance(
                session,
                dict,
            ):
                continue

            outcome = str(
                session.get(
                    "outcome",
                    "Pending",
                )
            )

            outcome_counts[outcome] = (
                outcome_counts.get(
                    outcome,
                    0,
                )
                + 1
            )

    return {
        "total_sessions": total_sessions,
        "total_students_counselled": total_students,
        "outcome_counts": outcome_counts,
    }

# ===========================================================================
# PAYMENT MANAGEMENT
# ===========================================================================

def _ensure_payment_history(lead: dict) -> list:
    history = lead.get("payment_history", [])

    if not isinstance(history, list):
        history = []
        lead["payment_history"] = history

    return history


def _safe_amount(value, default=0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _recalculate_payment_totals(lead: dict) -> dict:
    """
    Keep the complete fee calculation consistent.

    final_fee = base_fee - discount
    balance_amount = final_fee - total_paid
    """

    base_fee = max(0.0, _safe_amount(lead.get("base_fee", 0)))
    discount = max(0.0, _safe_amount(lead.get("discount", 0)))
    total_paid = max(0.0, _safe_amount(lead.get("total_paid", 0)))

    final_fee = max(0.0, base_fee - discount)
    balance = max(0.0, final_fee - total_paid)

    lead["base_fee"] = base_fee
    lead["discount"] = discount
    lead["final_fee"] = final_fee
    lead["total_paid"] = total_paid
    lead["balance_amount"] = balance

    if final_fee <= 0:
        lead["payment_status"] = lead.get(
            "payment_status",
            "Not Started",
        )
    elif total_paid <= 0:
        lead["payment_status"] = "Not Started"
    elif total_paid < final_fee:
        lead["payment_status"] = "Partial"
    else:
        lead["payment_status"] = "Paid"

    return lead


def set_fee_details(
    lead_id: str,
    base_fee=0,
    discount=0,
    currency: str = "INR",
    converted_amount=0,
):
    """
    Set course fee details for a lead.

    Existing payment history is preserved.
    """

    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    lead["base_fee"] = max(0.0, _safe_amount(base_fee))
    lead["discount"] = max(0.0, _safe_amount(discount))
    lead["currency"] = str(currency or "INR").strip() or "INR"
    lead["converted_amount"] = max(
        0.0,
        _safe_amount(converted_amount),
    )

    _recalculate_payment_totals(lead)
    lead["updated_at"] = datetime.now().isoformat(timespec="seconds")

    save_leads(leads)
    return lead


def get_payment_summary(lead_id: str) -> dict | None:
    lead = get_lead(lead_id)

    if not isinstance(lead, dict):
        return None

    history = _ensure_payment_history(lead)
    _recalculate_payment_totals(lead)

    return {
        "lead_id": lead_id,
        "student_type": lead.get("student_type", "Indian"),
        "base_fee": lead.get("base_fee", 0.0),
        "discount": lead.get("discount", 0.0),
        "final_fee": lead.get("final_fee", 0.0),
        "total_paid": lead.get("total_paid", 0.0),
        "balance_amount": lead.get("balance_amount", 0.0),
        "currency": lead.get("currency", "INR"),
        "converted_amount": lead.get("converted_amount", 0.0),
        "payment_status": lead.get(
            "payment_status",
            "Not Started",
        ),
        "payment_mode": lead.get("payment_mode", ""),
        "transaction_id": lead.get("transaction_id", ""),
        "payment_date": lead.get("payment_date", ""),
        "payment_history": history,
    }


def record_payment(
    lead_id: str,
    amount,
    payment_mode: str = "Online",
    transaction_id: str = "",
    payment_date: str = "",
    notes: str = "",
):
    """
    Record one payment and automatically update:

        total_paid
        balance_amount
        payment_status

    A payment cannot exceed the configured remaining balance.
    """

    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    amount = _safe_amount(amount)

    if amount <= 0:
        return None

    if payment_mode not in PAYMENT_MODES:
        payment_mode = "Other"

    final_fee = max(
        0.0,
        _safe_amount(lead.get("final_fee", 0)),
    )
    current_paid = max(
        0.0,
        _safe_amount(lead.get("total_paid", 0)),
    )

    if final_fee > 0:
        remaining = max(0.0, final_fee - current_paid)

        if remaining <= 0:
            return None

        amount = min(amount, remaining)

    now = datetime.now().isoformat(timespec="seconds")

    if not payment_date:
        payment_date = now[:10]

    history = _ensure_payment_history(lead)

    payment = {
        "payment_id": f"PAY-{len(history) + 1:05d}",
        "amount": amount,
        "payment_mode": payment_mode,
        "transaction_id": str(transaction_id or "").strip(),
        "payment_date": str(payment_date or "").strip(),
        "notes": str(notes or "").strip(),
        "recorded_at": now,
    }

    history.append(payment)

    lead["payment_history"] = history
    lead["total_paid"] = current_paid + amount
    lead["payment_mode"] = payment_mode
    lead["transaction_id"] = payment["transaction_id"]
    lead["payment_date"] = payment["payment_date"]

    _recalculate_payment_totals(lead)

    lead["updated_at"] = now
    save_leads(leads)

    return payment


def update_payment_status(
    lead_id: str,
    payment_status: str,
):
    if payment_status not in PAYMENT_STATUSES:
        payment_status = "Not Started"

    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    lead["payment_status"] = payment_status
    lead["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    save_leads(leads)
    return lead


def get_payment_history(lead_id: str) -> list:
    lead = get_lead(lead_id)

    if not isinstance(lead, dict):
        return []

    history = lead.get("payment_history", [])
    return history if isinstance(history, list) else []


# ===========================================================================
# ADMISSION MANAGEMENT
# ===========================================================================

def update_admission(
    lead_id: str,
    admission_status: str = "",
    admission_date: str = "",
    student_id: str = "",
    batch: str = "",
    batch_start_date: str = "",
):
    """
    Update admission information.

    Payment completion does NOT automatically enroll the student.
    Enrollment is a separate admission action.
    """

    leads = load_leads()
    lead = leads.get(lead_id)

    if not isinstance(lead, dict):
        return None

    if admission_status:
        if admission_status not in ADMISSION_STATUSES:
            admission_status = "Not Started"

        lead["admission_status"] = admission_status

        if admission_status == "Enrolled":
            if not admission_date:
                admission_date = datetime.now().strftime("%Y-%m-%d")

            lead["admission_date"] = admission_date

            _record_status_change(
                lead,
                "Enrolled",
                changed_at=datetime.now().isoformat(
                    timespec="seconds"
                ),
            )

            lead["status"] = "Enrolled"

    if admission_date:
        lead["admission_date"] = admission_date

    if student_id:
        lead["student_id"] = student_id

    if batch:
        lead["batch"] = batch

    if batch_start_date:
        lead["batch_start_date"] = batch_start_date

    lead["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    save_leads(leads)
    return lead


def get_admission_summary(lead_id: str) -> dict | None:
    lead = get_lead(lead_id)

    if not isinstance(lead, dict):
        return None

    return {
        "lead_id": lead_id,
        "admission_status": lead.get(
            "admission_status",
            "Not Started",
        ),
        "admission_date": lead.get("admission_date", ""),
        "student_id": lead.get("student_id", ""),
        "batch": lead.get("batch", ""),
        "batch_start_date": lead.get(
            "batch_start_date",
            "",
        ),
        "payment_status": lead.get(
            "payment_status",
            "Not Started",
        ),
        "final_fee": lead.get("final_fee", 0.0),
        "total_paid": lead.get("total_paid", 0.0),
        "balance_amount": lead.get(
            "balance_amount",
            0.0,
        ),
    }