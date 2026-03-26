"""Groq API client — free LLM tier with rate limit tracking."""

import json
import logging
import re
import time
from datetime import date

from groq import Groq

logger = logging.getLogger(__name__)


def safe_parse_json(text: str, fallback: dict | None = None) -> dict | None:
    """Parse JSON from LLM output using multiple strategies."""
    if not text:
        return fallback

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return fallback


class GroqClient:
    """Wrapper around the Groq API (free Llama models)."""

    def __init__(self, api_key: str, daily_limit: int = 14400):
        self.client = Groq(api_key=api_key)
        self.daily_limit = daily_limit
        self._request_count = 0
        self._count_date = date.today()
        self._total_tokens = 0

    def _check_rate_limit(self):
        today = date.today()
        if today != self._count_date:
            self._request_count = 0
            self._count_date = today
        if self._request_count >= self.daily_limit:
            raise RuntimeError(
                f"Groq daily limit reached ({self.daily_limit}). "
                "Try again tomorrow or use a local model."
            )

    def complete(
        self,
        prompt: str,
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 1024,
        system_prompt: str = "",
        temperature: float = 0.7,
    ) -> str:
        self._check_rate_limit()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self._request_count += 1
                usage = response.usage
                if usage:
                    self._total_tokens += (usage.prompt_tokens or 0) + (
                        usage.completion_tokens or 0
                    )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == 2:
                    raise
                wait = 2**attempt
                logger.warning("Groq error (%s), retrying in %ds...", e, wait)
                time.sleep(wait)

        raise RuntimeError("Groq API failed after 3 retries")

    def complete_json(
        self,
        prompt: str,
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 2048,
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> dict:
        if "JSON" not in system_prompt and "json" not in prompt.lower():
            prompt += "\n\nRespond with valid JSON only, no other text."

        text = self.complete(prompt, model, max_tokens, system_prompt, temperature)
        result = safe_parse_json(text)
        if result is None:
            logger.error("Failed to parse JSON from Groq response")
            raise ValueError("Groq returned unparseable JSON")
        return result

    @property
    def requests_remaining(self) -> int:
        if date.today() != self._count_date:
            return self.daily_limit
        return max(0, self.daily_limit - self._request_count)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens
