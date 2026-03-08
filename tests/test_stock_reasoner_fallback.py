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


class _HoldLLM:
    provider = "openai"
    model = "dummy"

    def __init__(self, *, action_bias: str, confidence: int) -> None:
        self._action_bias = action_bias
        self._confidence = confidence

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "summary": "summary",
            "details": "details",
            "decision": "观望",
            "trend": "震荡",
            "urgency": "中",
            "risk_points": ["risk"],
            "catalysts": ["cat"],
            "action_bias": self._action_bias,
            "confidence": self._confidence,
            "evidence_used": [],
            "reliability_notes": ["note"],
        }


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

    def test_strong_top_signal_does_not_stay_hold(self) -> None:
        pred = self._pred()
        pred.score = 1.05
        pred.pred_return = 0.028

        out = generate_stock_narrative(
            llm_client=_HoldLLM(action_bias="偏多", confidence=72),
            market="cn",
            prediction=pred,
            latest_close=1500.0,
            feature_snapshot={"ret_1": 0.01, "ret_5": 0.03, "ma5_ratio": 0.01, "ma10_ratio": 0.02, "rsi14": 55.0, "macd": 0.5},
            news_items=[],
            provider_used="tavily",
            language="zh",
        )

        self.assertEqual("买入", out.decision)

    def test_bottom_signal_hold_is_calibrated_to_trim(self) -> None:
        pred = PredictionRecord(
            market="us",
            symbol="TSLA",
            asof_date="2026-03-05",
            score=-0.35,
            rank=3,
            side="bottom",
            pred_return=-0.012,
            model_version="us_20260305_test",
            data_window_start="2024-03-05",
            data_window_end="2026-03-05",
        )

        out = generate_stock_narrative(
            llm_client=_HoldLLM(action_bias="偏空", confidence=68),
            market="us",
            prediction=pred,
            latest_close=180.0,
            feature_snapshot={"ret_1": -0.01, "ret_5": -0.03, "ma5_ratio": -0.01, "ma10_ratio": -0.02, "rsi14": 42.0, "macd": -0.4},
            news_items=[],
            provider_used="tavily",
            language="zh",
        )

        self.assertEqual("减仓", out.decision)


if __name__ == "__main__":
    unittest.main()
