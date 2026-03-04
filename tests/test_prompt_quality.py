from __future__ import annotations

import unittest

from app.common.schemas import PredictionRecord
from app.llm.prompts import SYSTEM_PROMPT, build_stock_reasoning_prompt


class PromptQualityTest(unittest.TestCase):
    def test_prompt_contains_reliability_constraints(self) -> None:
        pred = PredictionRecord(
            market="cn",
            symbol="SH600519",
            asof_date="2026-03-04",
            score=1.2,
            rank=1,
            side="top",
            pred_return=0.03,
            model_version="cn_20260304_test",
            data_window_start="2024-03-04",
            data_window_end="2026-03-04",
        )

        prompt = build_stock_reasoning_prompt(
            market="cn",
            symbol="SH600519",
            prediction=pred,
            latest_close=1234.5,
            feature_snapshot={"ret_1": 0.01, "rsi14": 66.6},
            news_items=[],
        )

        self.assertIn("禁止编造数据", SYSTEM_PROMPT)
        self.assertIn("confidence", prompt)
        self.assertIn("evidence_used", prompt)
        self.assertIn("reliability_notes", prompt)


if __name__ == "__main__":
    unittest.main()
