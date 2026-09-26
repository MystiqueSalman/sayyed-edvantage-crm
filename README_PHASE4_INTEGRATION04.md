# Phase 4 Integration 04 — Master KB → Live Agent Knowledge Bridge

This integration establishes the completed Master Knowledge Base as the
authoritative source for live-agent course/commercial knowledge.

## Files
- `Sayyed_EdVantage_PHASE4_INTEGRATION04.py`
- `TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION04.py`

## Important
The bridge deliberately has **no fallback to `data\knowledge\courses.json`**.
That prevents two competing sources of truth.

The bridge is read-only and does not:
- write CRM
- write courses.json
- send messages
- perform external actions
- invoke an executor
- grant execution authority

## Test
From the project root:

```powershell
python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION04.py
```

Expected:
```text
PHASE 4 INTEGRATION 04 TEST RESULT: 38/38 PASSED
RETURN CODE: 0
```

## Next integration
After this contract passes, the next step is to connect `app\ai\agent.py`
to this bridge so `ask_agent()` obtains course/commercial knowledge from the
Master KB rather than directly from the legacy `courses.json`.
