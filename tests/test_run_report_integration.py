from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from app.common.config import AppConfig
from app.common.schemas import NewsItem, StockNarrative
from app.features.technical import FEATURE_COLUMNS
from app.jobs import run_report
from app.model.registry import ModelBundle


class DummyPredictor:
    def predict(self, x):
        # deterministic ranking by first feature
        return x[:, 0]


def _make_ohlcv(symbol: str, end_date: date, days: int = 80) -> pd.DataFrame:
    start = end_date - timedelta(days=days)
    idx = pd.date_range(start=start, end=end_date, freq="B")
    rows = []
    price = 100.0
    for d in idx:
        price += 0.5
        rows.append(
            {
                "date": d.date(),
                "open": price - 0.2,
                "high": price + 0.4,
                "low": price - 0.4,
                "close": price,
                "volume": 100000,
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


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
        prediction_top_n=2,
        llm_model="gpt-4o-mini",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="dummy",
        tavily_api_key="t",
        brave_api_key="b",
        telegram_bot_token="token",
        telegram_chat_id="chat",
        telegram_message_thread_id=None,
        outputs_root=outputs,
        models_root=models,
        qlib_data_root=qlib_data,
    )


class RunReportIntegrationTest(unittest.TestCase):
    def test_cn_report_outputs_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)

            bundle = ModelBundle(
                model=DummyPredictor(),
                feature_columns=list(FEATURE_COLUMNS),
                model_version="cn_20260303_test",
                engine="qlib-lightgbm",
                trained_at="2026-03-03T10:00:00",
                data_window_start="2024-03-03",
                data_window_end="2026-03-03",
            )

            def fake_narrative(**kwargs):
                pred = kwargs["prediction"]
                return StockNarrative(
                    symbol=pred.symbol,
                    summary=f"{pred.symbol} summary",
                    details=f"{pred.symbol} details",
                    used_provider="tavily",
                    news_items=[],
                )

            with patch("app.jobs.run_report.load_config", return_value=cfg), \
                patch("app.jobs.run_report.load_universe", return_value={"cn": ["SZ000001", "SH600519", "SZ300750"], "us": []}), \
                patch("app.jobs.run_report._fetch_single_symbol", side_effect=lambda market, symbol, start, asof: _make_ohlcv(symbol, asof)), \
                patch("app.jobs.run_report._resolve_model_bundle", return_value=bundle), \
                patch("app.jobs.run_report.search_news_with_fallback", return_value=([], "tavily")), \
                patch("app.jobs.run_report.generate_stock_narrative", side_effect=fake_narrative):
                with patch("sys.argv", ["run_report", "--market", "cn", "--date", "2026-03-03", "--no-telegram"]):
                    code = run_report.main()

            self.assertEqual(0, code)
            output_dir = cfg.outputs_root / "cn" / "2026-03-03"
            self.assertTrue((output_dir / "summary.md").exists())
            self.assertTrue((output_dir / "details.md").exists())
            self.assertTrue((output_dir / "predictions.csv").exists())
            self.assertTrue((output_dir / "run_meta.json").exists())

    def test_us_report_telegram_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)

            bundle = ModelBundle(
                model=DummyPredictor(),
                feature_columns=list(FEATURE_COLUMNS),
                model_version="us_20260303_test",
                engine="qlib-lightgbm",
                trained_at="2026-03-03T10:00:00",
                data_window_start="2024-03-03",
                data_window_end="2026-03-03",
            )

            def fake_narrative(**kwargs):
                pred = kwargs["prediction"]
                news = [NewsItem(title="n", url="https://example.com", source="x", snippet="s")]
                return StockNarrative(
                    symbol=pred.symbol,
                    summary=f"{pred.symbol} summary",
                    details=f"{pred.symbol} details",
                    used_provider="brave",
                    news_items=news,
                )

            post_calls: list[str] = []

            class FakeResp:
                status_code = 200

                @staticmethod
                def json():
                    return {"ok": True}

            def fake_post(url, json, timeout):
                post_calls.append(json["text"])
                return FakeResp()

            with patch("app.jobs.run_report.load_config", return_value=cfg), \
                patch("app.jobs.run_report.load_universe", return_value={"cn": [], "us": ["AAPL", "MSFT", "NVDA"]}), \
                patch("app.jobs.run_report._fetch_single_symbol", side_effect=lambda market, symbol, start, asof: _make_ohlcv(symbol, asof)), \
                patch("app.jobs.run_report._resolve_model_bundle", return_value=bundle), \
                patch("app.jobs.run_report.search_news_with_fallback", return_value=([], "brave")), \
                patch("app.jobs.run_report.generate_stock_narrative", side_effect=fake_narrative), \
                patch("app.report.telegram_sender.requests.post", side_effect=fake_post):
                with patch("sys.argv", ["run_report", "--market", "us", "--date", "2026-03-03"]):
                    code = run_report.main()

            self.assertEqual(0, code)
            self.assertGreaterEqual(len(post_calls), 2)
            # First message should be summary.
            self.assertIn("日报摘要", post_calls[0])
            # Later messages should contain symbol detail headers.
            self.assertTrue(any("AAPL" in c or "MSFT" in c or "NVDA" in c for c in post_calls[1:]))


if __name__ == "__main__":
    unittest.main()
