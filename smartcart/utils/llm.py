"""
Google Gemini API client wrapper — handles prompt dispatch, JSON response
parsing, retry logic, and structured output validation via Pydantic.
"""

import json
import re
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from config import LLM
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=LLM.api_key)
    return _client


async def call_claude(
    system_prompt: str,
    user_message: str,
    expect_json: bool = True,
) -> dict | str:
    """Dispatch a prompt to Gemini and return the response.

    The function name is kept as call_claude so no callers need to change.
    If expect_json=True, parses the response as JSON. On parse failure,
    retries once with an explicit JSON-only instruction appended.
    """
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=LLM.temperature,
        max_output_tokens=LLM.max_tokens,
    )

    try:
        response_text = await _send(client, config, user_message)

        if not expect_json:
            return response_text

        try:
            return json.loads(_strip_code_fences(response_text))
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON; retrying with explicit instruction")
            retry_message = (
                user_message
                + "\n\nYour previous response was not valid JSON. "
                "Please respond with valid JSON only, no explanation or markdown."
            )
            retry_text = await _send(client, config, retry_message)
            return json.loads(_strip_code_fences(retry_text))

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise


async def _send(
    client: genai.Client,
    config: types.GenerateContentConfig,
    user_message: str,
) -> str:
    response = await client.aio.models.generate_content(
        model=LLM.model,
        contents=user_message,
        config=config,
    )
    return response.text


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that the model sometimes wraps JSON in."""
    text = text.strip()
    text = re.sub(r"^```(?:json|python|yaml)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def parse_llm_json(response_text: str, model_class: type[T]) -> T:
    """Strip code fences, parse JSON, and validate against a Pydantic model."""
    cleaned = _strip_code_fences(response_text)
    data = json.loads(cleaned)
    return model_class.model_validate(data)
