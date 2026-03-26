"""AI model router — routes tasks to cheap (8B) or quality (70B) Groq models."""

import logging
import os

from src.ai.groq_client import GroqClient

logger = logging.getLogger(__name__)

# Token limits per task type
MAX_TOKENS_PER_TASK = {
    "compliance_check": 512,
    "medicine_classify": 512,
    "edge_case": 1024,
    "report_narrative": 2048,
}
MAX_TOKENS_ABSOLUTE = 4096

# Task → model tier mapping
TASK_TIERS = {
    "compliance_check": "cheap",  # Llama 3.1 8B — fast classification
    "medicine_classify": "cheap",
    "edge_case": "quality",  # Llama 3.3 70B — needs reasoning
    "report_narrative": "quality",
}

MODEL_MAP = {
    "cheap": "llama-3.1-8b-instant",
    "quality": "llama-3.3-70b-versatile",
}


class AIRouter:
    """Routes AI requests to cheap or quality Groq models based on task."""

    def __init__(self, config: dict | None = None):
        if config is None:
            config = {}
        ai_config = config.get("ai", {})
        groq_config = ai_config.get("groq", {})

        api_key = groq_config.get("api_key") or os.getenv("GROQ_API_KEY", "")
        daily_limit = groq_config.get("daily_limit", 14400)

        self.groq: GroqClient | None = None
        if api_key:
            self.groq = GroqClient(api_key=api_key, daily_limit=daily_limit)

        routing = ai_config.get("routing", {})
        self.task_routing = {**TASK_TIERS, **routing}

    def _get_model(self, task: str) -> str:
        tier = self.task_routing.get(task, "cheap")
        return MODEL_MAP.get(tier, MODEL_MAP["cheap"])

    def _cap_tokens(self, task: str, requested: int) -> int:
        task_cap = MAX_TOKENS_PER_TASK.get(task, MAX_TOKENS_ABSOLUTE)
        return min(requested, task_cap, MAX_TOKENS_ABSOLUTE)

    def route(
        self,
        task: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        if not self.groq:
            raise RuntimeError("No AI provider configured. Set GROQ_API_KEY.")

        model = self._get_model(task)
        max_tokens = self._cap_tokens(task, max_tokens)

        result = self.groq.complete(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        logger.info("AI [%s] Groq/%s: OK", task, model)
        return result

    def route_json(
        self,
        task: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict:
        if not self.groq:
            raise RuntimeError("No AI provider configured. Set GROQ_API_KEY.")

        model = self._get_model(task)
        max_tokens = self._cap_tokens(task, max_tokens)

        result = self.groq.complete_json(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        logger.info("AI JSON [%s] Groq/%s: OK", task, model)
        return result

    @property
    def status(self) -> dict:
        return {
            "provider": "groq",
            "requests_remaining": self.groq.requests_remaining if self.groq else 0,
            "total_tokens": self.groq.total_tokens if self.groq else 0,
            "available": self.groq is not None,
        }
