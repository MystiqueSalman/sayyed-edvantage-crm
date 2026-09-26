# Phase 4 Integration 08 — Live Session Manager

Adds a managed session layer around Phase 4 Integration 07.

## Guarantees

- One stable `session_id` represents one conversation.
- A session may be bound to one `lead_id`.
- A different lead cannot silently take over the session.
- Follow-up turns reuse the existing session and lead.
- Ended sessions reject new turns.
- Missing CRM identity remains fail-closed.
- No CRM writes.
- No messages are sent.
- No external actions are executed.

## Install

Extract into:

`C:\Users\SALMAN SAYYED\Documents\SayyedEdVantage-AI-Agent`

If the same-named files exist, choose **Replace**, not Rename.

## Test

```powershell
python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION08.py
```

Expected:

```text
PHASE 4 INTEGRATION 08 TEST RESULT: ALL PASSED
RETURN CODE: 0
```

## Session example

Use one ID for the whole conversation:

`LIVE_USER_001`

and, when the CRM lead is known:

`SE-00001`

The same session ID should be reused for subsequent questions.
