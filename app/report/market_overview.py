from __future__ import annotations

from datetime import date, timedelta
import logging
from statistics import median
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


MARKET_BENCHMARKS: dict[str, list[tuple[str, str]]] = {
    # ticker, display name
    "cn": [
        ("000001.SS", "上证指数"),
        ("399001.SZ", "深证成指"),
        ("399006.SZ", "创业板指"),
    ],
    "us": [
        ("^GSPC", "标普500"),
        ("^IXIC", "纳斯达克"),
        ("^DJI", "道琼斯"),
    ],
    "hk": [
        ("^HSI", "恒生指数"),
        ("^HSCE", "国企指数"),
    ],
}


def market_news_query(market: str) -> str:
    if market == "cn":
        return "A股 大盘 指数 最新消息"
    if market == "us":
        return "US stock market index latest news"
    if market == "hk":
        return "港股 恒生指数 最新消息"
    return f"{market} stock market latest news"


def _normalize_download(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df.index).date,
            "open": pd.to_numeric(df["Open"], errors="coerce"),
            "high": pd.to_numeric(df["High"], errors="coerce"),
            "low": pd.to_numeric(df["Low"], errors="coerce"),
            "close": pd.to_numeric(df["Close"], errors="coerce"),
            "volume": pd.to_numeric(df["Volume"], errors="coerce"),
        }
    )
    out = out.dropna().sort_values("date")
    return out


def fetch_market_benchmarks(market: str, asof_date: date) -> list[dict[str, Any]]:
    benchmarks = MARKET_BENCHMARKS.get(market, [])
    if not benchmarks:
        return []

    start = asof_date - timedelta(days=60)
    end = asof_date + timedelta(days=1)
    results: list[dict[str, Any]] = []
    for ticker, display_name in benchmarks:
        try:
            raw = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="column",
            )
            frame = _normalize_download(raw)
            if frame.empty:
                logger.warning("Benchmark empty: %s %s", market, ticker)
                continue
            closes = frame["close"].tolist()
            latest = float(closes[-1])
            ret_1d = (latest / float(closes[-2]) - 1) if len(closes) >= 2 else 0.0
            ret_5d = (latest / float(closes[-6]) - 1) if len(closes) >= 6 else ret_1d
            ma20 = float(frame["close"].tail(20).mean()) if len(frame) >= 20 else float(frame["close"].mean())
            ma20_ratio = latest / ma20 - 1 if ma20 else 0.0
            results.append(
                {
                    "ticker": ticker,
                    "name": display_name,
                    "latest_close": latest,
                    "ret_1d": ret_1d,
                    "ret_5d": ret_5d,
                    "ma20_ratio": ma20_ratio,
                }
            )
        except Exception as exc:
            logger.warning("Benchmark fetch failed: %s %s %s", market, ticker, exc)
    return results


def _compute_symbol_return(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    if frame is None or frame.empty:
        return None, None
    sorted_frame = frame.sort_values("date")
    closes = sorted_frame["close"].tolist()
    if len(closes) < 2:
        return None, None
    latest = float(closes[-1])
    ret_1d = latest / float(closes[-2]) - 1
    ret_5d = latest / float(closes[-6]) - 1 if len(closes) >= 6 else ret_1d
    return ret_1d, ret_5d


def build_market_snapshot(
    market: str,
    market_data: dict[str, pd.DataFrame],
    asof_date: date,
    market_index_fetch_enabled: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for symbol, frame in market_data.items():
        ret_1d, ret_5d = _compute_symbol_return(frame)
        if ret_1d is None:
            continue
        rows.append({"symbol": symbol, "ret_1d": ret_1d, "ret_5d": ret_5d})

    rets_1d = [r["ret_1d"] for r in rows]
    up = len([x for x in rets_1d if x > 0.0])
    down = len([x for x in rets_1d if x < 0.0])
    flat = len(rets_1d) - up - down

    gainers = sorted(rows, key=lambda x: x["ret_1d"], reverse=True)[:3]
    losers = sorted(rows, key=lambda x: x["ret_1d"])[:3]

    benchmarks = fetch_market_benchmarks(market, asof_date) if market_index_fetch_enabled else []
    return {
        "market": market,
        "asof_date": asof_date.isoformat(),
        "benchmarks": benchmarks,
        "sample_size": len(rows),
        "avg_ret_1d": float(sum(rets_1d) / len(rets_1d)) if rets_1d else 0.0,
        "median_ret_1d": float(median(rets_1d)) if rets_1d else 0.0,
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "gainers": gainers,
        "losers": losers,
    }
