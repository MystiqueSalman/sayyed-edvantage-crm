"""WhatsApp Cloud API webhook helpers for the Sayyed EdVantage AI agent.

Meta forwards incoming WhatsApp messages to POST /webhook/<verify-token>;
this module parses them, asks the AI agent, and sends the reply back via
the WhatsApp Cloud API.
"""
import logging
import os
import re
import secrets

import requests

from app.ai.agent import ask_agent

logger = logging.getLogger("sayyed_edvantage.whatsapp")

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
# WhatsApp's text limit is 4096 chars; stay safely under it.
MAX_WA_TEXT = 4000

FALLBACK_NO_AI = (
    "Hello! Thanks for reaching out to Sayyed EdVantage. "
    "Our counsellor will get back to you shortly. "
    "You can also call us at +91 7977877884."
)
FALLBACK_ERROR = (
    "Sorry, I'm having a little trouble right now. "
    "Please try again in a bit, or call us at +91 7977877884."
)


def _verify_token() -> str:
    return os.environ.get("WHATSAPP_VERIFY_TOKEN", "")


def _phone_number_id() -> str:
    return os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def _access_token() -> str:
    return os.environ.get("WHATSAPP_TOKEN", "")


def is_configured() -> bool:
    """True when all WhatsApp credentials are present."""
    return bool(_verify_token() and _phone_number_id() and _access_token())


def check_path_token(path_token: str) -> bool:
    """The webhook URL itself carries the verify token as its last segment,
    so only Meta (which was given the full URL) can reach it."""
    expected = _verify_token()
    return bool(expected) and secrets.compare_digest(path_token, expected)


def extract_text_messages(payload: dict) -> list[tuple[str, str, str]]:
    """Pull [(sender, text, message_id)] out of a Cloud API webhook payload."""
    found: list[tuple[str, str, str]] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for msg in value.get("messages", []) or []:
                if msg.get("type") != "text":
                    continue
                text = ((msg.get("text") or {}).get("body") or "").strip()
                sender = msg.get("from", "")
                msg_id = msg.get("id", "")
                if sender and text:
                    found.append((sender, text, msg_id))
    return found


def format_for_whatsapp(text: str) -> str:
    """WhatsApp uses *bold* (single asterisks), not **bold**."""
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    if len(text) > MAX_WA_TEXT:
        text = text[:MAX_WA_TEXT].rstrip() + "…"
    return text


def send_message(to: str, text: str) -> bool:
    """Send a text message via the WhatsApp Cloud API. Never raises."""
    try:
        resp = requests.post(
            f"{GRAPH_BASE}/{_phone_number_id()}/messages",
            headers={
                "Authorization": f"Bearer {_access_token()}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text, "preview_url": False},
            },
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - Meta already got its 200; just log.
        logger.warning("WhatsApp send failed: %s", exc)
        return False


def process_incoming(sender: str, text: str) -> None:
    """Background job: ask the AI agent and reply on WhatsApp."""
    session_id = f"wa:{sender}"
    try:
        reply = ask_agent(text, session_id=session_id)
    except RuntimeError as exc:
        logger.warning("AI not configured, sending fallback: %s", exc)
        reply = FALLBACK_NO_AI
    except Exception:  # noqa: BLE001
        logger.exception("AI agent failed for WhatsApp message")
        reply = FALLBACK_ERROR
    send_message(sender, format_for_whatsapp(reply))
