
PHASE 4 INTEGRATION 06 V4

V4 replaces the faulty V3 patch. V3 had a nested raw-string construction
error that caused: NameError: name 'r' is not defined.

Purpose:
Route the live agent commercial pricing through the authoritative
Master KB bridge and remove the legacy pricing import/calls.

Run from the project root:

python .\PATCH_PHASE4_INTEGRATION06_V4.py

python .\TEST_SAYYED_EDVANTAGE_PHASE4_INTEGRATION06_V4.py

python -c "from app.ai.agent import ask_agent; print(ask_agent('I am from India and interested in Data Science. What is the fee?', 'LIVE_I06_V4'))"

A timestamped backup of app\ai\agent.py is created before writing.
