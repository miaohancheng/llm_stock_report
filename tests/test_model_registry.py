from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from app.model.registry import ModelBundle, load_latest_model, model_is_expired, save_model_bundle


class DummyModel:
    def predict(self, x):
        return [0.0 for _ in range(len(x))]


class ModelRegistryTest(unittest.TestCase):
    def test_save_load_and_expire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = ModelBundle(
                model=DummyModel(),
                feature_columns=["ret_1"],
                model_version="cn_20260303_abcd123",
                engine="qlib-lightgbm",
                trained_at="2026-03-01T10:00:00",
                data_window_start="2024-03-01",
                data_window_end="2026-03-03",
            )
            save_model_bundle(root, "cn", bundle)

            loaded = load_latest_model(root, "cn")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(bundle.model_version, loaded.model_version)
            self.assertFalse(model_is_expired(loaded, date(2026, 3, 3), expire_days=8))
            self.assertTrue(model_is_expired(loaded, date(2026, 3, 20), expire_days=8))


if __name__ == "__main__":
    unittest.main()
