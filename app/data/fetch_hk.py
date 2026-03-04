from __future__ import annotations

from datetime import date, timedelta
import logging

import pandas as pd
import yfinance as yf

from app.data.normalize import DataFetchError, normalize_hk_symbol, to_yfinance_hk_ticker

logger = logging.getLogger(__name__)


def fetch_hk_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    normalized = normalize_hk_symbol(symbol)
    ticker = to_yfinance_hk_ticker(normalized)
    end_inclusive = end + timedelta(days=1)

    try:
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end_inclusive.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="column",
        )
    except Exception as exc:
        raise DataFetchError(f"yfinance HK request failed for {normalized}: {exc}") from exc

    if df is None or df.empty:
        raise DataFetchError(f"No HK data returned for {normalized}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataFetchError(f"Missing columns from yfinance HK for {normalized}: {missing}")

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
    out["symbol"] = normalized
    logger.info("Fetched HK %s rows=%d", normalized, len(out))
    return out


def fetch_hk_batch(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        result[symbol] = fetch_hk_ohlcv(symbol, start, end)
    return result
