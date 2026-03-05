from __future__ import annotations

import numpy as np
import pandas as pd

from app.common.schemas import PredictionRecord
from app.model.registry import ModelBundle


def _predict_values(model: object, x_frame: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict"):
        try:
            # Keep dataframe columns so tree models fitted with feature names stay consistent.
            pred = model.predict(x_frame)
        except Exception:
            pred = model.predict(x_frame.to_numpy(dtype=float))
        return np.asarray(pred, dtype=float)
    raise TypeError("Model object does not support predict")


def build_predictions(
    market: str,
    asof_date: str,
    bundle: ModelBundle,
    predict_frame: pd.DataFrame,
    top_n: int,
) -> list[PredictionRecord]:
    if predict_frame.empty:
        return []

    x_frame = predict_frame[bundle.feature_columns].copy()
    raw = _predict_values(bundle.model, x_frame)
    std = float(np.std(raw)) if len(raw) > 1 else 0.0
    scores = (raw - float(np.mean(raw))) / (std if std > 1e-12 else 1.0)

    out = predict_frame[["symbol"]].copy()
    out["pred_return"] = raw
    out["score"] = scores
    out = out.sort_values("score", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1

    total = len(out)
    records: list[PredictionRecord] = []
    for _, row in out.iterrows():
        rank = int(row["rank"])
        if rank <= top_n:
            side = "top"
        elif rank > total - top_n:
            side = "bottom"
        else:
            side = "neutral"

        records.append(
            PredictionRecord(
                market=market,
                symbol=str(row["symbol"]),
                asof_date=asof_date,
                score=float(row["score"]),
                rank=rank,
                side=side,
                pred_return=float(row["pred_return"]),
                model_version=bundle.model_version,
                data_window_start=bundle.data_window_start,
                data_window_end=bundle.data_window_end,
            )
        )

    return records
