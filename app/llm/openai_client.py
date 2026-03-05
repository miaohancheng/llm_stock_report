from __future__ import annotations

import logging
import os
import time
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
        self.parse_max_retries = _safe_env_int("LLM_PARSE_MAX_RETRIES", 2)
        self.parse_retry_base_delay_seconds = _safe_env_float("LLM_PARSE_RETRY_BASE_DELAY_SECONDS", 2.0)
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

        provider_name = "OpenAI(OpenRouter)" if self.is_openrouter else "OpenAI"
        last_exc: Exception | None = None
        for parse_attempt in range(1, self.parse_max_retries + 1):
            response = post_json_with_retry(
                url=f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                payload=self._build_payload(system_prompt, user_prompt),
                timeout_seconds=self.timeout_seconds,
                retry=self.retry,
                provider_name=provider_name,
            )
            try:
                data = response.json()
                content = _extract_openai_content(data)
            except Exception as exc:
                logger.error("Invalid OpenAI response: %s", response.text[:500])
                last_exc = LLMError(f"OpenAI response parsing failed: {exc}")
            else:
                try:
                    return parse_json_text(content, provider_name="OpenAI")
                except LLMError as exc:
                    last_exc = exc
                    logger.error("Invalid OpenAI response content: %s", str(content)[:500])

            if parse_attempt < self.parse_max_retries:
                delay = self.parse_retry_base_delay_seconds * (2 ** (parse_attempt - 1))
                logger.warning(
                    "%s content parse failed, retrying request %d/%d in %.1fs",
                    provider_name,
                    parse_attempt,
                    self.parse_max_retries,
                    delay,
                )
                time.sleep(delay)

        if last_exc is not None:
            raise LLMError(str(last_exc)) from last_exc
        raise LLMError("OpenAI response parsing failed for unknown reason")

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
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
        return payload

    def _build_headers(self) -> dict[str, str]:
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
        return headers


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


def _safe_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return max(0.0, float(value))
    except Exception:
        return default


def _extract_openai_content(data: dict[str, Any]) -> Any:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError("OpenAI response missing choices")

    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    if not isinstance(message, dict):
        message = {}

    content = message.get("content")
    normalized = _normalize_content(content)
    if normalized:
        return normalized

    text_alt = first.get("text")
    if isinstance(text_alt, str) and text_alt.strip():
        return text_alt.strip()

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            fn = call.get("function")
            if not isinstance(fn, dict):
                continue
            arguments = fn.get("arguments")
            if isinstance(arguments, str) and arguments.strip():
                return arguments.strip()

    return content


def _normalize_content(content: Any) -> str | None:
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if isinstance(content, dict):
        for key in ("text", "content"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                texts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            for key in ("text", "content", "output_text"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
                    break
        merged = "\n".join(texts).strip()
        return merged or None
    return None
