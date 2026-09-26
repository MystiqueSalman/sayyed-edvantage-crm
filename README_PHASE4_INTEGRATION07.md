# Phase 4 Integration 07 — Live Agent Gateway
One clean entry point for live conversations.

- Stable `session_id` across turns.
- Optional verified `lead_id`.
- Reuses Phase 4 Integration 06.
- Read-only CRM behavior.
- No message sending or external actions.
- No execution authority.

Install both Python files in the project root. Replace same-named files; do not create `(1)` copies.

Test:
`python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION07.py`

Expected:
`PHASE 4 INTEGRATION 07 TEST RESULT: ALL PASSED`
`RETURN CODE: 0`

Example:
`python -c "from Sayyed_EdVantage_PHASE4_INTEGRATION07 import ask_live_agent; r=ask_live_agent('Hello','LIVE_USER_001','SE-00001'); print(r.status); print(r.response_text)"`
