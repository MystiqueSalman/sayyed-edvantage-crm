import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client: OpenAI | None = None


def _get_client() -> OpenAI:
    global client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    if client is None:
        client = OpenAI(api_key=api_key)

    return client


def ask_ai(prompt: str) -> str:
    response = _get_client().responses.create(
        model="gpt-5.6",
        input=prompt,
    )

    return response.output_text