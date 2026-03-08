from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app.features.technical import FEATURE_COLUMNS
from app.model.trainer import train_market_model


def _train_frame() -> pd.DataFrame:
    rows: list[dict] = []
    symbols = ["AAPL", "MSFT", "NVDA"]
    for idx, symbol in enumerate(symbols):
        for step in range(4):
            row = {
                "symbol": symbol,
                "next_day_return": 0.001 * (idx + step + 1),
            }
            for feature_idx, feature in enumerate(FEATURE_COLUMNS, start=1):
                row[feature] = float((idx + 1) * (step + feature_idx))
            rows.append(row)
    return pd.DataFrame(rows)


class TrainerMetadataTest(unittest.TestCase):
    def test_lightgbm_failure_sets_fallback_metadata(self) -> None:
        with patch("app.model.trainer._train_with_lightgbm", side_effect=RuntimeError("boom")):
            bundle = train_market_model(
                train_frame=_train_frame(),
                model_version="us_20260308_test",
                data_window_start="2024-03-08",
                data_window_end="2026-03-08",
            )

        self.assertTrue(bundle.fallback_used)
        self.assertIn("lightgbm-unavailable", bundle.fallback_reason or "")
        self.assertEqual(12, bundle.train_rows)
        self.assertEqual(3, bundle.symbol_count)


if __name__ == "__main__":
    unittest.main()
