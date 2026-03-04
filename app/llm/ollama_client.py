from __future__ import annotations

import logging
from typing import Any

from app.llm.base import LLMError, RetryConfig, parse_json_text, post_json_with_retry

logger = logging.getLogger(__name__)


class OllamaClient:
    provider = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        max_retries: int = 6,
        retry_base_delay_seconds: float = 5.0,
        retry_max_delay_seconds: float = 120.0,
        retry_jitter_seconds: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = (api_key or "").strip()
        self.retry = RetryConfig(
            max_retries=max_retries,
            retry_base_delay_seconds=retry_base_delay_seconds,
            retry_max_delay_seconds=retry_max_delay_seconds,
            retry_jitter_seconds=retry_jitter_seconds,
        )

    def model_id(self) -> str:
        return f"{self.provider}:{self.model}"

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.3},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = post_json_with_retry(
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=90,
            retry=self.retry,
            provider_name="Ollama",
        )
        try:
            data = response.json()
        except Exception as exc:
            logger.error("Invalid Ollama response: %s", response.text[:500])
            raise LLMError(f"Ollama response parsing failed: {exc}") from exc

        raw_content = ""
        message = data.get("message")
        if isinstance(message, dict) and message.get("content"):
            raw_content = str(message.get("content"))
        elif data.get("response"):
            raw_content = str(data.get("response"))

        if not raw_content:
            raise LLMError(f"Ollama returned empty content: {str(data)[:200]}")
        return parse_json_text(raw_content, provider_name="Ollama")
