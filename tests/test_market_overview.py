from __future__ import annotations

from datetime import date, timedelta
import unittest

import pandas as pd

from app.report.market_overview import build_market_snapshot


def _frame(symbol: str, start: date, days: int, step: float) -> pd.DataFrame:
    rows = []
    px = 100.0
    for i in range(days):
        d = start + timedelta(days=i)
        px += step
        rows.append(
            {
                "date": d,
                "open": px - 0.1,
                "high": px + 0.2,
                "low": px - 0.2,
                "close": px,
                "volume": 1000 + i,
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


class MarketOverviewTest(unittest.TestCase):
    def test_build_snapshot_from_symbol_pool(self) -> None:
        asof = date(2026, 3, 3)
        start = asof - timedelta(days=10)
        market_data = {
            "AAA": _frame("AAA", start, 11, 1.0),
            "BBB": _frame("BBB", start, 11, -0.5),
            "CCC": _frame("CCC", start, 11, 0.2),
        }
        snapshot = build_market_snapshot(
            market="us",
            market_data=market_data,
            asof_date=asof,
            market_index_fetch_enabled=False,
        )

        self.assertEqual("us", snapshot["market"])
        self.assertEqual(3, snapshot["sample_size"])
        self.assertEqual(2, snapshot["up_count"])
        self.assertEqual(1, snapshot["down_count"])
        self.assertEqual(0, len(snapshot["benchmarks"]))
        self.assertTrue(snapshot["gainers"])
        self.assertTrue(snapshot["losers"])


if __name__ == "__main__":
    unittest.main()
