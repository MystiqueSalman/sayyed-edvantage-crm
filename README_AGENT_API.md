# Agentic AI API

The live counselling agent is exposed through FastAPI.

## Run

Set `OPENAI_API_KEY` in `.env`, then start the service from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Endpoints

- `GET /health` checks that the service is running.
- `POST /api/chat` sends a message and preserves context by `session_id`.
- `DELETE /api/chat/{session_id}` clears one conversation.

Example request:

```json
{
  "session_id": "student-123",
  "message": "Which course is suitable after 12th?"
}
```

The chat endpoint uses the existing authoritative knowledge bridge, conversation
memory, international pricing safeguards, and CRM lead workflow in
`app.ai.agent`.
