from __future__ import annotations

import logging
import os
from typing import Any

from app.llm.base import LLMError, RetryConfig, parse_json_text, post_json_with_retry

logger = logging.getLogger(__name__)


class OpenAIClient:
    provider = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 6,
        retry_base_delay_seconds: float = 5.0,
        retry_max_delay_seconds: float = 120.0,
        retry_jitter_seconds: float = 1.0,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.is_openrouter = "openrouter.ai" in self.base_url.lower()
        self.timeout_seconds = 90 if self.is_openrouter else 45
        self.max_tokens = _safe_env_int("LLM_MAX_OUTPUT_TOKENS", 800)
        # OpenRouter compatibility: some routed models are less stable with strict response_format.
        self.use_response_format = _safe_env_bool("OPENAI_USE_RESPONSE_FORMAT", default=not self.is_openrouter)
        self.retry = RetryConfig(
            max_retries=max_retries,
            retry_base_delay_seconds=retry_base_delay_seconds,
            retry_max_delay_seconds=retry_max_delay_seconds,
            retry_jitter_seconds=retry_jitter_seconds,
        )

    def model_id(self) -> str:
        return f"{self.provider}:{self.model}"

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not set")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": self.max_tokens,
        }
        if self.use_response_format:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.is_openrouter:
            referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
            app_title = os.getenv("OPENROUTER_APP_TITLE", "").strip()
            if referer:
                headers["HTTP-Referer"] = referer
            if app_title:
                headers["X-Title"] = app_title

        response = post_json_with_retry(
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
            retry=self.retry,
            provider_name="OpenAI(OpenRouter)" if self.is_openrouter else "OpenAI",
        )
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("Invalid OpenAI response: %s", response.text[:500])
            raise LLMError(f"OpenAI response parsing failed: {exc}") from exc

        try:
            return parse_json_text(content, provider_name="OpenAI")
        except LLMError:
            logger.error("Invalid OpenAI response content: %s", str(content)[:500])
            raise


def _safe_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return max(64, int(value))
    except Exception:
        return default


def _safe_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default
