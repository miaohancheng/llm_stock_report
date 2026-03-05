from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Protocol

import requests

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    provider: str
    model: str

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...

    def model_id(self) -> str:
        ...


@dataclass
class RetryConfig:
    max_retries: int = 6
    retry_base_delay_seconds: float = 5.0
    retry_max_delay_seconds: float = 120.0
    retry_jitter_seconds: float = 1.0

    def normalized(self) -> RetryConfig:
        return RetryConfig(
            max_retries=max(1, int(self.max_retries)),
            retry_base_delay_seconds=max(0.0, float(self.retry_base_delay_seconds)),
            retry_max_delay_seconds=max(
                max(0.0, float(self.retry_base_delay_seconds)),
                float(self.retry_max_delay_seconds),
            ),
            retry_jitter_seconds=max(0.0, float(self.retry_jitter_seconds)),
        )


def _calc_delay(retry: RetryConfig, attempt: int) -> float:
    base = retry.retry_base_delay_seconds * (2 ** max(0, attempt - 1))
    delay = min(retry.retry_max_delay_seconds, base)
    delay += random.uniform(0.0, retry.retry_jitter_seconds)
    return delay


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code in {408, 409} or 500 <= status_code <= 599


def _is_retryable_400_text(body_text: str) -> bool:
    text = (body_text or "").strip().lower()
    if not text:
        return False
    retryable_markers = (
        "timeout",
        "timed out",
        "rate limit",
        "rate-limited",
        "temporarily rate-limited",
        "upstream connect error",
        "disconnect/reset before headers",
        "server overloaded",
        "overflow",
        "please retry",
        "retry shortly",
        "try again",
    )
    return any(marker in text for marker in retryable_markers)


def _is_retryable_response(status_code: int, body_text: str) -> bool:
    if _is_retryable_status(status_code):
        return True
    if status_code == 400 and _is_retryable_400_text(body_text):
        return True
    return False


def _parse_retry_after_seconds(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        value = float(text)
        return max(0.0, value)
    except Exception:
        return None


def post_json_with_retry(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
    retry: RetryConfig,
    provider_name: str,
) -> requests.Response:
    retry = retry.normalized()
    last_error: Exception | None = None

    for attempt in range(1, retry.max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt >= retry.max_retries:
                break
            delay = _calc_delay(retry, attempt)
            logger.warning(
                "%s transient network error, retry %d/%d in %.1fs: %s",
                provider_name,
                attempt,
                retry.max_retries,
                delay,
                exc,
            )
            time.sleep(delay)
            continue

        if response.status_code >= 400:
            response_text = response.text[:3000]
            retryable = _is_retryable_response(response.status_code, response_text)
            if attempt < retry.max_retries and retryable:
                retry_after = _parse_retry_after_seconds(response.headers.get("Retry-After"))
                if retry_after is not None:
                    delay = min(retry_after, retry.retry_max_delay_seconds)
                else:
                    delay = _calc_delay(retry, attempt)
                logger.warning(
                    "%s rate/server limit HTTP %d, retry %d/%d in %.1fs: %s",
                    provider_name,
                    response.status_code,
                    attempt,
                    retry.max_retries,
                    delay,
                    response_text[:200],
                )
                time.sleep(delay)
                continue

            if retryable:
                raise LLMError(
                    f"{provider_name} request failed after {retry.max_retries} attempts: "
                    f"HTTP {response.status_code} {response_text[:300]}"
                )
            raise LLMError(f"{provider_name} request failed: HTTP {response.status_code} {response_text[:300]}")

        return response

    raise LLMError(f"{provider_name} request failed after retries: {last_error}")


def parse_json_text(raw_text: Any, *, provider_name: str) -> dict[str, Any]:
    if isinstance(raw_text, str):
        text = raw_text.strip()
    elif raw_text is None:
        text = ""
    else:
        text = str(raw_text).strip()
    if not text:
        raise LLMError(f"{provider_name} returned empty response body")

    candidates = [text]
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            candidates.append("\n".join(lines[1:-1]).strip())

    left = text.find("{")
    right = text.rfind("}")
    if left >= 0 and right > left:
        candidates.append(text[left : right + 1].strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise ValueError("JSON root must be object")
            return parsed
        except Exception:
            continue

    raise LLMError(f"{provider_name} response is not valid JSON: {text[:300]}")
