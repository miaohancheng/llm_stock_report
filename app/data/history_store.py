from __future__ import annotations

from datetime import date, timedelta
import logging
from pathlib import Path
import random
import time
from typing import Callable

import pandas as pd

from app.common.config import AppConfig
from app.data.normalize import DataFetchError

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume", "symbol"]


def _history_root(cfg: AppConfig) -> Path:
    root = cfg.qlib_data_root / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _history_path(cfg: AppConfig, market: str, symbol: str) -> Path:
    market_dir = _history_root(cfg) / market
    market_dir.mkdir(parents=True, exist_ok=True)
    safe_symbol = symbol.replace("/", "_")
    return market_dir / f"{safe_symbol}.csv"


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def _normalize_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return _empty_frame()

    frame = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in frame.columns:
            if col == "symbol":
                frame[col] = symbol
            else:
                frame[col] = pd.NA

    frame = frame[REQUIRED_COLUMNS].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["symbol"] = symbol
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return frame


def load_cached_history(cfg: AppConfig, market: str, symbol: str) -> pd.DataFrame:
    path = _history_path(cfg, market, symbol)
    if not path.exists():
        return _empty_frame()
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        logger.warning("Failed reading cache %s: %s", path, exc)
        return _empty_frame()
    return _normalize_frame(df, symbol)


def save_cached_history(cfg: AppConfig, market: str, symbol: str, frame: pd.DataFrame) -> None:
    path = _history_path(cfg, market, symbol)
    normalized = _normalize_frame(frame, symbol)
    normalized.to_csv(path, index=False)


def _merge_history(old: pd.DataFrame, new: pd.DataFrame, symbol: str) -> pd.DataFrame:
    old_n = _normalize_frame(old, symbol)
    new_n = _normalize_frame(new, symbol)
    if old_n.empty:
        return new_n
    if new_n.empty:
        return old_n
    merged = pd.concat([old_n, new_n], ignore_index=True)
    merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return merged


def _retry_fetch(
    fetcher: Callable[[str, date, date], pd.DataFrame],
    symbol: str,
    start: date,
    end: date,
    cfg: AppConfig,
) -> pd.DataFrame:
    last_error: Exception | None = None
    retries = max(1, cfg.fetch_max_retries)

    for attempt in range(1, retries + 1):
        try:
            return fetcher(symbol, start, end)
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            base = cfg.fetch_retry_base_delay_seconds * (2 ** (attempt - 1))
            delay = min(cfg.fetch_retry_max_delay_seconds, base)
            delay += random.uniform(0, max(0.0, cfg.fetch_retry_jitter_seconds))
            logger.warning(
                "Fetch failed for %s [%s -> %s], retry %d/%d in %.1fs: %s",
                symbol,
                start,
                end,
                attempt,
                retries,
                delay,
                exc,
            )
            time.sleep(delay)

    raise DataFetchError(f"Fetch failed after {retries} retries for {symbol}: {last_error}")


def history_window_start(cfg: AppConfig, asof_date: date) -> date:
    return asof_date - timedelta(days=cfg.training_window_days + cfg.feature_warmup_days)


def history_retention_start(cfg: AppConfig, asof_date: date) -> date:
    extra = cfg.training_window_days + cfg.feature_warmup_days + cfg.history_prune_buffer_days
    return asof_date - timedelta(days=extra)


def get_or_update_symbol_history(
    cfg: AppConfig,
    market: str,
    symbol: str,
    asof_date: date,
    fetcher: Callable[[str, date, date], pd.DataFrame],
) -> pd.DataFrame:
    cached = load_cached_history(cfg, market, symbol)
    target_start = history_window_start(cfg, asof_date)
    retention_start = history_retention_start(cfg, asof_date)

    merged = cached

    if merged.empty:
        fetched = _retry_fetch(fetcher, symbol, target_start, asof_date, cfg)
        merged = _merge_history(merged, fetched, symbol)
    else:
        earliest = min(merged["date"])
        latest = max(merged["date"])

        if latest < asof_date:
            recent_start = max(target_start, latest - timedelta(days=cfg.incremental_overlap_days))
            fetched_recent = _retry_fetch(fetcher, symbol, recent_start, asof_date, cfg)
            merged = _merge_history(merged, fetched_recent, symbol)

        if earliest > target_start:
            backfill_end = earliest + timedelta(days=1)
            fetched_old = _retry_fetch(fetcher, symbol, target_start, backfill_end, cfg)
            merged = _merge_history(merged, fetched_old, symbol)

    merged = merged[merged["date"] >= retention_start].copy()
    merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    save_cached_history(cfg, market, symbol, merged)

    windowed = merged[merged["date"] >= target_start].copy()
    if windowed.empty:
        raise DataFetchError(f"No historical rows available after incremental sync for {symbol}")

    logger.info(
        "History prepared %s/%s rows=%d range=%s..%s",
        market,
        symbol,
        len(windowed),
        windowed["date"].min(),
        windowed["date"].max(),
    )
    return windowed
