from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_1",
    "ret_5",
    "ma5_ratio",
    "ma10_ratio",
    "ma20_ratio",
    "rsi14",
    "macd",
    "macd_signal",
    "vol_ratio_5",
    "volatility_10",
]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = down.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-12)
    return 100 - (100 / (1 + rs))


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["symbol", "date"])

    grouped = frame.groupby("symbol", group_keys=False)

    frame["ret_1"] = grouped["close"].pct_change(1)
    frame["ret_5"] = grouped["close"].pct_change(5)

    ma5 = grouped["close"].transform(lambda x: x.rolling(5, min_periods=5).mean())
    ma10 = grouped["close"].transform(lambda x: x.rolling(10, min_periods=10).mean())
    ma20 = grouped["close"].transform(lambda x: x.rolling(20, min_periods=20).mean())

    frame["ma5_ratio"] = frame["close"] / ma5 - 1
    frame["ma10_ratio"] = frame["close"] / ma10 - 1
    frame["ma20_ratio"] = frame["close"] / ma20 - 1

    frame["rsi14"] = grouped["close"].transform(_rsi)

    ema12 = grouped["close"].transform(lambda x: x.ewm(span=12, adjust=False).mean())
    ema26 = grouped["close"].transform(lambda x: x.ewm(span=26, adjust=False).mean())
    frame["macd"] = ema12 - ema26
    frame["macd_signal"] = grouped["macd"].transform(lambda x: x.ewm(span=9, adjust=False).mean())

    vol5 = grouped["volume"].transform(lambda x: x.rolling(5, min_periods=5).mean())
    frame["vol_ratio_5"] = frame["volume"] / vol5

    frame["volatility_10"] = grouped["ret_1"].transform(lambda x: x.rolling(10, min_periods=10).std())

    frame["next_day_return"] = grouped["close"].shift(-1) / frame["close"] - 1

    frame = frame.replace([np.inf, -np.inf], np.nan)
    return frame
