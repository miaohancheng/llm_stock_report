from __future__ import annotations

import logging

from app.common.schemas import NewsItem
from app.news.brave_client import search_brave
from app.news.tavily_client import search_tavily

logger = logging.getLogger(__name__)


def deduplicate_news(items: list[NewsItem], max_results: int = 5) -> list[NewsItem]:
    deduped: list[NewsItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.url.strip().lower(), item.title.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max_results:
            break
    return deduped


def search_news_with_fallback(
    query: str,
    tavily_api_key: str | None,
    brave_api_key: str | None,
    max_results: int = 5,
) -> tuple[list[NewsItem], str]:
    errors: list[str] = []

    if tavily_api_key:
        try:
            items = deduplicate_news(search_tavily(tavily_api_key, query, max_results=max_results), max_results)
            if items:
                return items, "tavily"
        except Exception as exc:
            errors.append(f"tavily:{exc}")
            logger.warning("Tavily search failed: %s", exc)

    if brave_api_key:
        try:
            items = deduplicate_news(search_brave(brave_api_key, query, max_results=max_results), max_results)
            if items:
                return items, "brave"
        except Exception as exc:
            errors.append(f"brave:{exc}")
            logger.warning("Brave search failed: %s", exc)

    if errors:
        logger.error("Search failed for query=%s errors=%s", query, ";".join(errors))
    return [], "none"
