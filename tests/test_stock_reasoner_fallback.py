from __future__ import annotations

import unittest

from app.common.schemas import PredictionRecord
from app.llm.base import LLMError
from app.llm.report_reasoner import generate_stock_narrative


class _FailLLM:
    provider = "openai"
    model = "dummy"

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        raise LLMError("OpenAI returned empty response body")


class StockReasonerFallbackTest(unittest.TestCase):
    def _pred(self) -> PredictionRecord:
        return PredictionRecord(
            market="cn",
            symbol="SH600519",
            asof_date="2026-03-05",
            score=0.66,
            rank=1,
            side="top",
            pred_return=0.0123,
            model_version="cn_20260305_test",
            data_window_start="2024-03-05",
            data_window_end="2026-03-05",
        )

    def test_llm_failure_returns_template_zh(self) -> None:
        out = generate_stock_narrative(
            llm_client=_FailLLM(),
            market="cn",
            prediction=self._pred(),
            latest_close=1500.0,
            feature_snapshot={"ret_1": 0.01, "ret_5": 0.03, "ma5_ratio": 0.01, "ma10_ratio": 0.02, "rsi14": 55.0, "macd": 0.5},
            news_items=[],
            provider_used="tavily",
            language="zh",
        )
        self.assertIn("模板兜底", out.summary)
        self.assertTrue(out.used_provider.endswith("+template"))
        self.assertTrue(any("兜底原因" in x for x in out.reliability_notes))

    def test_llm_failure_returns_template_en(self) -> None:
        out = generate_stock_narrative(
            llm_client=_FailLLM(),
            market="us",
            prediction=self._pred(),
            latest_close=180.0,
            feature_snapshot={"ret_1": 0.01, "ret_5": 0.03, "ma5_ratio": 0.01, "ma10_ratio": 0.02, "rsi14": 55.0, "macd": 0.5},
            news_items=[],
            provider_used="tavily",
            language="en",
        )
        self.assertIn("Template fallback", out.summary)
        self.assertTrue(out.used_provider.endswith("+template"))
        self.assertTrue(any("Fallback reason" in x for x in out.reliability_notes))


if __name__ == "__main__":
    unittest.main()
