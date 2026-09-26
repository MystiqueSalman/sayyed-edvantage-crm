# Phase 4 Integration 09 — Corrected

The screenshot showed a constructor error because `LiveConversationResult`
required `lead_id` even for a session with no CRM lead.

This correction makes `lead_id` optional (`None` by default) and aligns the
existing test cases with that contract.

## Files

- PATCH_PHASE4_INTEGRATION09_LEAD_OPTIONAL.py

## Use

Copy the patch file into the project root:

`C:\Users\SALMAN SAYYED\Documents\SayyedEdVantage-AI-Agent`

Then run:

```powershell
python .\PATCH_PHASE4_INTEGRATION09_LEAD_OPTIONAL.py
```

Then run the existing Integration 09 test:

```powershell
python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION09.py
```

Expected:

```text
PHASE 4 INTEGRATION 09 TEST RESULT: ALL PASSED
RETURN CODE: 0
```

A backup of the implementation is created automatically.
No `leads.json` changes are made.
