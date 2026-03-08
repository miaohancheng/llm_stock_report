from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from app.news.aggregator import search_news_with_fallback
from app.report.telegram_sender import TelegramSender


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict:
        return self._payload


class HTTPRetryTest(unittest.TestCase):
    def test_tavily_rate_limit_retries_then_stays_primary(self) -> None:
        responses = [
            _FakeResponse(429, {}, "rate limited"),
            _FakeResponse(
                200,
                {
                    "results": [
                        {
                            "title": "AAPL earnings beat",
                            "url": "https://example.com/aapl",
                            "content": "earnings",
                            "published_date": "2026-03-08",
                        }
                    ]
                },
            ),
        ]

        with patch("app.common.http_retry.requests.request", side_effect=lambda *args, **kwargs: responses.pop(0)) as request_mock, \
            patch("app.common.http_retry.time.sleep", return_value=None):
            items, provider = search_news_with_fallback(
                query="AAPL earnings guidance quarterly results",
                tavily_api_key="t_key",
                brave_api_key="b_key",
            )

        self.assertEqual("tavily", provider)
        self.assertEqual(1, len(items))
        self.assertEqual(2, request_mock.call_count)

    def test_tavily_exhausts_then_brave_succeeds(self) -> None:
        responses = [
            _FakeResponse(500, {}, "upstream error"),
            _FakeResponse(500, {}, "upstream error"),
            _FakeResponse(500, {}, "upstream error"),
            _FakeResponse(
                200,
                {
                    "web": {
                        "results": [
                            {
                                "title": "Brave headline",
                                "url": "https://example.com/brave",
                                "description": "snippet",
                                "age": "1d",
                            }
                        ]
                    }
                },
            ),
        ]

        with patch("app.common.http_retry.requests.request", side_effect=lambda *args, **kwargs: responses.pop(0)) as request_mock, \
            patch("app.common.http_retry.time.sleep", return_value=None):
            items, provider = search_news_with_fallback(
                query="AAPL stock latest news",
                tavily_api_key="t_key",
                brave_api_key="b_key",
            )

        self.assertEqual("brave", provider)
        self.assertEqual(1, len(items))
        self.assertEqual(4, request_mock.call_count)

    def test_telegram_sender_retries_timeouts(self) -> None:
        sender = TelegramSender(bot_token="token", chat_id="chat")
        side_effects = [
            requests.exceptions.Timeout("timeout"),
            requests.exceptions.Timeout("timeout"),
            _FakeResponse(200, {"ok": True}),
        ]
        
        def fake_request(*args, **kwargs):
            outcome = side_effects.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch("app.common.http_retry.requests.request", side_effect=fake_request) as request_mock, \
            patch("app.common.http_retry.time.sleep", return_value=None):
            sender.send_summary("[US] 2026-03-08 Daily Summary", "# test")

        self.assertEqual(3, request_mock.call_count)


if __name__ == "__main__":
    unittest.main()
