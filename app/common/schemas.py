from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    snippet: str
    published_at: str | None = None


@dataclass
class PredictionRecord:
    market: str
    symbol: str
    asof_date: str
    score: float
    rank: int
    side: str
    pred_return: float
    model_version: str
    data_window_start: str
    data_window_end: str

    def to_csv_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StockNarrative:
    symbol: str
    summary: str
    details: str
    used_provider: str
    news_items: list[NewsItem] = field(default_factory=list)
    decision: str = "观望"
    trend: str = "震荡"
    urgency: str = "中"
    confidence: int = 50
    risk_points: list[str] = field(default_factory=list)
    catalysts: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    reliability_notes: list[str] = field(default_factory=list)
    latest_close: float | None = None
    feature_snapshot: dict[str, float] = field(default_factory=dict)


@dataclass
class MarketNarrative:
    market: str
    summary: str
    details: str
    used_provider: str
    news_items: list[NewsItem] = field(default_factory=list)


@dataclass
class RunMeta:
    run_id: str
    market: str
    status: str
    total_symbols: int
    success_symbols: int
    failed_symbols: int
    failed_list: list[str]
    model_version: str
    llm_model: str
    search_provider_primary: str
    search_provider_fallback: str
    start_time: str
    end_time: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
