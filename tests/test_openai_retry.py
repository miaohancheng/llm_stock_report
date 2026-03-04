from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.llm.openai_client import OpenAIClient


class _Resp:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload)
        self.headers = {}

    def json(self):
        return self._payload


class OpenAIRetryTest(unittest.TestCase):
    def test_retry_on_429_then_success(self) -> None:
        calls = {"n": 0}

        def fake_post(url, headers, json, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                resp = _Resp(429, {"error": {"message": "rate limit"}}, text='{"error":"rate"}')
                resp.headers = {"Retry-After": "0"}
                return resp
            return _Resp(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"summary":"ok","details":"ok","risk_points":[],"action_bias":"中性","confidence":50,"evidence_used":[],"reliability_notes":[]}'
                            }
                        }
                    ]
                },
            )

        client = OpenAIClient(
            api_key="k",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            max_retries=3,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            retry_jitter_seconds=0,
        )

        with patch("app.llm.base.requests.post", side_effect=fake_post):
            result = client.chat_json("sys", "user")

        self.assertEqual(2, calls["n"])
        self.assertEqual("ok", result["summary"])


if __name__ == "__main__":
    unittest.main()
