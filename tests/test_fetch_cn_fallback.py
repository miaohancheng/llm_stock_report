from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

import pandas as pd

from app.data.fetch_cn import fetch_cn_ohlcv
from app.data.normalize import DataFetchError


def _em_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "日期": ["2026-03-01", "2026-03-02"],
            "开盘": [10.0, 10.2],
            "收盘": [10.3, 10.1],
            "最高": [10.4, 10.5],
            "最低": [9.9, 10.0],
            "成交量": [100000, 120000],
        }
    )


def _tx_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-03-01", "2026-03-02"],
            "open": [10.0, 10.2],
            "close": [10.3, 10.1],
            "high": [10.4, 10.5],
            "low": [9.9, 10.0],
            "amount": [100000, 120000],
        }
    )


def _yf_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2026-03-01", "2026-03-02"])
    return pd.DataFrame(
        {
            "Open": [10.0, 10.2],
            "High": [10.4, 10.5],
            "Low": [9.9, 10.0],
            "Close": [10.3, 10.1],
            "Volume": [100000, 120000],
        },
        index=idx,
    )


class FetchCnFallbackTest(unittest.TestCase):
    def test_eastmoney_success_first(self) -> None:
        with patch("akshare.stock_zh_a_hist", return_value=_em_df()) as em_mock, \
            patch("akshare.stock_zh_a_hist_tx") as tx_mock:
            out = fetch_cn_ohlcv("SH600519", date(2026, 3, 1), date(2026, 3, 2))

        self.assertFalse(out.empty)
        self.assertEqual("SH600519", out.iloc[-1]["symbol"])
        em_mock.assert_called_once()
        tx_mock.assert_not_called()

    def test_tencent_fallback_when_eastmoney_fails(self) -> None:
        with patch("akshare.stock_zh_a_hist", side_effect=RuntimeError("remote closed")), \
            patch("akshare.stock_zh_a_hist_tx", return_value=_tx_df()) as tx_mock, \
            patch("yfinance.download") as yf_mock:
            out = fetch_cn_ohlcv("SH600519", date(2026, 3, 1), date(2026, 3, 2))

        self.assertFalse(out.empty)
        self.assertEqual("SH600519", out.iloc[-1]["symbol"])
        self.assertIn("volume", out.columns)
        tx_mock.assert_called_once()
        yf_mock.assert_not_called()

    def test_yfinance_fallback_when_akshare_unavailable(self) -> None:
        with patch("akshare.stock_zh_a_hist", side_effect=RuntimeError("em blocked")), \
            patch("akshare.stock_zh_a_hist_tx", side_effect=RuntimeError("tx blocked")), \
            patch("yfinance.download", return_value=_yf_df()) as yf_mock:
            out = fetch_cn_ohlcv("SZ000001", date(2026, 3, 1), date(2026, 3, 2))

        self.assertFalse(out.empty)
        self.assertEqual("SZ000001", out.iloc[-1]["symbol"])
        yf_mock.assert_called_once()

    def test_raise_when_all_providers_fail(self) -> None:
        with patch("akshare.stock_zh_a_hist", side_effect=RuntimeError("em blocked")), \
            patch("akshare.stock_zh_a_hist_tx", side_effect=RuntimeError("tx blocked")), \
            patch("yfinance.download", side_effect=RuntimeError("yf blocked")):
            with self.assertRaises(DataFetchError):
                fetch_cn_ohlcv("SZ000001", date(2026, 3, 1), date(2026, 3, 2))


if __name__ == "__main__":
    unittest.main()
