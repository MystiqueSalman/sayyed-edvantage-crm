# Phase 4 Integration 05

Wires `app\ai\agent.py` so `ask_agent()` obtains course/commercial knowledge
from the authoritative Master KB bridge created in Integration 04.

The patch:
- creates a timestamped backup of `agent.py`
- removes the live `get_course_knowledge()` dependency from `ask_agent()`
- keeps existing conversation memory and session_id behavior
- fails closed if the Master KB bridge is unavailable
- does not modify leads.json
- does not delete courses.json

Apply:
```powershell
python .\PATCH_PHASE4_INTEGRATION05.py
```

Verify:
```powershell
python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION05.py
python -c "from app.ai.agent import ask_agent; print('AGENT IMPORT: OK')"
```
