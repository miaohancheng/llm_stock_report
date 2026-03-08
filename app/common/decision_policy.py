from __future__ import annotations

from app.common.schemas import PredictionRecord


def _side(prediction: PredictionRecord) -> str:
    return (prediction.side or "").strip().lower()


def baseline_decision(prediction: PredictionRecord) -> str:
    side = _side(prediction)
    score = float(prediction.score or 0.0)
    pred_return = float(prediction.pred_return or 0.0)
    rank = int(prediction.rank or 0)

    if side == "top":
        if score >= 0.55 or pred_return >= 0.02:
            return "买入"
        if rank == 1 and score >= 0.2 and pred_return >= 0.0:
            return "买入"
        return "观望"

    if side == "bottom":
        if score <= -0.55 or pred_return <= -0.02:
            return "卖出"
        return "减仓"

    return "观望"


def baseline_trend(prediction: PredictionRecord) -> str:
    side = _side(prediction)
    if side == "top":
        return "看多"
    if side == "bottom":
        return "看空"
    return "震荡"


def calibrate_decision(
    *,
    prediction: PredictionRecord,
    decision: str,
    action_bias: str,
    confidence: int,
) -> str:
    baseline = baseline_decision(prediction)
    bias = (action_bias or "").strip()
    side = _side(prediction)

    if decision == "观望":
        if baseline == "买入" and bias == "偏多" and confidence >= 55:
            return "买入"
        if baseline == "卖出" and bias == "偏空" and confidence >= 55:
            return "卖出"
        if baseline == "减仓" and bias == "偏空":
            return "减仓"

    if side == "top" and decision in {"减仓", "卖出", "卖出/观望"} and bias == "偏多" and confidence >= 65:
        return baseline

    if side == "bottom" and decision == "买入" and bias == "偏空" and confidence >= 65:
        return baseline

    return decision
