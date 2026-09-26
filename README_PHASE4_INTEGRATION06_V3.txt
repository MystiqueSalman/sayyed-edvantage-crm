PHASE 4 INTEGRATION 06 V3
Purpose: force the live agent's commercial pricing path through the authoritative Master KB.

Run from project root:
1. python .\PATCH_PHASE4_INTEGRATION06_V3.py
2. python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION06_V3.py
3. python -c "from app.ai.agent import ask_agent; print(ask_agent('I am from India and interested in Data Science. What is the fee?', 'LIVE_I06_V3'))"

The patch creates a timestamped backup of app/ai/agent.py before writing.
