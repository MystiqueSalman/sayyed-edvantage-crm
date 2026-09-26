from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

from app.ai.agent import ask_agent
from app.ai.memory import clear_memory


app = FastAPI(
    title="Sayyed EdVantage Agentic AI API",
    version="1.0.0",
    description="CRM-aware education counselling agent for Sayyed EdVantage.",
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str = Field(
        default="default_student",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )


class ChatResponse(BaseModel):
    session_id: str
    response: str


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sayyed-edvantage-agent")


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be blank")

    try:
        response = ask_agent(message, session_id=request.session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(session_id=request.session_id, response=response)


@app.delete("/api/chat/{session_id}", status_code=204)
def reset_chat(
    session_id: str = Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    ),
) -> None:
    clear_memory(session_id)