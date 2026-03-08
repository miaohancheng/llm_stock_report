from __future__ import annotations

from dataclasses import dataclass
import logging
import random
import time

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HTTPRetryConfig:
    max_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 10.0
    retry_jitter_seconds: float = 0.5

    def normalized(self) -> HTTPRetryConfig:
        base_delay = max(0.0, float(self.retry_base_delay_seconds))
        max_delay = max(base_delay, float(self.retry_max_delay_seconds))
        return HTTPRetryConfig(
            max_retries=max(1, int(self.max_retries)),
            retry_base_delay_seconds=base_delay,
            retry_max_delay_seconds=max_delay,
            retry_jitter_seconds=max(0.0, float(self.retry_jitter_seconds)),
        )


DEFAULT_HTTP_RETRY = HTTPRetryConfig()
RETRYABLE_STATUS_CODES = {408, 409, 429}


class HTTPRetryError(RuntimeError):
    def __init__(
        self,
        provider_name: str,
        *,
        status_code: int | None = None,
        detail: str = "",
    ) -> None:
        self.provider_name = provider_name
        self.status_code = status_code
        self.detail = detail
        status_text = f" HTTP {status_code}" if status_code is not None else ""
        suffix = f": {detail}" if detail else ""
        super().__init__(f"{provider_name}{status_text}{suffix}")


def request_with_retry(
    *,
    method: str,
    url: str,
    provider_name: str,
    timeout_seconds: float,
    retry: HTTPRetryConfig = DEFAULT_HTTP_RETRY,
    **request_kwargs,
) -> requests.Response:
    retry = retry.normalized()
    method_upper = method.upper()
    last_error: Exception | None = None

    for attempt in range(1, retry.max_retries + 1):
        try:
            response = requests.request(method_upper, url, timeout=timeout_seconds, **request_kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt >= retry.max_retries:
                break
            delay = _calc_delay(retry, attempt)
            logger.warning(
                "%s %s transient network error, retry %d/%d in %.1fs: %s",
                provider_name,
                method_upper,
                attempt,
                retry.max_retries,
                delay,
                exc,
            )
            time.sleep(delay)
            continue

        if response.status_code < 400:
            if attempt > 1:
                logger.info(
                    "%s %s succeeded after retry %d/%d",
                    provider_name,
                    method_upper,
                    attempt,
                    retry.max_retries,
                )
            return response

        detail = response.text[:300]
        if _is_retryable_status(response.status_code) and attempt < retry.max_retries:
            delay = _calc_delay(retry, attempt)
            logger.warning(
                "%s %s HTTP %d, retry %d/%d in %.1fs: %s",
                provider_name,
                method_upper,
                response.status_code,
                attempt,
                retry.max_retries,
                delay,
                detail[:200],
            )
            time.sleep(delay)
            continue

        raise HTTPRetryError(provider_name, status_code=response.status_code, detail=detail)

    raise HTTPRetryError(provider_name, detail=str(last_error or "request failed after retries"))


def _calc_delay(retry: HTTPRetryConfig, attempt: int) -> float:
    base = retry.retry_base_delay_seconds * (2 ** max(0, attempt - 1))
    delay = min(retry.retry_max_delay_seconds, base)
    delay += random.uniform(0.0, retry.retry_jitter_seconds)
    return delay


def _is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES or 500 <= status_code <= 599
