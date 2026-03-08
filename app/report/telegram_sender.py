from __future__ import annotations

from html import escape
import logging
from typing import Iterable

from app.common.http_retry import HTTPRetryError, request_with_retry
from app.report.splitter import render_telegram_html, split_markdown_for_telegram_html

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
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if self.message_thread_id:
            payload["message_thread_id"] = self.message_thread_id

        try:
            response = request_with_retry(
                method="POST",
                url=url,
                provider_name="telegram",
                timeout_seconds=20,
                json=payload,
            )
        except HTTPRetryError as exc:
            status_text = f"HTTP {exc.status_code} " if exc.status_code is not None else ""
            raise RuntimeError(f"Telegram send failed: {status_text}{exc.detail[:200]}".strip()) from exc

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Telegram send failed: invalid JSON response: {exc}") from exc
        if not data.get("ok"):
            raise RuntimeError(f"Telegram send failed: {data}")

    def send_summary(self, title: str, content: str) -> None:
        summary_html = render_telegram_html(content)
        self._post(f"<b>{escape(title)}</b>\n\n{summary_html}")

    def send_detail_for_symbol(self, market_tag: str, symbol: str, detail_content: str) -> None:
        content_limit = max(200, self.limit - 128)
        chunks = split_markdown_for_telegram_html(detail_content, content_limit)
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            title = f"[{market_tag}][{symbol}][{idx}/{total}]"
            self._post(f"<b>{escape(title)}</b>\n\n{chunk}")

    def send_report(
        self,
        summary_title: str,
        summary_content: str,
        market_tag: str,
        detail_blocks: Iterable[tuple[str, str]],
    ) -> None:
        if not self.enabled:
            logger.warning("Telegram is not configured, skip sending")
            return

        self.send_summary(summary_title, summary_content)
        for symbol, detail in detail_blocks:
            self.send_detail_for_symbol(market_tag, symbol, detail)
