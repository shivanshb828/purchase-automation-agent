"""
Anthropic Claude API client wrapper — handles prompt dispatch, JSON response
parsing, retry logic, and structured output validation via Pydantic.
"""

import json
import re
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from config import LLM
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


async def call_claude(
    system_prompt: str,
    user_message: str,
    expect_json: bool = True,
) -> dict | str:
    """Dispatch a prompt to Claude and return the response.

    If expect_json=True, parses the response as JSON. On parse failure,
    retries once with an explicit JSON-only instruction appended.
    """
    client = anthropic.AsyncAnthropic(api_key=LLM.api_key)

    try:
        response_text = await _send(client, system_prompt, user_message)

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
            retry_text = await _send(client, system_prompt, retry_message)
            return json.loads(_strip_code_fences(retry_text))

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        raise


async def _send(
    client: anthropic.AsyncAnthropic,
    system_prompt: str,
    user_message: str,
) -> str:
    message = await client.messages.create(
        model=LLM.model,
        max_tokens=LLM.max_tokens,
        temperature=LLM.temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that Claude sometimes wraps JSON in."""
    text = text.strip()
    text = re.sub(r"^```(?:json|python|yaml)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def parse_llm_json(response_text: str, model_class: type[T]) -> T:
    """Strip code fences, parse JSON, and validate against a Pydantic model."""
    cleaned = _strip_code_fences(response_text)
    data = json.loads(cleaned)
    return model_class.model_validate(data)
