from __future__ import annotations

import logging
from typing import Any

from app.common.decision_policy import baseline_decision, baseline_trend, calibrate_decision
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
    return baseline_decision(prediction)


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
    return baseline_trend(prediction)


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


def _market_label(market: str, language: str) -> str:
    m = (market or "").strip().lower()
    if (language or "").strip().lower() == "en":
        return {"cn": "China A-share", "us": "US", "hk": "Hong Kong"}.get(m, m.upper())
    return {"cn": "A股", "us": "美股", "hk": "港股"}.get(m, m.upper())


def _market_mood_text(market_snapshot: dict[str, Any], language: str) -> str:
    anchor_ret = float(market_snapshot.get("avg_ret_1d", 0.0) or 0.0)
    benches = market_snapshot.get("benchmarks") or []
    if isinstance(benches, list) and benches:
        try:
            anchor_ret = float((benches[0] or {}).get("ret_1d", anchor_ret) or anchor_ret)
        except Exception:
            pass
    if (language or "").strip().lower() == "en":
        if anchor_ret >= 0.01:
            return "strong bullish"
        if anchor_ret >= 0.002:
            return "mild bullish"
        if anchor_ret <= -0.01:
            return "sharp pullback"
        if anchor_ret <= -0.002:
            return "mild pullback"
        return "sideways"
    if anchor_ret >= 0.01:
        return "强势上涨"
    if anchor_ret >= 0.002:
        return "小幅上涨"
    if anchor_ret <= -0.01:
        return "明显下跌"
    if anchor_ret <= -0.002:
        return "小幅下跌"
    return "震荡整理"


def _default_fallback(
    symbol: str,
    prediction: PredictionRecord,
    provider: str,
    language: str = "zh",
    *,
    reason: str | None = None,
) -> StockNarrative:
    language = (language or "zh").strip().lower()
    reason_text = (reason or "").strip()
    if language == "en":
        summary = (
            f"{symbol} score={prediction.score:.2f}; model side={prediction.side}. "
            "Use strict risk control and avoid single-signal decisions. Template fallback applied."
        )
        details = (
            "This output is based on factor-model ranking. Do not rely on it alone when news evidence is missing or LLM parsing fails.\n\n"
            "Watchpoints: monitor volume expansion, MA20 trend integrity, and event-driven volatility."
        )
        reliability_notes = ["Insufficient news evidence or LLM parse fallback."]
        if reason_text:
            reliability_notes.append(f"Fallback reason: {reason_text[:180]}")
    else:
        summary = (
            f"{symbol} 预测分数 {prediction.score:.2f}，"
            f"模型信号为{prediction.side}，请结合风险控制审慎评估（已启用模板兜底）。"
        )
        details = (
            "模型输出来自量化因子排序，新闻证据不足或解析失败时不建议单独依赖该信号。\n\n"
            "观察要点：关注量能变化、MA20趋势完整性与事件催化带来的波动。"
        )
        reliability_notes = ["新闻证据不足或LLM解析失败"]
        if reason_text:
            reliability_notes.append(f"兜底原因: {reason_text[:180]}")

    provider_label = (provider or "none").strip() or "none"
    used_provider = f"{provider_label}+template"
    return StockNarrative(
        symbol=symbol,
        summary=summary,
        details=details,
        used_provider=used_provider,
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


def _default_market_fallback(
    market: str,
    provider: str,
    language: str = "zh",
    *,
    asof_date: str | None = None,
    market_snapshot: dict[str, Any] | None = None,
    news_items: list[NewsItem] | None = None,
    reason: str | None = None,
) -> MarketNarrative:
    language = (language or "zh").strip().lower()
    snapshot = market_snapshot or {}
    news = list(news_items or [])[:3]
    up = int(snapshot.get("up_count", 0) or 0)
    down = int(snapshot.get("down_count", 0) or 0)
    flat = int(snapshot.get("flat_count", 0) or 0)
    avg_ret_1d = float(snapshot.get("avg_ret_1d", 0.0) or 0.0)
    median_ret_1d = float(snapshot.get("median_ret_1d", 0.0) or 0.0)
    sample_size = int(snapshot.get("sample_size", 0) or 0)
    mood = _market_mood_text(snapshot, language)
    provider_label = (provider or "none").strip() or "none"
    fallback_provider = f"{provider_label}+template"
    date_text = asof_date or str(snapshot.get("asof_date", "") or "")
    market_label = _market_label(market, language)
    reason_text = (reason or "").strip()

    if language == "en":
        summary = (
            f"{market_label} market is {mood}, breadth up {up}/down {down}/flat {flat}, "
            f"avg 1D return {avg_ret_1d * 100:+.2f}%. Generated by deterministic fallback."
        )
        lines = [
            f"### {market_label} Market Recap ({date_text})".strip(),
            "",
            "#### 1) Market Snapshot",
            f"- Sample size: {sample_size}",
            f"- Breadth: up {up} / down {down} / flat {flat}",
            f"- Average return (1D): {avg_ret_1d * 100:+.2f}%",
            f"- Median return (1D): {median_ret_1d * 100:+.2f}%",
            "",
            "#### 2) Index Watch",
        ]
        benches = snapshot.get("benchmarks") or []
        if isinstance(benches, list) and benches:
            for item in benches[:4]:
                lines.append(
                    "- "
                    + f"{item.get('name')}({item.get('ticker')}): "
                    + f"close={float(item.get('latest_close', 0.0)):.2f}, "
                    + f"1d={float(item.get('ret_1d', 0.0)) * 100:+.2f}%"
                )
        else:
            lines.append("- Benchmark index data unavailable.")
        lines.extend(["", "#### 3) News Clues"])
        if news:
            for i, item in enumerate(news, start=1):
                lines.append(f"- N{i}: {item.title}")
        else:
            lines.append("- No timely market news evidence.")
        lines.extend(
            [
                "",
                "#### 4) Next-session Watchpoints",
                "- Monitor whether benchmark indices can hold above MA20-related trend lines.",
                "- Watch breadth expansion vs. index-only rebound divergence.",
                "- Track policy/macroeconomic headlines and earnings guidance updates.",
                "",
                "#### 5) Risk Notes",
                "- Sample-size bias may distort breadth signal.",
                "- News timing and source quality may lag real-time market shifts.",
            ]
        )
        if reason_text:
            lines.extend(["", f"- Fallback trigger: {reason_text}"])
        details = "\n".join(lines).strip()
    else:
        summary = (
            f"{market_label}市场呈现{mood}，市场宽度上涨{up}/下跌{down}/平盘{flat}，"
            f"样本1日均值{avg_ret_1d * 100:+.2f}%；已启用模板复盘兜底。"
        )
        lines = [
            f"### {market_label}大盘复盘（{date_text}）".strip(),
            "",
            "#### 一、市场快照",
            f"- 样本覆盖: {sample_size} 只",
            f"- 市场宽度: 上涨 {up} / 下跌 {down} / 平盘 {flat}",
            f"- 平均涨跌幅(1D): {avg_ret_1d * 100:+.2f}%",
            f"- 中位涨跌幅(1D): {median_ret_1d * 100:+.2f}%",
            "",
            "#### 二、指数观察",
        ]
        benches = snapshot.get("benchmarks") or []
        if isinstance(benches, list) and benches:
            for item in benches[:4]:
                lines.append(
                    "- "
                    + f"{item.get('name')}({item.get('ticker')}): "
                    + f"收盘={float(item.get('latest_close', 0.0)):.2f}, "
                    + f"1日={float(item.get('ret_1d', 0.0)) * 100:+.2f}%"
                )
        else:
            lines.append("- 暂无可用指数行情（接口波动或节假日）。")
        lines.extend(["", "#### 三、新闻脉络"])
        if news:
            for i, item in enumerate(news, start=1):
                lines.append(f"- N{i}: {item.title}")
        else:
            lines.append("- 暂无高质量时效新闻，结论偏技术面。")
        lines.extend(
            [
                "",
                "#### 四、后市观察点",
                "- 关注基准指数能否延续至MA20上方并放量确认。",
                "- 观察市场宽度是否与指数方向同向扩散，避免“指数涨、个股弱”的背离。",
                "- 跟踪政策/宏观数据与龙头公司业绩指引变化。",
                "",
                "#### 五、风险提示",
                "- 当前样本规模有限，统计结果存在偏差风险。",
                "- 新闻时效与来源覆盖不完整，需配合盘中数据复核。",
            ]
        )
        if reason_text:
            lines.extend(["", f"- 兜底触发原因: {reason_text}"])
        details = "\n".join(lines).strip()

    return MarketNarrative(
        market=market,
        summary=summary,
        details=details,
        used_provider=fallback_provider,
        news_items=news,
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
        logger.warning("LLM failed for %s, use template fallback: %s", prediction.symbol, exc)
        return _default_fallback(
            prediction.symbol,
            prediction,
            provider_used,
            language=language,
            reason=str(exc),
        )

    summary = str(parsed.get("summary") or "").strip()
    details = str(parsed.get("details") or "").strip()
    action_bias = _normalize_bias(str(parsed.get("action_bias") or ""), prediction)
    confidence = _clamp_confidence(parsed.get("confidence"))
    decision = _normalize_decision(str(parsed.get("decision") or ""), prediction)
    decision = calibrate_decision(
        prediction=prediction,
        decision=decision,
        action_bias=action_bias,
        confidence=confidence,
    )
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
        logger.warning("Market LLM failed for %s, use template fallback: %s", market, exc)
        return _default_market_fallback(
            market,
            provider_used,
            language=language,
            asof_date=asof_date,
            market_snapshot=market_snapshot,
            news_items=news_items,
            reason=str(exc),
        )

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
        return _default_market_fallback(
            market,
            provider_used,
            language=language,
            asof_date=asof_date,
            market_snapshot=market_snapshot,
            news_items=news_items,
            reason="LLM output missing required summary/details",
        )

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
