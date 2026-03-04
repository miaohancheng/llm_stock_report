from __future__ import annotations

import unittest
from unittest.mock import patch

from app.llm.gemini_client import GeminiClient
from app.llm.ollama_client import OllamaClient


class _Resp:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)
        self.headers = {}

    def json(self):
        return self._payload


class LLMClientsTest(unittest.TestCase):
    def test_gemini_client_parse_json(self) -> None:
        def fake_post(url, headers, json, timeout):
            return _Resp(
                200,
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": '{"summary":"ok","details":"d","risk_points":[],"action_bias":"中性","confidence":50,"evidence_used":[],"reliability_notes":[]}'
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        client = GeminiClient(
            api_key="g",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.0-flash",
            max_retries=1,
        )

        with patch("app.llm.base.requests.post", side_effect=fake_post):
            result = client.chat_json("sys", "user")

        self.assertEqual("ok", result["summary"])

    def test_ollama_client_parse_json(self) -> None:
        def fake_post(url, headers, json, timeout):
            return _Resp(
                200,
                {
                    "message": {
                        "content": '{"summary":"ok","details":"d","risk_points":[],"action_bias":"中性","confidence":50,"evidence_used":[],"reliability_notes":[]}'
                    }
                },
            )

        client = OllamaClient(
            base_url="http://127.0.0.1:11434",
            model="qwen2.5:7b",
            max_retries=1,
        )

        with patch("app.llm.base.requests.post", side_effect=fake_post):
            result = client.chat_json("sys", "user")

        self.assertEqual("ok", result["summary"])


if __name__ == "__main__":
    unittest.main()
