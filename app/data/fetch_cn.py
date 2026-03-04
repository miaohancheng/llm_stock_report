from __future__ import annotations

from datetime import date, timedelta
import logging

import pandas as pd

from app.data.normalize import DataFetchError, normalize_cn_symbol, to_akshare_symbol

logger = logging.getLogger(__name__)


def _to_akshare_prefixed_symbol(normalized: str) -> str:
    prefix = normalized[:2].lower()
    code = normalized[2:]
    return f"{prefix}{code}"


def _to_yfinance_cn_ticker(normalized: str) -> str:
    code = normalized[2:]
    suffix = ".SS" if normalized.startswith("SH") else ".SZ"
    return f"{code}{suffix}"


def _standardize_cn_frame(df: pd.DataFrame, normalized: str, source: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise DataFetchError(f"No CN data returned for {normalized} via {source}")

    frame = df.copy()
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "Date": "date",
        "Open": "open",
        "Close": "close",
        "High": "high",
        "Low": "low",
        "Volume": "volume",
    }
    frame = frame.rename(columns=rename_map)

    if "volume" not in frame.columns and "amount" in frame.columns:
        frame["volume"] = frame["amount"]

    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise DataFetchError(f"Missing columns from CN source {source} for {normalized}: {missing}")

    frame = frame[required].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna().sort_values("date")
    frame["symbol"] = normalized
    if frame.empty:
        raise DataFetchError(f"No usable CN rows for {normalized} via {source}")
    return frame


def fetch_cn_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    try:
        import akshare as ak
    except Exception as exc:  # pragma: no cover - dependency absence tested via behavior
        raise DataFetchError("akshare is not installed") from exc

    normalized = normalize_cn_symbol(symbol)
    raw_code = to_akshare_symbol(normalized)
    errors: list[str] = []

    # Source 1: Eastmoney via AKShare.
    try:
        em_df = ak.stock_zh_a_hist(
            symbol=raw_code,
            period="daily",
            adjust="qfq",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            timeout=25,
        )
        out = _standardize_cn_frame(em_df, normalized, "akshare-eastmoney")
        logger.info("Fetched CN %s rows=%d source=akshare-eastmoney", normalized, len(out))
        return out
    except Exception as exc:
        errors.append(f"akshare-eastmoney:{exc}")
        logger.warning("CN eastmoney failed for %s: %s", normalized, exc)

    # Source 2: Tencent via AKShare.
    tx_symbol = _to_akshare_prefixed_symbol(normalized)
    try:
        tx_df = ak.stock_zh_a_hist_tx(
            symbol=tx_symbol,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            adjust="qfq",
            timeout=25,
        )
        out = _standardize_cn_frame(tx_df, normalized, "akshare-tencent")
        logger.info("Fetched CN %s rows=%d source=akshare-tencent", normalized, len(out))
        return out
    except Exception as exc:
        errors.append(f"akshare-tencent:{exc}")
        logger.warning("CN tencent failed for %s: %s", normalized, exc)

    # Source 3: yfinance (e.g. 600519.SS / 000001.SZ).
    try:
        import yfinance as yf

        ticker = _to_yfinance_cn_ticker(normalized)
        y_df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="column",
        )
        if isinstance(y_df.columns, pd.MultiIndex):
            y_df.columns = [c[0] for c in y_df.columns]
        y_df = y_df.reset_index().rename(columns={"index": "Date"})
        out = _standardize_cn_frame(y_df, normalized, "yfinance")
        logger.info("Fetched CN %s rows=%d source=yfinance", normalized, len(out))
        return out
    except Exception as exc:
        errors.append(f"yfinance:{exc}")
        logger.warning("CN yfinance failed for %s: %s", normalized, exc)

    raise DataFetchError(f"CN fetch failed for {normalized} with all providers: {' | '.join(errors)}")


def fetch_cn_batch(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        result[symbol] = fetch_cn_ohlcv(symbol, start, end)
    return result
