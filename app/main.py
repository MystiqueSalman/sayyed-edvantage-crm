import logging
import os
import secrets

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from app import whatsapp
from app.ai.agent import ask_agent
from app.ai.memory import clear_memory


logger = logging.getLogger("sayyed_edvantage.api")


app = FastAPI(
    title="Sayyed EdVantage Agentic AI API",
    version="1.0.0",
    description="CRM-aware education counselling agent for Sayyed EdVantage.",
)


# HTTP Basic Auth for the /api/* endpoints. Uses the same credentials as the
# CRM dashboard (SE_CRM_USER / SE_CRM_PASSWORD). /health stays open so the
# hosting platform's healthcheck keeps working.
security = HTTPBasic(auto_error=False)


def _api_user() -> str:
    return os.environ.get("SE_CRM_USER", "")


def _api_password() -> str:
    return os.environ.get("SE_CRM_PASSWORD", "")


def require_auth(
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> None:
    expected_user = _api_user()
    expected_password = _api_password()
    if not expected_user or not expected_password:
        # Fail closed: never serve the API without credentials configured.
        raise HTTPException(status_code=503, detail="API auth not configured")
    if credentials is None or not (
        secrets.compare_digest(credentials.username, expected_user)
        and secrets.compare_digest(credentials.password, expected_password)
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
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


PRIVACY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy &ndash; Sayyed EdVantage</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:2rem auto;padding:0 1.25rem;line-height:1.65;color:#1a1a2e}
h1{color:#0f1f4b}h2{color:#0f1f4b;margin-top:2rem}
</style>
</head>
<body>
<h1>Privacy Policy &ndash; Sayyed EdVantage</h1>
<p><em>Effective: 26 September 2026</em></p>

<h2>Who we are</h2>
<p>Sayyed EdVantage (&ldquo;Empowering Students for Success&rdquo;) provides training
and counselling for courses including Data Science, Artificial Intelligence, Generative AI,
Python Programming, Data Analytics, Linux, DevOps, Cyber Security and Ethical Hacking.<br>
Contact: <a href="mailto:sayyededvantage@gmail.com">sayyededvantage@gmail.com</a> &middot; +91 7977877884</p>

<h2>Data we collect via WhatsApp</h2>
<p>When you message us on WhatsApp we collect your phone number, the messages you send,
and basic delivery metadata. If you share your name, email address, or course interests,
we store those so we can counsel you about our programs.</p>

<h2>How we use it</h2>
<p>We use this data to respond to your queries (including through an AI assistant),
share course information and fees, follow up on admissions, and improve our services.
We do not sell your personal data.</p>

<h2>Sharing</h2>
<p>We share data only with providers needed to operate this service: Meta/WhatsApp
for message delivery and OpenAI for generating AI replies. We do not share your data
with advertisers.</p>

<h2>Retention</h2>
<p>Conversation records are kept while you are an active prospect or student, and
deleted on request.</p>

<h2>Your rights</h2>
<p>You may ask for a copy, correction, or deletion of your data at any time by writing
to <a href="mailto:sayyededvantage@gmail.com">sayyededvantage@gmail.com</a>.
To stop receiving WhatsApp messages from us, simply reply asking us to stop.</p>

<h2>Security</h2>
<p>We apply reasonable safeguards to protect your data. No method of transmission
or storage is completely secure.</p>

<h2>Changes</h2>
<p>We may update this policy from time to time. The current version is always
available at this page.</p>
</body>
</html>
"""


@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy() -> HTMLResponse:
    return HTMLResponse(PRIVACY_HTML)


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_auth)],
)
def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be blank")

    try:
        response = ask_agent(message, session_id=request.session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(session_id=request.session_id, response=response)


@app.delete(
    "/api/chat/{session_id}",
    status_code=204,
    dependencies=[Depends(require_auth)],
)
def reset_chat(
    session_id: str = Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    ),
) -> None:
    clear_memory(session_id)


# ---------------------------------------------------------------------------
# WhatsApp Cloud API webhook.
#
# Meta calls these endpoints directly, so they intentionally do NOT use the
# HTTP Basic Auth above (Meta cannot send custom auth headers). Protection
# comes from the URL itself: configure Meta's callback URL as
#   https://<host>/webhook/<WHATSAPP_VERIFY_TOKEN>
# so only someone who knows the secret token can reach these routes.
# ---------------------------------------------------------------------------

_seen_whatsapp_ids: set[str] = set()


@app.get("/webhook/{path_token}")
def whatsapp_verify(path_token: str, request: Request):
    if not whatsapp.check_path_token(path_token):
        raise HTTPException(status_code=403, detail="Forbidden")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    expected = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    if mode == "subscribe" and expected and secrets.compare_digest(token, expected):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook/{path_token}")
async def whatsapp_incoming(
    path_token: str, request: Request, background_tasks: BackgroundTasks
):
    if not whatsapp.check_path_token(path_token):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not whatsapp.is_configured():
        logger.warning("WhatsApp webhook hit but WHATSAPP_* env vars are not set")
        return {"status": "ignored_not_configured"}
    for sender, text, msg_id in whatsapp.extract_text_messages(payload):
        if msg_id:
            if msg_id in _seen_whatsapp_ids:
                continue  # Meta retried a delivery; don't answer twice.
            _seen_whatsapp_ids.add(msg_id)
            if len(_seen_whatsapp_ids) > 10000:
                _seen_whatsapp_ids.clear()
        # Answer in the background so Meta gets its HTTP 200 immediately.
        background_tasks.add_task(whatsapp.process_incoming, sender, text)
    return {"status": "ok"}
