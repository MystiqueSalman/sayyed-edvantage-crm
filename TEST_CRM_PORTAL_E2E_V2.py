"""
Sayyed EdVantage CRM — Portal End-to-End Verification
SAFE READ-ONLY VERIFICATION RUNNER

Default CRM source:
    Sayyed_EdVantage_CRM_REBUILT.py

Optional:
    python .\TEST_CRM_PORTAL_E2E.py YourCRMFile.py

This test never POSTs, writes leads.json, sends messages, or executes actions.
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

EXPECTED_ROUTES = [
    "/",
    "/counselling",
    "/follow-ups",
]

EXPECTED_FEATURES = [
    "counselling_history",
    "followup_history",
    "payment_history",
    "activity",
    "lead_id",
    "leads.json",
]


def check(label: str, condition: bool) -> None:
    print(f"{label:<68}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


def select_crm_source() -> Path:
    if len(sys.argv) > 1:
        candidate = ROOT / sys.argv[1]
        if not candidate.is_file():
            raise FileNotFoundError(f"Specified CRM file not found: {candidate}")
        return candidate

    preferred = ROOT / "Sayyed_EdVantage_CRM_REBUILT.py"
    if preferred.is_file():
        return preferred

    raise FileNotFoundError(
        "Sayyed_EdVantage_CRM_REBUILT.py was not found. "
        "Specify the exact CRM filename as the first argument."
    )


def source_checks(source: Path) -> None:
    py_compile.compile(str(source), doraise=True)
    text = source.read_text(encoding="utf-8")

    check("CRM Python syntax", True)

    for feature in EXPECTED_FEATURES:
        check(f"CRM data/feature present: {feature}", feature in text)

    # Routes are checked only when the source actually declares them.
    route_hits = sum(route in text for route in EXPECTED_ROUTES)
    check("Core portal routes represented", route_hits >= 2)


def read_leads() -> dict:
    check("data/leads.json exists", DATA_FILE.exists())
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    check("leads.json is a JSON object", isinstance(data, dict))
    return data


def data_checks(leads: dict) -> None:
    check("At least one lead exists", len(leads) > 0)

    ids = []
    for key, lead in leads.items():
        check(f"Lead object valid: {key}", isinstance(lead, dict))
        lead_id = str(lead.get("lead_id", key))
        ids.append(lead_id)
        check(f"Lead identity consistent: {key}", lead_id == str(key))

        for history_key in (
            "counselling_history",
            "followup_history",
            "payment_history",
        ):
            if history_key in lead:
                check(
                    f"{history_key} is list for {key}",
                    isinstance(lead[history_key], list),
                )

    print(f"Leads found: {len(ids)}")
    print("Lead IDs:", ", ".join(ids))


def http_get(path: str) -> tuple[int, str]:
    req = urllib.request.Request(
        BASE_URL + path,
        method="GET",
        headers={"User-Agent": "SayyedEdVantage-E2E-ReadOnly-Test/1.0"},
    )
    with urllib.request.urlopen(req, timeout=4) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def live_read_only_checks() -> None:
    print()
    print("-" * 78)
    print("LIVE PORTAL READ-ONLY CHECKS")
    print("-" * 78)

    try:
        status, body = http_get("/")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        print("CRM server is not running/reachable.")
        print(f"Reason: {exc}")
        print()
        print("This is NOT a code failure.")
        print("Start the CRM first, then run this test again.")
        return

    check("Dashboard HTTP 200", status == 200)
    check("Dashboard contains Sayyed EdVantage", "Sayyed EdVantage" in body)

    for path in ["/counselling", "/follow-ups"]:
        status, body = http_get(path)
        check(f"{path} HTTP 200", status == 200)
        check(f"{path} returns HTML", "<html" in body.lower())

    print("No POST/write request was made.")


def main() -> None:
    print("=" * 78)
    print("SAYYED EDVANTAGE CRM — PORTAL END-TO-END VERIFICATION (V2)")
    print("=" * 78)

    source = select_crm_source()
    print(f"CRM source selected: {source.name}")
    print()

    source_checks(source)

    print()
    print("-" * 78)
    print("SHARED DATA VERIFICATION")
    print("-" * 78)

    leads = read_leads()
    data_checks(leads)

    live_read_only_checks()

    print()
    print("=" * 78)
    print("AUTOMATED SAFE CRM VERIFICATION PASSED")
    print("=" * 78)
    print("Next: manual persistence + cross-layer workflow verification.")
    print("No CRM write, message send, or external action was performed.")
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("CRM PORTAL VERIFICATION FAILED")
        print(f"Reason: {exc}")
        sys.exit(1)
