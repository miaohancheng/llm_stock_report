from __future__ import annotations

import unittest

import pandas as pd

from app.model.predictor import build_predictions
from app.model.registry import ModelBundle


class _DummyModel:
    def predict(self, x):
        return x["feature_1"].to_numpy()


class PredictorBucketTest(unittest.TestCase):
    def test_small_universe_uses_non_overlapping_top_bottom_buckets(self) -> None:
        bundle = ModelBundle(
            model=_DummyModel(),
            feature_columns=["feature_1"],
            model_version="test_model",
            engine="linear-fallback",
            trained_at="2026-03-08T00:00:00",
            data_window_start="2025-03-08",
            data_window_end="2026-03-08",
        )
        frame = pd.DataFrame(
            [
                {"symbol": "AAA", "feature_1": 3.0},
                {"symbol": "BBB", "feature_1": 2.0},
                {"symbol": "CCC", "feature_1": 1.0},
            ]
        )

        out = build_predictions(
            market="us",
            asof_date="2026-03-08",
            bundle=bundle,
            predict_frame=frame,
            top_n=10,
        )

        self.assertEqual(["AAA", "BBB", "CCC"], [x.symbol for x in out])
        self.assertEqual(["top", "neutral", "bottom"], [x.side for x in out])


if __name__ == "__main__":
    unittest.main()
