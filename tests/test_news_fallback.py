from __future__ import annotations

import unittest
from unittest.mock import patch

from app.common.schemas import NewsItem
from app.news.aggregator import build_stock_news_queries, search_news_with_fallback


class NewsFallbackTest(unittest.TestCase):
    def test_tavily_to_brave_fallback(self) -> None:
        brave_items = [
            NewsItem(
                title="Brave headline",
                url="https://example.com/1",
                source="example.com",
                snippet="snippet",
            )
        ]

        with patch("app.news.aggregator.search_tavily", side_effect=RuntimeError("tavily down")):
            with patch("app.news.aggregator.search_brave", return_value=brave_items):
                items, provider = search_news_with_fallback(
                    query="AAPL stock latest news",
                    tavily_api_key="t_key",
                    brave_api_key="b_key",
                )

        self.assertEqual("brave", provider)
        self.assertEqual(1, len(items))
        self.assertEqual("Brave headline", items[0].title)

    def test_prioritized_queries_fill_from_next_query(self) -> None:
        tavily_side_effect = [
            [],
            [
                NewsItem(
                    title="Q4 earnings beat",
                    url="https://example.com/earnings",
                    source="example.com",
                    snippet="earnings",
                )
            ],
        ]
        with patch("app.news.aggregator.search_tavily", side_effect=tavily_side_effect), \
            patch("app.news.aggregator.search_brave", return_value=[]):
            items, provider = search_news_with_fallback(
                query=[
                    "AAPL earnings guidance quarterly results",
                    "AAPL stock latest news",
                ],
                tavily_api_key="t_key",
                brave_api_key="b_key",
            )

        self.assertEqual("tavily", provider)
        self.assertEqual(1, len(items))
        self.assertIn("earnings", items[0].title.lower())

    def test_build_stock_news_queries_prioritize_earnings(self) -> None:
        us_queries = build_stock_news_queries("us", "AAPL")
        hk_queries = build_stock_news_queries("hk", "HK00700")
        cn_queries = build_stock_news_queries("cn", "SH600519")

        self.assertTrue(any("earnings" in q.lower() or "10-q" in q.lower() for q in us_queries[:2]))
        self.assertTrue(any("财报" in q or "业绩" in q for q in hk_queries[:2]))
        self.assertTrue(any("财报" in q or "业绩" in q for q in cn_queries[:2]))


if __name__ == "__main__":
    unittest.main()
