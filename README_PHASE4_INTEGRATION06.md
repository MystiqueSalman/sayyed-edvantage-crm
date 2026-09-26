# Phase 4 Integration 06

## Unified Live Conversation State + CRM + Master KB + Agent Response Pipeline

This integration adds a thin, read-only live-session orchestration layer.

It:
- keeps one explicit `session_id` across live turns;
- keeps a lead reference bound to that session;
- reuses the verified CRM record through `get_lead()`;
- delegates response generation to the existing `app.ai.agent.ask_agent(message, session_id)`;
- preserves local turn history for the running live session;
- fails closed when a supplied CRM lead does not exist;
- never writes `leads.json`;
- never sends messages or performs external actions.

## Files

- `Sayyed_EdVantage_PHASE4_INTEGRATION06.py`
- `TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION06.py`

## Install

Copy both files to the project root:

```powershell
Copy-Item .\Sayyed_EdVantage_PHASE4_INTEGRATION06.py .
Copy-Item .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION06.py .
```

## Verify

```powershell
python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION06.py
```

Expected:

```text
PHASE 4 INTEGRATION 06 TEST RESULT: ALL PASSED
RETURN CODE: 0
```

## Important

The `session_id` should be the same value for every turn belonging to one live conversation.

Example:

```powershell
python -c "from Sayyed_EdVantage_PHASE4_INTEGRATION06 import run_live_turn; print(run_live_turn('Hello', 'LIVE_INT_06', 'SE-00001').response_text)"
```

Then use the same `LIVE_INT_06` for the next turn.

This layer does not grant execution authority.
