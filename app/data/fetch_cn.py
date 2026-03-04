from __future__ import annotations

from datetime import date
import logging

import pandas as pd

from app.data.normalize import DataFetchError, normalize_cn_symbol, to_akshare_symbol

logger = logging.getLogger(__name__)


def fetch_cn_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    try:
        import akshare as ak
    except Exception as exc:  # pragma: no cover - dependency absence tested via behavior
        raise DataFetchError("akshare is not installed") from exc

    normalized = normalize_cn_symbol(symbol)
    raw_code = to_akshare_symbol(normalized)

    try:
        df = ak.stock_zh_a_hist(
            symbol=raw_code,
            period="daily",
            adjust="qfq",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
    except Exception as exc:
        raise DataFetchError(f"AKShare request failed for {normalized}: {exc}") from exc

    if df is None or df.empty:
        raise DataFetchError(f"No CN data returned for {normalized}")

    columns = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
    }
    df = df.rename(columns=columns)
    missing = [c for c in columns.values() if c not in df.columns]
    if missing:
        raise DataFetchError(f"Missing columns from AKShare for {normalized}: {missing}")

    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().sort_values("date")
    df["symbol"] = normalized
    logger.info("Fetched CN %s rows=%d", normalized, len(df))
    return df


def fetch_cn_batch(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        result[symbol] = fetch_cn_ohlcv(symbol, start, end)
    return result
