from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Tuple

import pandas as pd

from app.features.technical import FEATURE_COLUMNS, add_technical_features


def build_market_feature_frame(market_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for symbol, df in market_data.items():
        local = df.copy()
        local["symbol"] = symbol
        frames.append(local)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    featured = add_technical_features(merged)
    featured["date"] = pd.to_datetime(featured["date"]).dt.date
    return featured


def split_train_predict_frame(feature_frame: pd.DataFrame, asof_date: date) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if feature_frame.empty:
        return feature_frame.copy(), feature_frame.copy()

    # Train on rows strictly before asof date with labels.
    train = feature_frame[
        (feature_frame["date"] < asof_date) & feature_frame["next_day_return"].notna()
    ].copy()

    # Predict using latest available row per symbol at or before asof date.
    valid = feature_frame[feature_frame["date"] <= asof_date].copy()
    idx = valid.groupby("symbol")["date"].transform("max") == valid["date"]
    predict = valid[idx].copy()

    # Keep only rows with full features.
    train = train.dropna(subset=FEATURE_COLUMNS + ["next_day_return"])
    predict = predict.dropna(subset=FEATURE_COLUMNS)
    return train, predict


def frame_window(feature_frame: pd.DataFrame) -> tuple[str, str]:
    if feature_frame.empty:
        return "", ""
    start = pd.to_datetime(feature_frame["date"]).min().date().isoformat()
    end = pd.to_datetime(feature_frame["date"]).max().date().isoformat()
    return start, end


def save_debug_frames(root: Path, market: str, asof_date: date, train: pd.DataFrame, predict: pd.DataFrame) -> None:
    debug_dir = root / "debug" / market / asof_date.isoformat()
    debug_dir.mkdir(parents=True, exist_ok=True)
    train.to_csv(debug_dir / "train_frame.csv", index=False)
    predict.to_csv(debug_dir / "predict_frame.csv", index=False)
