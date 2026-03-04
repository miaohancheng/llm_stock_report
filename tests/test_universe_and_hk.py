from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest

import yaml

from app.common.config import load_universe
from app.data.normalize import normalize_hk_symbol, normalize_symbol, to_yfinance_hk_ticker


class UniverseAndHKTest(unittest.TestCase):
    def test_hk_symbol_normalization(self) -> None:
        self.assertEqual("HK00700", normalize_hk_symbol("700"))
        self.assertEqual("HK00700", normalize_hk_symbol("0700"))
        self.assertEqual("HK00700", normalize_hk_symbol("00700"))
        self.assertEqual("HK00700", normalize_symbol("HK00700", "hk"))
        self.assertEqual("00700.HK", to_yfinance_hk_ticker("HK00700"))

    def test_universe_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True, exist_ok=True)

            (root / "config" / "universe.yaml").write_text(
                yaml.safe_dump(
                    {
                        "cn": ["SH600519"],
                        "us": ["AAPL"],
                        "hk": ["HK00700"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "config" / "report.yaml").write_text("", encoding="utf-8")

            old_env = {k: os.environ.get(k) for k in ["STOCK_LIST_CN", "STOCK_LIST_US", "STOCK_LIST_HK"]}
            try:
                os.environ["STOCK_LIST_CN"] = "SZ000001,SZ300750"
                os.environ["STOCK_LIST_US"] = "MSFT,NVDA"
                os.environ["STOCK_LIST_HK"] = "HK03690,09988"

                uni = load_universe(root)
                self.assertEqual(["SZ000001", "SZ300750"], uni["cn"])
                self.assertEqual(["MSFT", "NVDA"], uni["us"])
                self.assertEqual(["HK03690", "09988"], uni["hk"])
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
