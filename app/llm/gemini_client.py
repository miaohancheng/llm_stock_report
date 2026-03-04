from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from app.llm.base import LLMError, RetryConfig, parse_json_text, post_json_with_retry

logger = logging.getLogger(__name__)


class GeminiClient:
    provider = "gemini"

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
            raise LLMError("GEMINI_API_KEY is not set")

        url = f"{self.base_url}/models/{quote(self.model, safe='')}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
        headers = {"Content-Type": "application/json"}

        response = post_json_with_retry(
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=60,
            retry=self.retry,
            provider_name="Gemini",
        )
        try:
            data = response.json()
        except Exception as exc:
            logger.error("Invalid Gemini response: %s", response.text[:500])
            raise LLMError(f"Gemini response parsing failed: {exc}") from exc

        try:
            candidates = data.get("candidates") or []
            parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
            text = ""
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    text = str(part.get("text"))
                    break
            if not text:
                prompt_feedback = data.get("promptFeedback")
                raise LLMError(f"Gemini returned empty content: {prompt_feedback}")
            return parse_json_text(text, provider_name="Gemini")
        except LLMError:
            raise
        except Exception as exc:
            logger.error("Unexpected Gemini payload: %s", str(data)[:500])
            raise LLMError(f"Gemini response parsing failed: {exc}") from exc
