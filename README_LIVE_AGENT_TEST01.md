# Sayyed EdVantage — LIVE AGENT TEST 01

This is the first controlled test of the **actual** `app.ai.agent.ask_agent()`
in the user's project.

## Important

This test is observational. It does not call `create_lead`, `update_lead`,
`delete_lead`, messaging functions, payment functions, or external-action
functions.

It snapshots `data\leads.json` before the test and verifies that both its SHA-256
hash and parsed JSON content are unchanged afterward.

## Install

Copy these files to:

`C:\Users\SALMAN SAYYED\Documents\SayyedEdVantage-AI-Agent`

If the same filenames already exist, choose **Replace**.

## Run

Make sure the `.venv` is active:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```powershell
python .\TEST_SAYYED_EDVANTAGE_LIVE_AGENT_TEST01.py
```

If your agent uses an external model provider, its existing API configuration
must already be available.

## Expected

```text
LIVE AGENT TEST 01 RESULT: ALL PASSED
CRM WRITE CHECK: PASS
MESSAGE SEND CHECK: PASS
EXTERNAL ACTION CHECK: PASS
RETURN CODE: 0
```

## What this test covers

1. Greeting / natural conversation
2. Data Science knowledge
3. Indian fee
4. International fee safety
5. Eligibility
6. Recommendation clarification
7. Conversation memory
8. Counselling continuity
9. Fee objection handling
10. Certification safety
11. Career/job guarantee safety
12. CRM identity handling
13. Payment/enrollment safety
14. Unknown-course handling
15. CRM immutability

A passing result does **not** mean the complete live agent is production-ready.
It means the first controlled live-agent smoke/safety gate passed. We then
continue with the broader adversarial and end-to-end test matrix.
