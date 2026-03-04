from __future__ import annotations

from datetime import date, timedelta
import logging

import pandas as pd
import yfinance as yf

from app.data.normalize import DataFetchError, normalize_hk_symbol, to_yfinance_hk_ticker

logger = logging.getLogger(__name__)


def _build_hk_ticker_candidates(normalized_symbol: str) -> list[str]:
    raw = normalized_symbol[2:]
    candidates = [to_yfinance_hk_ticker(normalized_symbol), f"{raw}.HK"]
    try:
        n = int(raw)
        candidates.append(f"{n:04d}.HK")
        candidates.append(f"{n}.HK")
    except ValueError:
        pass

    deduped: list[str] = []
    seen = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def _download_hk_ticker(ticker: str, start: date, end_inclusive: date) -> pd.DataFrame:
    return yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end_inclusive.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
    )


def fetch_hk_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    normalized = normalize_hk_symbol(symbol)
    end_inclusive = end + timedelta(days=1)
    candidates = _build_hk_ticker_candidates(normalized)

    df = None
    last_error: Exception | None = None
    used_ticker: str | None = None
    for ticker in candidates:
        try:
            candidate_df = _download_hk_ticker(ticker, start, end_inclusive)
        except Exception as exc:
            last_error = exc
            logger.warning("HK ticker download failed %s -> %s: %s", normalized, ticker, exc)
            continue
        if candidate_df is not None and not candidate_df.empty:
            df = candidate_df
            used_ticker = ticker
            break
        logger.warning("HK ticker returned empty %s -> %s", normalized, ticker)

    if df is None or df.empty:
        detail = str(last_error) if last_error else "empty response"
        # Prefix NON_RETRYABLE so retry layer can stop on invalid/delisted symbols.
        raise DataFetchError(
            f"NON_RETRYABLE: No HK data returned for {normalized} (tried {candidates}) detail={detail}"
        )

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
    logger.info("Fetched HK %s rows=%d ticker=%s", normalized, len(out), used_ticker)
    return out


def fetch_hk_batch(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        result[symbol] = fetch_hk_ohlcv(symbol, start, end)
    return result
