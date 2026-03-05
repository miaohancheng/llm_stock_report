from __future__ import annotations

from datetime import datetime
import logging

import numpy as np
import pandas as pd

from app.features.technical import FEATURE_COLUMNS
from app.model.registry import ModelBundle

logger = logging.getLogger(__name__)


class LinearFallbackModel:
    def __init__(self, coefficients: np.ndarray):
        self.coefficients = coefficients

    def predict(self, x: np.ndarray) -> np.ndarray:
        return x @ self.coefficients[:-1] + self.coefficients[-1]


def _train_with_lightgbm(train_frame: pd.DataFrame) -> tuple[object, str]:
    from lightgbm import LGBMRegressor

    model = LGBMRegressor(
        objective="regression",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
        force_col_wise=True,
        verbosity=-1,
        random_state=42,
    )
    x = train_frame[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = train_frame["next_day_return"].to_numpy(dtype=float)
    model.fit(x, y)
    return model, "qlib-lightgbm"


def _train_with_linear_fallback(train_frame: pd.DataFrame) -> tuple[object, str]:
    x = train_frame[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = train_frame["next_day_return"].to_numpy(dtype=float)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    design = np.column_stack([x, np.ones(len(x))])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return LinearFallbackModel(coef), "linear-fallback"


def train_market_model(
    train_frame: pd.DataFrame,
    model_version: str,
    data_window_start: str,
    data_window_end: str,
) -> ModelBundle:
    if train_frame.empty:
        raise ValueError("Training frame is empty")

    if len(train_frame) < 30:
        logger.warning("Training rows are very small (%d), model quality may be poor", len(train_frame))

    symbol_count = int(train_frame["symbol"].nunique()) if "symbol" in train_frame.columns else 0
    if 0 < symbol_count < 3:
        logger.warning(
            "Universe has only %d symbol(s); skip LightGBM and use linear fallback for stability",
            symbol_count,
        )
        model, engine = _train_with_linear_fallback(train_frame)
        return ModelBundle(
            model=model,
            feature_columns=list(FEATURE_COLUMNS),
            model_version=model_version,
            engine=f"{engine}-small-universe",
            trained_at=datetime.utcnow().isoformat(timespec="seconds"),
            data_window_start=data_window_start,
            data_window_end=data_window_end,
        )

    model: object
    engine: str
    try:
        # We keep this import to align with expected Qlib runtime environments.
        # When unavailable, the pipeline falls back to a deterministic local model.
        import qlib  # noqa: F401
        model, engine = _train_with_lightgbm(train_frame)
    except Exception as exc:
        logger.warning("Qlib/LightGBM training path unavailable, fallback model used: %s", exc)
        model, engine = _train_with_linear_fallback(train_frame)

    return ModelBundle(
        model=model,
        feature_columns=list(FEATURE_COLUMNS),
        model_version=model_version,
        engine=engine,
        trained_at=datetime.utcnow().isoformat(timespec="seconds"),
        data_window_start=data_window_start,
        data_window_end=data_window_end,
    )
