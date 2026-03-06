from __future__ import annotations

from datetime import date, timedelta
import unittest

import pandas as pd

from app.jobs.run_report import _build_lookback_metrics


class DailyLookbackMetricsTest(unittest.TestCase):
    def test_build_lookback_metrics(self) -> None:
        start = date(2026, 1, 1)
        rows = []
        px = 100.0
        for i in range(40):
            d = start + timedelta(days=i)
            px += 0.5
            rows.append(
                {
                    "date": d,
                    "open": px - 0.1,
                    "high": px + 0.4,
                    "low": px - 0.4,
                    "close": px,
                    "volume": 1000 + i * 10,
                    "symbol": "AAA",
                }
            )
        frame = pd.DataFrame(rows)
        metrics = _build_lookback_metrics(frame, 30)

        self.assertIn("lookback_days", metrics)
        self.assertIn("ret_lb", metrics)
        self.assertIn("range_lb", metrics)
        self.assertIn("vol_lb", metrics)
        self.assertIn("mdd_lb", metrics)
        self.assertIn("vol_ratio_lb", metrics)
        self.assertGreaterEqual(metrics["lookback_days"], 30.0)


if __name__ == "__main__":
    unittest.main()
