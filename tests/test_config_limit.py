from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import yaml

from app.common.config import load_config
from app.jobs.run_retrain import _prepare_symbols


class ConfigLimitTest(unittest.TestCase):
    def test_universe_limit_30(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True, exist_ok=True)

            universe = {
                "cn": [f"SZ{100000+i:06d}" for i in range(35)],
                "us": ["AAPL"],
            }
            (root / "config" / "universe.yaml").write_text(
                yaml.safe_dump(universe),
                encoding="utf-8",
            )
            (root / "config" / "report.yaml").write_text(
                yaml.safe_dump({"max_stocks_per_run": 30}),
                encoding="utf-8",
            )

            cfg = load_config(root)
            symbols = _prepare_symbols(cfg, "cn")
            self.assertEqual(30, len(symbols))


if __name__ == "__main__":
    unittest.main()
