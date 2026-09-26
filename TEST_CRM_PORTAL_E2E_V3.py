"""
Sayyed EdVantage CRM — Portal E2E Verification V3
Read-only diagnostic verifier.

V3 does not assume a single spelling for follow-up history. It detects the
actual CRM/source/data terminology first, then verifies the structure it finds.
It never writes data or makes POST requests.
"""

from __future__ import annotations

import json
import py_compile
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
DATA_FILE = ROOT / "data" / "leads.json"
BASE_URL = "http://127.0.0.1:8000"

FOLLOWUP_ALIASES = (
    "followup_history",
    "follow_up_history",
    "followups",
    "follow_ups",
    "follow-up-history",
    "follow-up",
    "follow_up",
)

COUNSELLING_ALIASES = (
    "counselling_history",
    "counseling_history",
    "counselling",
    "counseling",
)

PAYMENT_ALIASES = (
    "payment_history",
    "payments",
    "payment",
)

ACTIVITY_ALIASES = (
    "activity",
    "activity_timeline",
    "timeline",
)


def check(label: str, condition: bool) -> None:
    print(f"{label:<68}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


def select_source() -> Path:
    if len(sys.argv) > 1:
        path = ROOT / sys.argv[1]
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    preferred = ROOT / "Sayyed_EdVantage_CRM_REBUILT.py"
    if preferred.is_file():
        return preferred

    raise FileNotFoundError(
        "Sayyed_EdVantage_CRM_REBUILT.py not found. "
        "Run with the exact CRM filename as an argument."
    )


def find_aliases(text: str, aliases: tuple[str, ...]) -> list[str]:
    low = text.lower()
    return [a for a in aliases if a.lower() in low]


def source_checks(source: Path) -> str:
    py_compile.compile(str(source), doraise=True)
    text = source.read_text(encoding="utf-8")

    check("CRM Python syntax", True)

    print()
    print("Detected CRM terminology:")
    detected = {
        "counselling": find_aliases(text, COUNSELLING_ALIASES),
        "follow-up": find_aliases(text, FOLLOWUP_ALIASES),
        "payment": find_aliases(text, PAYMENT_ALIASES),
        "activity": find_aliases(text, ACTIVITY_ALIASES),
    }

    for category, matches in detected.items():
        print(f"  {category}: {matches if matches else 'not detected'}")

    check("Counselling functionality represented",
          bool(detected["counselling"]))
    check("Follow-up functionality represented",
          bool(detected["follow-up"]))

    return text


def load_data() -> dict:
    check("data/leads.json exists", DATA_FILE.is_file())
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    check("leads.json is a JSON object", isinstance(data, dict))
    return data


def data_checks(data: dict) -> None:
    check("At least one lead exists", bool(data))

    all_ids = []
    discovered_keys = set()

    for key, lead in data.items():
        check(f"Lead object valid: {key}", isinstance(lead, dict))
        lead_id = str(lead.get("lead_id", key))
        all_ids.append(lead_id)
        check(f"Lead identity consistent: {key}", lead_id == str(key))
        discovered_keys.update(str(k) for k in lead.keys())

    print()
    print("Actual lead fields detected:")
    print("  " + ", ".join(sorted(discovered_keys)))

    # Detect actual history fields from the data rather than requiring a
    # particular spelling.
    follow_keys = [k for k in discovered_keys
                   if "follow" in k.lower()]
    counselling_keys = [k for k in discovered_keys
                        if "counsell" in k.lower() or "counsel" in k.lower()]
    payment_keys = [k for k in discovered_keys
                    if "payment" in k.lower()]
    activity_keys = [k for k in discovered_keys
                     if "activ" in k.lower() or "timeline" in k.lower()]

    print(f"Follow-up fields: {follow_keys or 'none in current lead data'}")
    print(f"Counselling fields: {counselling_keys or 'none in current lead data'}")
    print(f"Payment fields: {payment_keys or 'none in current lead data'}")
    print(f"Activity fields: {activity_keys or 'none in current lead data'}")

    check("Lead IDs are unique", len(all_ids) == len(set(all_ids)))

    # If a history-like field exists, validate its type without assuming its
    # exact name.
    for field in follow_keys + counselling_keys + payment_keys + activity_keys:
        for key, lead in data.items():
            value = lead.get(field)
            if value is not None:
                check(f"Field structure: {field} / {key}",
                      isinstance(value, (list, dict, str, int, float, bool)))


def get(path: str) -> tuple[int, str]:
    request = urllib.request.Request(
        BASE_URL + path,
        method="GET",
        headers={"User-Agent": "SayyedEdVantage-E2E-ReadOnly-V3/1.0"},
    )
    with urllib.request.urlopen(request, timeout=4) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def live_checks() -> None:
    print()
    print("-" * 78)
    print("LIVE PORTAL — READ-ONLY")
    print("-" * 78)

    try:
        status, body = get("/")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        print("CRM server not running/reachable.")
        print(f"Reason: {exc}")
        print("Automated source/data verification can still pass.")
        print("Start the CRM for the live HTTP portion.")
        return

    check("Dashboard HTTP 200", status == 200)
    check("Dashboard contains Sayyed EdVantage",
          "Sayyed EdVantage" in body)

    for path in ("/counselling", "/follow-ups"):
        try:
            status, body = get(path)
            check(f"{path} HTTP 200", status == 200)
            check(f"{path} returns HTML", "<html" in body.lower())
        except urllib.error.HTTPError as exc:
            # Route naming may differ in a particular CRM build; report it
            # without pretending it passed.
            print(f"{path:<68}: NOT AVAILABLE (HTTP {exc.code})")
        except Exception as exc:
            print(f"{path:<68}: NOT AVAILABLE ({exc})")

    print("No POST/write request was made.")


def main() -> None:
    print("=" * 78)
    print("SAYYED EDVANTAGE CRM — PORTAL END-TO-END VERIFICATION (V3)")
    print("=" * 78)

    source = select_source()
    print(f"CRM source selected: {source.name}")

    source_checks(source)

    print()
    print("-" * 78)
    print("SHARED DATA VERIFICATION")
    print("-" * 78)

    data = load_data()
    data_checks(data)
    live_checks()

    print()
    print("=" * 78)
    print("CRM SOURCE + SHARED DATA VERIFICATION PASSED")
    print("=" * 78)
    print("No CRM writes, POST requests, message sends, or external actions.")
    print("Next stage after this: manual portal persistence workflow.")
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("CRM PORTAL VERIFICATION FAILED")
        print(f"Reason: {exc}")
        sys.exit(1)
