from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from app.common.config import load_config
from app.common.schemas import MarketNarrative, NewsItem, PredictionRecord, StockNarrative
from app.jobs.run_report import _summary_title
from app.report.renderer import (
    render_market_detail_telegram_card,
    render_summary_markdown,
    render_summary_telegram_card,
    render_symbol_detail_telegram_card,
)


class ReportLanguageTest(unittest.TestCase):
    def test_report_language_from_config_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "config" / "report.yaml").write_text(
                yaml.safe_dump({"report_language": "en", "pages_site_base_url": "https://example.com/site/"}),
                encoding="utf-8",
            )
            (root / "config" / "universe.yaml").write_text(yaml.safe_dump({"cn": ["SH600519"]}), encoding="utf-8")

            isolated_env = dict(os.environ)
            for key in ("REPORT_LANGUAGE", "PAGES_SITE_BASE_URL"):
                isolated_env.pop(key, None)

            with patch.dict(os.environ, isolated_env, clear=True):
                cfg = load_config(root)
                self.assertEqual("en", cfg.report_language)
                self.assertEqual("https://example.com/site", cfg.pages_site_base_url)

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

    def test_summary_telegram_card_in_chinese(self) -> None:
        preds = [
            PredictionRecord(
                market="us",
                symbol="AAPL",
                asof_date="2026-03-05",
                score=0.8,
                rank=1,
                side="top",
                pred_return=0.021,
                model_version="us_20260305_test",
                data_window_start="2024-03-05",
                data_window_end="2026-03-05",
            ),
            PredictionRecord(
                market="us",
                symbol="TSLA",
                asof_date="2026-03-05",
                score=-0.7,
                rank=2,
                side="bottom",
                pred_return=-0.015,
                model_version="us_20260305_test",
                data_window_start="2024-03-05",
                data_window_end="2026-03-05",
            ),
        ]
        narratives = {
            "AAPL": StockNarrative(
                symbol="AAPL",
                summary="景气度仍在，但追高需要观察成交量。",
                details="details",
                used_provider="tavily",
                decision="买入",
                trend="看多",
            ),
            "TSLA": StockNarrative(
                symbol="TSLA",
                summary="事件扰动仍大，短线承压。",
                details="details",
                used_provider="tavily",
                decision="卖出",
                trend="看空",
            ),
        }
        card = render_summary_telegram_card(
            market="us",
            asof_date="2026-03-05",
            predictions=preds,
            narratives=narratives,
            failed_symbols=["META"],
            market_summary="科技股分化，风险偏好没有同步扩散。",
            language="zh",
            pages_url="https://example.com/site/zh/cases/us-2026-03-05.html",
            model_warning="当前使用降级模型（linear-fallback）。原因：small-universe。",
        )
        self.assertIn("交易卡片", card)
        self.assertIn("最强信号", card)
        self.assertIn("主要风险", card)
        self.assertIn("关注名单", card)
        self.assertIn("跳过", card)
        self.assertIn("查看完整报告", card)
        self.assertIn("模型提醒", card)

    def test_symbol_telegram_card_is_compact(self) -> None:
        pred = PredictionRecord(
            market="us",
            symbol="NVDA",
            asof_date="2026-03-05",
            score=1.1,
            rank=1,
            side="top",
            pred_return=0.034,
            model_version="us_20260305_test",
            data_window_start="2024-03-05",
            data_window_end="2026-03-05",
        )
        narrative = StockNarrative(
            symbol="NVDA",
            summary="算力主线没坏，但波动会放大。",
            details="这里是长推理，不应该直接原样出现在 Telegram 卡片里。",
            used_provider="brave",
            decision="买入",
            trend="看多",
            urgency="高",
            catalysts=["财报预期改善", "AI 资本开支继续上修"],
            risk_points=["高位波动放大", "若指引不及预期会快速回撤"],
            news_items=[NewsItem(title="NVIDIA earnings preview", url="https://example.com/nvda", source="x", snippet="s")],
            latest_close=912.34,
        )
        card = render_symbol_detail_telegram_card(
            market="us",
            asof_date="2026-03-05",
            prediction=pred,
            narrative=narrative,
            language="zh",
            pages_url="https://example.com/site/zh/cases/us-2026-03-05.html",
        )
        self.assertIn("一句话", card)
        self.assertIn("动作", card)
        self.assertIn("新闻线索", card)
        self.assertNotIn("详细推理", card)
        self.assertIn("查看完整报告", card)

    def test_market_telegram_card_in_english(self) -> None:
        narrative = MarketNarrative(
            market="us",
            summary="Breadth stayed weak even as mega caps held up.",
            details="long details",
            used_provider="tavily",
            news_items=[NewsItem(title="Fed watch", url="https://example.com/fed", source="x", snippet="s")],
        )
        card = render_market_detail_telegram_card(
            market="us",
            asof_date="2026-03-05",
            market_snapshot={
                "up_count": 120,
                "down_count": 220,
                "flat_count": 15,
                "avg_ret_1d": -0.001,
                "median_ret_1d": -0.003,
                "benchmarks": [
                    {"name": "NASDAQ 100", "ret_1d": 0.004},
                    {"name": "S&P 500", "ret_1d": 0.001},
                ],
            },
            narrative=narrative,
            language="en",
            pages_url="https://example.com/site/en/cases/us-2026-03-05.html",
        )
        self.assertIn("Market Card", card)
        self.assertIn("Breadth", card)
        self.assertIn("Benchmarks", card)
        self.assertIn("News Hooks", card)
        self.assertIn("Open full report", card)


if __name__ == "__main__":
    unittest.main()
