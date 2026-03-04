from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from app.common.config import load_config
from app.common.schemas import PredictionRecord, StockNarrative
from app.jobs.run_report import _summary_title
from app.report.renderer import render_summary_markdown


class ReportLanguageTest(unittest.TestCase):
    def test_report_language_from_config_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "config" / "report.yaml").write_text(
                yaml.safe_dump({"report_language": "en"}),
                encoding="utf-8",
            )
            (root / "config" / "universe.yaml").write_text(yaml.safe_dump({"cn": ["SH600519"]}), encoding="utf-8")

            cfg = load_config(root)
            self.assertEqual("en", cfg.report_language)

            with patch.dict(os.environ, {"REPORT_LANGUAGE": "zh"}, clear=False):
                cfg2 = load_config(root)
                self.assertEqual("zh", cfg2.report_language)

            with patch.dict(os.environ, {"REPORT_LANGUAGE": "invalid"}, clear=False):
                cfg3 = load_config(root)
                self.assertEqual("zh", cfg3.report_language)

    def test_summary_render_in_english(self) -> None:
        pred = PredictionRecord(
            market="us",
            symbol="AAPL",
            asof_date="2026-03-05",
            score=0.2,
            rank=1,
            side="top",
            pred_return=0.01,
            model_version="us_20260305_test",
            data_window_start="2024-03-05",
            data_window_end="2026-03-05",
        )
        narrative = StockNarrative(
            symbol="AAPL",
            summary="Bullish but watch volatility.",
            details="details",
            used_provider="tavily",
            decision="买入",
            trend="看多",
        )
        md = render_summary_markdown(
            market="us",
            asof_date="2026-03-05",
            predictions=[pred],
            narratives={"AAPL": narrative},
            failed_symbols=[],
            market_summary="Tech leadership narrowed.",
            language="en",
        )
        self.assertIn("Decision Dashboard", md)
        self.assertIn("Pred", md)
        self.assertIn("Market Recap", md)
        self.assertIn("Not investment advice", md)

    def test_summary_title_in_english(self) -> None:
        self.assertEqual("[US] 2026-03-05 Daily Summary", _summary_title("us", "2026-03-05", "en"))


if __name__ == "__main__":
    unittest.main()
