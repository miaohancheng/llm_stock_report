from __future__ import annotations

import logging
from typing import Iterable

from app.common.http_retry import request_with_retry
from app.common.schemas import NewsItem

logger = logging.getLogger(__name__)


def search_tavily(api_key: str, query: str, max_results: int = 5) -> list[NewsItem]:
    if not api_key:
        raise ValueError("Tavily API key is required")

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }
    response = request_with_retry(
        method="POST",
        url=url,
        provider_name="tavily",
        timeout_seconds=20,
        json=payload,
    )
    data = response.json()

    results: Iterable[dict] = data.get("results", [])
    items: list[NewsItem] = []
    for item in results:
        items.append(
            NewsItem(
                title=str(item.get("title", "")).strip(),
                url=str(item.get("url", "")).strip(),
                source="tavily",
                snippet=str(item.get("content", "")).strip(),
                published_at=item.get("published_date"),
            )
        )
    logger.info("Tavily returned %d items for query=%s", len(items), query)
    return items
