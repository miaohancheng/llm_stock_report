from __future__ import annotations

from datetime import date, timedelta
import logging

import pandas as pd
import yfinance as yf

from app.data.normalize import DataFetchError, normalize_us_symbol

logger = logging.getLogger(__name__)


def fetch_us_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    ticker = normalize_us_symbol(symbol)

    # yfinance end is exclusive; add one day for inclusive date behavior.
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
        raise DataFetchError(f"yfinance request failed for {ticker}: {exc}") from exc

    if df is None or df.empty:
        raise DataFetchError(f"No US data returned for {ticker}")

    # Newer yfinance may return MultiIndex with ticker level.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataFetchError(f"Missing columns from yfinance for {ticker}: {missing}")

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
    out["symbol"] = ticker
    logger.info("Fetched US %s rows=%d", ticker, len(out))
    return out


def fetch_us_batch(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        result[symbol] = fetch_us_ohlcv(symbol, start, end)
    return result
