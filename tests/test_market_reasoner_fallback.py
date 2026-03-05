from __future__ import annotations

import unittest

from app.common.schemas import NewsItem
from app.llm.base import LLMError
from app.llm.report_reasoner import generate_market_narrative


class _FailLLM:
    provider = "openai"
    model = "dummy"

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        raise LLMError("OpenAI returned empty response body")


class MarketReasonerFallbackTest(unittest.TestCase):
    def test_market_llm_failure_uses_template_zh(self) -> None:
        snapshot = {
            "market": "cn",
            "asof_date": "2026-03-05",
            "benchmarks": [
                {"ticker": "000001.SS", "name": "上证指数", "latest_close": 3012.5, "ret_1d": -0.006, "ret_5d": -0.01}
            ],
            "sample_size": 30,
            "avg_ret_1d": -0.004,
            "median_ret_1d": -0.003,
            "up_count": 9,
            "down_count": 18,
            "flat_count": 3,
            "gainers": [],
            "losers": [],
        }
        news = [
            NewsItem(title="A股量能回落", url="https://example.com/a", source="x", snippet="s"),
            NewsItem(title="北向资金净流出", url="https://example.com/b", source="x", snippet="s"),
        ]
        out = generate_market_narrative(
            llm_client=_FailLLM(),
            market="cn",
            asof_date="2026-03-05",
            market_snapshot=snapshot,
            news_items=news,
            provider_used="tavily",
            language="zh",
        )

        self.assertIn("模板复盘兜底", out.summary)
        self.assertIn("市场快照", out.details)
        self.assertIn("后市观察点", out.details)
        self.assertTrue(out.used_provider.endswith("+template"))
        self.assertEqual(2, len(out.news_items))

    def test_market_llm_failure_uses_template_en(self) -> None:
        snapshot = {
            "market": "us",
            "asof_date": "2026-03-05",
            "benchmarks": [
                {"ticker": "^GSPC", "name": "S&P 500", "latest_close": 5200.2, "ret_1d": 0.004, "ret_5d": -0.002}
            ],
            "sample_size": 20,
            "avg_ret_1d": 0.003,
            "median_ret_1d": 0.002,
            "up_count": 12,
            "down_count": 6,
            "flat_count": 2,
            "gainers": [],
            "losers": [],
        }
        out = generate_market_narrative(
            llm_client=_FailLLM(),
            market="us",
            asof_date="2026-03-05",
            market_snapshot=snapshot,
            news_items=[],
            provider_used="tavily",
            language="en",
        )

        self.assertIn("deterministic fallback", out.summary.lower())
        self.assertIn("Market Snapshot", out.details)
        self.assertIn("Next-session Watchpoints", out.details)
        self.assertTrue(out.used_provider.endswith("+template"))


if __name__ == "__main__":
    unittest.main()
