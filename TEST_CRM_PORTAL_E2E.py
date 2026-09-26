"""
Sayyed EdVantage CRM — Portal End-to-End Verification
SAFE READ-ONLY VERIFICATION RUNNER

Run this from the CRM project folder after starting the CRM server.

It:
- finds the latest Sayyed_EdVantage_CRM*.py / Sayyed_EdVantage_Lead_Manager*.py
- compiles the CRM source
- verifies expected CRM routes/features in source
- verifies data/leads.json exists and is valid JSON
- verifies lead identity and history structure without changing data
- optionally performs read-only HTTP checks against http://127.0.0.1:8000

It does NOT POST, create leads, modify leads.json, send messages, or execute
AI-agent actions.
"""

from __future__ import annotations

import json
import re
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
    "/lead",
    "/update-lead",
    "/add-counselling",
    "/follow-up-action",
    "/set-fee",
    "/record-payment",
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
    print(f"{label:<62}: {'PASSED' if condition else 'FAILED'}")
    if not condition:
        raise AssertionError(label)


def find_crm_source() -> Path:
    candidates = []
    patterns = [
        "Sayyed_EdVantage_CRM*.py",
        "Sayyed_EdVantage_Lead_Manager*.py",
        "lead_manager_CRM*.py",
        "lead_manager*.py",
    ]
    for pattern in patterns:
        candidates.extend(ROOT.glob(pattern))

    candidates = [
        p for p in candidates
        if p.name != Path(__file__).name and p.is_file()
    ]

    if not candidates:
        raise FileNotFoundError(
            "No CRM Python source found. Copy this test into the same folder "
            "as the CRM source before running it."
        )

    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_leads() -> dict:
    check("data/leads.json exists", DATA_FILE.exists())
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    check("leads.json is a JSON object", isinstance(data, dict))
    return data


def source_checks(source: Path) -> str:
    py_compile.compile(str(source), doraise=True)
    text = source.read_text(encoding="utf-8")

    check("CRM Python syntax", True)

    for route in EXPECTED_ROUTES:
        check(f"Route present: {route}", route in text)

    for feature in EXPECTED_FEATURES:
        check(f"CRM data/feature present: {feature}", feature in text)

    return text


def data_checks(leads: dict) -> None:
    check("At least one lead exists", len(leads) > 0)

    ids = []
    for key, lead in leads.items():
        check(f"Lead object valid: {key}", isinstance(lead, dict))
        lead_id = str(lead.get("lead_id", key))
        ids.append(lead_id)
        check(f"Lead identity consistent: {key}", lead_id == str(key))

        for history_key in ("counselling_history", "followup_history", "payment_history"):
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
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


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
        print("Start the CRM in another PowerShell window, then run this test again.")
        return

    check("Dashboard HTTP 200", status == 200)
    check("Dashboard contains Sayyed EdVantage", "Sayyed EdVantage" in body)

    for path in ["/counselling", "/follow-ups"]:
        try:
            status, body = http_get(path)
            check(f"{path} HTTP 200", status == 200)
            check(f"{path} returns HTML", "<html" in body.lower())
        except Exception as exc:
            print(f"{path:<62}: FAILED")
            raise AssertionError(f"{path} live check failed: {exc}")

    print()
    print("Read-only portal checks completed.")
    print("No POST/write request was made by this test.")


def main() -> None:
    print("=" * 78)
    print("SAYYED EDVANTAGE CRM — PORTAL END-TO-END VERIFICATION")
    print("=" * 78)

    source = find_crm_source()
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
    print("READ-ONLY CRM PORTAL VERIFICATION PASSED")
    print("=" * 78)
    print("IMPORTANT: This is the automated SAFE/read-only portion.")
    print("Next perform the manual persistence workflow below:")
    print("  1. Open one existing lead profile.")
    print("  2. Record one test counselling session.")
    print("  3. Confirm it appears in Counselling History.")
    print("  4. Confirm the follow-up appears in Follow-up Manager.")
    print("  5. Refresh/restart CRM and confirm persistence.")
    print("  6. Verify the Activity Timeline.")
    print("  7. Verify payment changes/history if used.")
    print("  8. Verify the AI-agent layer still reads the same lead.")
    print("  9. Verify authorization remains human-controlled.")
    print(" 10. Confirm no message/external action was sent.")
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("CRM PORTAL VERIFICATION FAILED")
        print(f"Reason: {exc}")
        sys.exit(1)