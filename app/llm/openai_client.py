from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class OpenAIClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not set")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code >= 400:
            raise LLMError(f"OpenAI request failed: HTTP {response.status_code} {response.text[:300]}")

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:
            logger.error("Invalid OpenAI response: %s", response.text[:500])
            raise LLMError(f"OpenAI response parsing failed: {exc}") from exc
