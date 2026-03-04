from __future__ import annotations

import unittest
from unittest.mock import patch

from app.common.schemas import NewsItem
from app.news.aggregator import search_news_with_fallback


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


if __name__ == "__main__":
    unittest.main()
