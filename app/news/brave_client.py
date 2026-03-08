from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.common.http_retry import request_with_retry
from app.common.schemas import NewsItem

logger = logging.getLogger(__name__)


def search_brave(api_key: str, query: str, max_results: int = 5) -> list[NewsItem]:
    if not api_key:
        raise ValueError("Brave API key is required")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": min(max_results, 20),
        "freshness": "pw",
    }

    response = request_with_retry(
        method="GET",
        url=url,
        provider_name="brave",
        timeout_seconds=20,
        headers=headers,
        params=params,
    )
    data = response.json()

    raw_results = data.get("web", {}).get("results", [])
    items: list[NewsItem] = []
    for item in raw_results:
        raw_url = str(item.get("url", "")).strip()
        domain = urlparse(raw_url).netloc.replace("www.", "") or "unknown"
        items.append(
            NewsItem(
                title=str(item.get("title", "")).strip(),
                url=raw_url,
                source=domain,
                snippet=str(item.get("description", "")).strip(),
                published_at=item.get("age"),
            )
        )
    logger.info("Brave returned %d items for query=%s", len(items), query)
    return items
