from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from app.common.config import AppConfig
from app.data.history_store import get_or_update_symbol_history, load_cached_history


def _make_cfg(root: Path) -> AppConfig:
    outputs = root / "outputs"
    models = root / "models"
    qlib_data = root / "qlib_data"
    outputs.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    qlib_data.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        project_root=root,
        timezone="Asia/Shanghai",
        max_stocks_per_run=30,
        detail_message_char_limit=3500,
        model_expire_days=8,
        prediction_top_n=10,
        llm_model="gpt-4o-mini",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key=None,
        tavily_api_key=None,
        brave_api_key=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        telegram_message_thread_id=None,
        outputs_root=outputs,
        models_root=models,
        qlib_data_root=qlib_data,
        training_window_days=15,
        feature_warmup_days=0,
        history_prune_buffer_days=2,
        incremental_overlap_days=3,
        fetch_max_retries=3,
        fetch_retry_base_delay_seconds=0.01,
        fetch_retry_max_delay_seconds=0.02,
        fetch_retry_jitter_seconds=0.0,
    )


def _build_frame(symbol: str, start: date, end: date) -> pd.DataFrame:
    idx = pd.date_range(start=start, end=end, freq="D")
    rows = []
    px = 100.0
    for d in idx:
        px += 0.2
        rows.append(
            {
                "date": d.date(),
                "open": px - 0.1,
                "high": px + 0.2,
                "low": px - 0.2,
                "close": px,
                "volume": 1000,
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


class HistoryStoreTest(unittest.TestCase):
    def test_retry_fetch_success_after_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            asof = date(2026, 3, 4)
            calls = {"n": 0}

            def flaky_fetch(symbol: str, start: date, end: date) -> pd.DataFrame:
                calls["n"] += 1
                if calls["n"] < 3:
                    raise RuntimeError("temporary blocked")
                return _build_frame(symbol, start, end)

            with patch("app.data.history_store.time.sleep", return_value=None):
                frame = get_or_update_symbol_history(
                    cfg=cfg,
                    market="cn",
                    symbol="SZ000001",
                    asof_date=asof,
                    fetcher=flaky_fetch,
                )

            self.assertEqual(3, calls["n"])
            self.assertFalse(frame.empty)
            self.assertEqual(asof, max(frame["date"]))

    def test_incremental_sync_and_prune(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            asof = date(2026, 3, 4)
            symbol = "AAPL"

            # Existing cache: older range ending before asof.
            existing = _build_frame(symbol, asof - timedelta(days=20), asof - timedelta(days=5))
            history_dir = cfg.qlib_data_root / "history" / "us"
            history_dir.mkdir(parents=True, exist_ok=True)
            existing.to_csv(history_dir / f"{symbol}.csv", index=False)

            fetch_calls: list[tuple[date, date]] = []

            def fetch_recent(s: str, start: date, end: date) -> pd.DataFrame:
                fetch_calls.append((start, end))
                return _build_frame(s, start, end)

            frame = get_or_update_symbol_history(
                cfg=cfg,
                market="us",
                symbol=symbol,
                asof_date=asof,
                fetcher=fetch_recent,
            )

            self.assertEqual(1, len(fetch_calls))
            # latest in existing is asof-5, overlap=3 => fetch should start from asof-8
            self.assertEqual(asof - timedelta(days=8), fetch_calls[0][0])
            self.assertEqual(asof, fetch_calls[0][1])

            self.assertEqual(asof, max(frame["date"]))
            self.assertGreaterEqual(min(frame["date"]), asof - timedelta(days=15))

            # Cached history should prune very old rows by retention window (15+2 days).
            cached = load_cached_history(cfg, "us", symbol)
            self.assertGreaterEqual(min(cached["date"]), asof - timedelta(days=17))


if __name__ == "__main__":
    unittest.main()
