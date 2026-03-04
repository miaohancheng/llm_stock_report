from __future__ import annotations

import logging
from typing import Iterable

import requests

from app.report.splitter import escape_telegram_markdown, split_text

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        message_thread_id: str | None = None,
        limit: int = 3500,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.limit = limit

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _post(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": escape_telegram_markdown(text),
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        if self.message_thread_id:
            payload["message_thread_id"] = self.message_thread_id

        response = requests.post(url, json=payload, timeout=20)
        if response.status_code >= 400:
            raise RuntimeError(f"Telegram send failed: HTTP {response.status_code} {response.text[:200]}")

        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram send failed: {data}")

    def send_summary(self, title: str, content: str) -> None:
        self._post(f"{title}\n\n{content}")

    def send_detail_for_symbol(self, market_tag: str, symbol: str, detail_markdown: str) -> None:
        chunks = split_text(detail_markdown, self.limit)
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            title = f"[{market_tag}][{symbol}][{idx}/{total}]"
            self._post(f"{title}\n\n{chunk}")

    def send_report(
        self,
        summary_title: str,
        summary_markdown: str,
        market_tag: str,
        detail_blocks: Iterable[tuple[str, str]],
    ) -> None:
        if not self.enabled:
            logger.warning("Telegram is not configured, skip sending")
            return

        self.send_summary(summary_title, summary_markdown)
        for symbol, detail in detail_blocks:
            self.send_detail_for_symbol(market_tag, symbol, detail)
