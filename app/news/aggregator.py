from __future__ import annotations

import logging
from typing import Iterable

from app.common.schemas import NewsItem
from app.news.brave_client import search_brave
from app.news.tavily_client import search_tavily

logger = logging.getLogger(__name__)


def build_stock_news_queries(market: str, symbol: str) -> list[str]:
    token = symbol.strip().upper()
    if market == "us":
        return [
            f"{token} earnings guidance quarterly results",
            f"{token} 10-Q 10-K revenue margin outlook",
            f"{token} analyst rating target price",
            f"{token} stock latest news",
        ]
    if market == "hk":
        hk_code = token[2:] if token.startswith("HK") and len(token) == 7 else token
        return [
            f"{token} 财报 业绩 业绩预告 指引",
            f"{hk_code} 港股 财报 业绩 快报 公告",
            f"{token} 研报 评级 目标价",
            f"{token} 股票 最新消息",
        ]
    return [
        f"{token} 财报 业绩 业绩预告 指引",
        f"{token} 年报 季报 公告",
        f"{token} 研报 评级 目标价",
        f"{token} 股票 最新消息",
    ]


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


def _normalize_queries(query: str | Iterable[str]) -> list[str]:
    if isinstance(query, str):
        raw_queries = [query]
    else:
        raw_queries = list(query)
    cleaned = [q.strip() for q in raw_queries if str(q).strip()]
    # Keep order and remove duplicates.
    return list(dict.fromkeys(cleaned))


def _search_single_query(
    query: str,
    tavily_api_key: str | None,
    brave_api_key: str | None,
    max_results: int,
    errors: list[str],
) -> tuple[list[NewsItem], str]:
    if tavily_api_key:
        try:
            items = deduplicate_news(search_tavily(tavily_api_key, query, max_results=max_results), max_results)
            if items:
                return items, "tavily"
        except Exception as exc:
            errors.append(f"tavily:{exc}")
            logger.warning("Tavily search failed for query=%s: %s", query, exc)

    if brave_api_key:
        try:
            items = deduplicate_news(search_brave(brave_api_key, query, max_results=max_results), max_results)
            if items:
                return items, "brave"
        except Exception as exc:
            errors.append(f"brave:{exc}")
            logger.warning("Brave search failed for query=%s: %s", query, exc)

    return [], "none"


def search_news_with_fallback(
    query: str | Iterable[str],
    tavily_api_key: str | None,
    brave_api_key: str | None,
    max_results: int = 5,
) -> tuple[list[NewsItem], str]:
    queries = _normalize_queries(query)
    if not queries:
        return [], "none"

    errors: list[str] = []
    all_items: list[NewsItem] = []
    providers: list[str] = []

    for q in queries:
        remaining = max_results - len(all_items)
        if remaining <= 0:
            break
        items, provider = _search_single_query(
            query=q,
            tavily_api_key=tavily_api_key,
            brave_api_key=brave_api_key,
            max_results=remaining,
            errors=errors,
        )
        if provider != "none":
            providers.append(provider)
        if items:
            all_items = deduplicate_news(all_items + items, max_results=max_results)

    if all_items:
        provider_label = "+".join(list(dict.fromkeys(providers))) if providers else "none"
        logger.info(
            "Search succeeded provider=%s queries=%d items=%d",
            provider_label,
            len(queries),
            len(all_items),
        )
        return all_items, provider_label

    if errors:
        logger.error("Search failed for query=%s errors=%s", " | ".join(queries), ";".join(errors))
    return [], "none"
