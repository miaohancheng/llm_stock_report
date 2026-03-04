from __future__ import annotations

import logging
from typing import Any

from app.common.schemas import MarketNarrative, NewsItem, PredictionRecord, StockNarrative
from app.llm.base import LLMClient, LLMError
from app.llm.prompts import SYSTEM_PROMPT, build_market_reasoning_prompt, build_stock_reasoning_prompt

logger = logging.getLogger(__name__)


def _normalize_bias(raw_bias: str, prediction: PredictionRecord) -> str:
    allowed = {"偏多", "中性", "偏空"}
    bias = (raw_bias or "").strip()
    if bias in allowed:
        return bias
    if prediction.side == "top":
        return "偏多"
    if prediction.side == "bottom":
        return "偏空"
    return "中性"


def _normalize_market_bias(raw_bias: str) -> str:
    allowed = {"偏多", "中性", "偏空"}
    bias = (raw_bias or "").strip()
    return bias if bias in allowed else "中性"


def _clamp_confidence(value: Any) -> int:
    try:
        conf = int(value)
    except Exception:
        return 50
    return max(0, min(100, conf))


def _default_fallback(symbol: str, prediction: PredictionRecord, provider: str) -> StockNarrative:
    summary = (
        f"{symbol} 预测分数 {prediction.score:.2f}，"
        f"模型信号为{prediction.side}，请结合风险控制审慎评估。"
    )
    details = (
        "模型输出来自量化因子排序，新闻证据不足或解析失败时不建议单独依赖该信号。"
    )
    return StockNarrative(
        symbol=symbol,
        summary=summary,
        details=details,
        used_provider=provider,
        news_items=[],
    )


def _default_market_fallback(market: str, provider: str) -> MarketNarrative:
    return MarketNarrative(
        market=market,
        summary=f"{market.upper()} 大盘复盘生成失败，建议以指数与成交结构为主做人工复核。",
        details="大盘分析调用异常，暂无法给出可靠结论，请关注主要指数与市场宽度变化。",
        used_provider=provider,
        news_items=[],
    )


def generate_stock_narrative(
    llm_client: LLMClient,
    market: str,
    prediction: PredictionRecord,
    latest_close: float,
    feature_snapshot: dict[str, float],
    news_items: list[NewsItem],
    provider_used: str,
) -> StockNarrative:
    prompt = build_stock_reasoning_prompt(
        market=market,
        symbol=prediction.symbol,
        prediction=prediction,
        latest_close=latest_close,
        feature_snapshot=feature_snapshot,
        news_items=news_items,
    )

    try:
        parsed: dict[str, Any] = llm_client.chat_json(SYSTEM_PROMPT, prompt)
    except LLMError as exc:
        logger.warning("LLM failed for %s: %s", prediction.symbol, exc)
        raise

    summary = str(parsed.get("summary") or "").strip()
    details = str(parsed.get("details") or "").strip()
    action_bias = _normalize_bias(str(parsed.get("action_bias") or ""), prediction)
    confidence = _clamp_confidence(parsed.get("confidence"))
    evidence_used = parsed.get("evidence_used") or []
    reliability_notes = parsed.get("reliability_notes") or []

    risks = parsed.get("risk_points") or []
    if isinstance(risks, list) and risks:
        risk_lines = "\n".join([f"- {str(x)}" for x in risks[:3]])
        details = f"{details}\n\n风险点:\n{risk_lines}".strip()

    if not summary:
        return _default_fallback(prediction.symbol, prediction, provider_used)
    if not details:
        return _default_fallback(prediction.symbol, prediction, provider_used)

    ev = [str(x).strip().upper() for x in evidence_used if str(x).strip()]
    ev = [x for x in ev if x.startswith("N")]
    if ev:
        details = f"{details}\n\n证据引用: {', '.join(ev[:5])}"
    else:
        details = f"{details}\n\n证据引用: 无（新闻证据不足）"

    notes = [str(x).strip() for x in reliability_notes if str(x).strip()]
    if notes:
        details = f"{details}\n\n数据可靠性说明:\n" + "\n".join([f"- {x}" for x in notes[:3]])

    details = f"{details}\n\n结论倾向: {action_bias} | 置信度: {confidence}/100"

    return StockNarrative(
        symbol=prediction.symbol,
        summary=summary,
        details=details,
        used_provider=provider_used,
        news_items=news_items,
    )


def generate_market_narrative(
    llm_client: LLMClient,
    market: str,
    asof_date: str,
    market_snapshot: dict[str, Any],
    news_items: list[NewsItem],
    provider_used: str,
) -> MarketNarrative:
    prompt = build_market_reasoning_prompt(
        market=market,
        asof_date=asof_date,
        market_snapshot=market_snapshot,
        news_items=news_items,
    )

    try:
        parsed: dict[str, Any] = llm_client.chat_json(SYSTEM_PROMPT, prompt)
    except LLMError as exc:
        logger.warning("Market LLM failed for %s: %s", market, exc)
        raise

    summary = str(parsed.get("summary") or "").strip()
    details = str(parsed.get("details") or "").strip()
    action_bias = _normalize_market_bias(str(parsed.get("action_bias") or ""))
    confidence = _clamp_confidence(parsed.get("confidence"))
    evidence_used = parsed.get("evidence_used") or []
    reliability_notes = parsed.get("reliability_notes") or []

    risks = parsed.get("risk_points") or []
    if isinstance(risks, list) and risks:
        risk_lines = "\n".join([f"- {str(x)}" for x in risks[:3]])
        details = f"{details}\n\n风险点:\n{risk_lines}".strip()

    if not summary or not details:
        return _default_market_fallback(market, provider_used)

    ev = [str(x).strip().upper() for x in evidence_used if str(x).strip()]
    ev = [x for x in ev if x.startswith("N")]
    if ev:
        details = f"{details}\n\n证据引用: {', '.join(ev[:5])}"
    else:
        details = f"{details}\n\n证据引用: 无（新闻证据不足）"

    notes = [str(x).strip() for x in reliability_notes if str(x).strip()]
    if notes:
        details = f"{details}\n\n数据可靠性说明:\n" + "\n".join([f"- {x}" for x in notes[:3]])

    details = f"{details}\n\n结论倾向: {action_bias} | 置信度: {confidence}/100"

    return MarketNarrative(
        market=market,
        summary=summary,
        details=details,
        used_provider=provider_used,
        news_items=news_items,
    )
