from __future__ import annotations

import logging
from typing import Any

from app.common.schemas import MarketNarrative, NewsItem, PredictionRecord, StockNarrative
from app.llm.base import LLMClient, LLMError
from app.llm.prompts import build_market_reasoning_prompt, build_stock_reasoning_prompt, get_system_prompt

logger = logging.getLogger(__name__)


def _normalize_bias(raw_bias: str, prediction: PredictionRecord) -> str:
    canonical = {
        "偏多": "偏多",
        "bullish": "偏多",
        "long": "偏多",
        "中性": "中性",
        "neutral": "中性",
        "偏空": "偏空",
        "bearish": "偏空",
        "short": "偏空",
    }
    bias = canonical.get((raw_bias or "").strip().lower(), None) or canonical.get((raw_bias or "").strip(), None)
    if bias:
        return bias
    if prediction.side == "top":
        return "偏多"
    if prediction.side == "bottom":
        return "偏空"
    return "中性"


def _normalize_market_bias(raw_bias: str) -> str:
    canonical = {
        "偏多": "偏多",
        "bullish": "偏多",
        "long": "偏多",
        "中性": "中性",
        "neutral": "中性",
        "偏空": "偏空",
        "bearish": "偏空",
        "short": "偏空",
    }
    return canonical.get((raw_bias or "").strip().lower(), None) or canonical.get((raw_bias or "").strip(), "中性")


def _clamp_confidence(value: Any) -> int:
    try:
        conf = int(value)
    except Exception:
        return 50
    return max(0, min(100, conf))


def _normalize_decision(raw: str, prediction: PredictionRecord) -> str:
    canonical = {
        "买入": "买入",
        "buy": "买入",
        "观望": "观望",
        "hold": "观望",
        "减仓": "减仓",
        "trim": "减仓",
        "卖出": "卖出",
        "sell": "卖出",
        "卖出/观望": "卖出/观望",
        "sell/hold": "卖出/观望",
    }
    value = canonical.get((raw or "").strip().lower(), None) or canonical.get((raw or "").strip(), None)
    if value:
        return value
    if prediction.side == "top" and prediction.score > 0.8:
        return "买入"
    if prediction.side == "bottom" and prediction.score < -0.8:
        return "卖出"
    if prediction.side == "bottom":
        return "减仓"
    return "观望"


def _normalize_trend(raw: str, prediction: PredictionRecord) -> str:
    canonical = {
        "看多": "看多",
        "bullish": "看多",
        "震荡": "震荡",
        "sideways": "震荡",
        "看空": "看空",
        "bearish": "看空",
        "强烈看空": "强烈看空",
        "strong bearish": "强烈看空",
    }
    value = canonical.get((raw or "").strip().lower(), None) or canonical.get((raw or "").strip(), None)
    if value:
        return value
    if prediction.side == "top":
        return "看多"
    if prediction.side == "bottom":
        return "看空"
    return "震荡"


def _normalize_urgency(raw: str, confidence: int) -> str:
    canonical = {
        "高": "高",
        "high": "高",
        "中": "中",
        "medium": "中",
        "低": "低",
        "low": "低",
    }
    value = canonical.get((raw or "").strip().lower(), None) or canonical.get((raw or "").strip(), None)
    if value:
        return value
    if confidence >= 75:
        return "高"
    if confidence <= 45:
        return "低"
    return "中"


def _format_bias_text(canonical_bias: str, language: str) -> str:
    if (language or "").strip().lower() == "en":
        mapping = {"偏多": "Bullish", "中性": "Neutral", "偏空": "Bearish"}
        return mapping.get(canonical_bias, "Neutral")
    return canonical_bias


def _default_fallback(symbol: str, prediction: PredictionRecord, provider: str, language: str = "zh") -> StockNarrative:
    language = (language or "zh").strip().lower()
    if language == "en":
        summary = (
            f"{symbol} score={prediction.score:.2f}; model side={prediction.side}. "
            "Use strict risk control and avoid single-signal decisions."
        )
        details = (
            "This output is based on factor-model ranking. Do not rely on it alone when news evidence is missing or LLM parsing fails."
        )
        reliability_notes = ["Insufficient news evidence or LLM parse fallback."]
    else:
        summary = (
            f"{symbol} 预测分数 {prediction.score:.2f}，"
            f"模型信号为{prediction.side}，请结合风险控制审慎评估。"
        )
        details = (
            "模型输出来自量化因子排序，新闻证据不足或解析失败时不建议单独依赖该信号。"
        )
        reliability_notes = ["新闻证据不足或LLM解析失败"]
    return StockNarrative(
        symbol=symbol,
        summary=summary,
        details=details,
        used_provider=provider,
        news_items=[],
        decision=_normalize_decision("", prediction),
        trend=_normalize_trend("", prediction),
        urgency="中",
        confidence=50,
        risk_points=[],
        catalysts=[],
        evidence_used=[],
        reliability_notes=reliability_notes,
    )


def _default_market_fallback(market: str, provider: str, language: str = "zh") -> MarketNarrative:
    language = (language or "zh").strip().lower()
    if language == "en":
        summary = (
            f"{market.upper()} market recap generation failed. "
            "Please manually validate benchmark index and market breadth."
        )
        details = (
            "Market analysis call failed. Reliable conclusion is unavailable; focus on index trend and breadth changes."
        )
    else:
        summary = f"{market.upper()} 大盘复盘生成失败，建议以指数与成交结构为主做人工复核。"
        details = "大盘分析调用异常，暂无法给出可靠结论，请关注主要指数与市场宽度变化。"
    return MarketNarrative(
        market=market,
        summary=summary,
        details=details,
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
    language: str = "zh",
) -> StockNarrative:
    language = (language or "zh").strip().lower()
    prompt = build_stock_reasoning_prompt(
        market=market,
        symbol=prediction.symbol,
        prediction=prediction,
        latest_close=latest_close,
        feature_snapshot=feature_snapshot,
        news_items=news_items,
        language=language,
    )

    try:
        parsed: dict[str, Any] = llm_client.chat_json(get_system_prompt(language), prompt)
    except LLMError as exc:
        logger.warning("LLM failed for %s: %s", prediction.symbol, exc)
        raise

    summary = str(parsed.get("summary") or "").strip()
    details = str(parsed.get("details") or "").strip()
    action_bias = _normalize_bias(str(parsed.get("action_bias") or ""), prediction)
    confidence = _clamp_confidence(parsed.get("confidence"))
    decision = _normalize_decision(str(parsed.get("decision") or ""), prediction)
    trend = _normalize_trend(str(parsed.get("trend") or ""), prediction)
    urgency = _normalize_urgency(str(parsed.get("urgency") or ""), confidence)
    evidence_used = parsed.get("evidence_used") or []
    reliability_notes = parsed.get("reliability_notes") or []
    catalysts = parsed.get("catalysts") or []

    risks = parsed.get("risk_points") or []
    risk_points = [str(x).strip() for x in risks if str(x).strip()][:4]
    catalysts_list = [str(x).strip() for x in catalysts if str(x).strip()][:3]

    if not summary:
        return _default_fallback(prediction.symbol, prediction, provider_used, language=language)
    if not details:
        return _default_fallback(prediction.symbol, prediction, provider_used, language=language)

    ev = [str(x).strip().upper() for x in evidence_used if str(x).strip()]
    ev = [x for x in ev if x.startswith("N")]
    notes = [str(x).strip() for x in reliability_notes if str(x).strip()]

    if language == "en":
        details = f"{details}\n\nBias: {_format_bias_text(action_bias, language)} | Confidence: {confidence}/100"
    else:
        details = f"{details}\n\n结论倾向: {action_bias} | 置信度: {confidence}/100"

    return StockNarrative(
        symbol=prediction.symbol,
        summary=summary,
        details=details,
        used_provider=provider_used,
        news_items=news_items,
        decision=decision,
        trend=trend,
        urgency=urgency,
        confidence=confidence,
        risk_points=risk_points,
        catalysts=catalysts_list,
        evidence_used=ev[:5],
        reliability_notes=notes[:3],
        latest_close=latest_close,
        feature_snapshot=feature_snapshot,
    )


def generate_market_narrative(
    llm_client: LLMClient,
    market: str,
    asof_date: str,
    market_snapshot: dict[str, Any],
    news_items: list[NewsItem],
    provider_used: str,
    language: str = "zh",
) -> MarketNarrative:
    language = (language or "zh").strip().lower()
    prompt = build_market_reasoning_prompt(
        market=market,
        asof_date=asof_date,
        market_snapshot=market_snapshot,
        news_items=news_items,
        language=language,
    )

    try:
        parsed: dict[str, Any] = llm_client.chat_json(get_system_prompt(language), prompt)
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
        label = "Risk points" if language == "en" else "风险点"
        details = f"{details}\n\n{label}:\n{risk_lines}".strip()

    if not summary or not details:
        return _default_market_fallback(market, provider_used, language=language)

    ev = [str(x).strip().upper() for x in evidence_used if str(x).strip()]
    ev = [x for x in ev if x.startswith("N")]
    if ev:
        label = "Evidence references" if language == "en" else "证据引用"
        details = f"{details}\n\n{label}: {', '.join(ev[:5])}"
    else:
        if language == "en":
            details = f"{details}\n\nEvidence references: None (insufficient news evidence)"
        else:
            details = f"{details}\n\n证据引用: 无（新闻证据不足）"

    notes = [str(x).strip() for x in reliability_notes if str(x).strip()]
    if notes:
        label = "Reliability notes" if language == "en" else "数据可靠性说明"
        details = f"{details}\n\n{label}:\n" + "\n".join([f"- {x}" for x in notes[:3]])

    if language == "en":
        details = (
            f"{details}\n\nBias: {_format_bias_text(action_bias, language)} | Confidence: {confidence}/100"
        )
    else:
        details = f"{details}\n\n结论倾向: {action_bias} | 置信度: {confidence}/100"

    return MarketNarrative(
        market=market,
        summary=summary,
        details=details,
        used_provider=provider_used,
        news_items=news_items,
    )
