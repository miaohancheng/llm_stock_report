from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from app.common.schemas import MarketNarrative, PredictionRecord, RunMeta, StockNarrative


def market_tag(market: str) -> str:
    return market.upper()


def _is_en(language: str) -> bool:
    return (language or "").strip().lower() == "en"


def _display_decision(decision: str, language: str) -> str:
    if not _is_en(language):
        return decision
    mapping = {
        "买入": "Buy",
        "观望": "Hold",
        "减仓": "Trim",
        "卖出": "Sell",
        "卖出/观望": "Sell/Hold",
    }
    return mapping.get(decision, decision)


def _display_trend(trend: str, language: str) -> str:
    if not _is_en(language):
        return trend
    mapping = {
        "看多": "Bullish",
        "震荡": "Sideways",
        "看空": "Bearish",
        "强烈看空": "Strong Bearish",
    }
    return mapping.get(trend, trend)


def _display_urgency(urgency: str, language: str) -> str:
    if not _is_en(language):
        return urgency
    mapping = {
        "高": "High",
        "中": "Medium",
        "低": "Low",
    }
    return mapping.get(urgency, urgency)


def _score_to_dashboard(score: float) -> int:
    # Convert z-score-like model output into 0-100 dashboard score.
    value = int(round(50 + score * 15))
    return max(0, min(100, value))


def _decision_icon(decision: str) -> str:
    if decision == "买入":
        return "🟢"
    if decision == "减仓":
        return "🟠"
    if decision in {"卖出", "卖出/观望"}:
        return "🔴"
    return "⚪"


def _default_decision(prediction: PredictionRecord) -> str:
    if prediction.side == "top" and prediction.score > 0.8:
        return "买入"
    if prediction.side == "bottom" and prediction.score < -0.8:
        return "卖出"
    if prediction.side == "bottom":
        return "减仓"
    return "观望"


def _default_trend(prediction: PredictionRecord) -> str:
    if prediction.side == "top":
        return "看多"
    if prediction.side == "bottom":
        return "看空"
    return "震荡"


def _side_label(side: str, language: str) -> str:
    mapping = {
        "top": "Bullish" if _is_en(language) else "偏多",
        "bottom": "Bearish" if _is_en(language) else "偏空",
        "mid": "Neutral" if _is_en(language) else "中性",
    }
    return mapping.get((side or "").strip().lower(), "Neutral" if _is_en(language) else "中性")


def _format_return_pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _market_breadth_comment(up: int, down: int, flat: int, language: str) -> str:
    total = up + down + flat
    if _is_en(language):
        if total <= 0:
            return "Sample is insufficient to infer daily breadth."
        if up > down:
            return "Advancers lead decliners, indicating stronger short-term risk appetite."
        if down > up:
            return "Decliners lead advancers, indicating weaker short-term risk appetite."
        return "Advancers and decliners are balanced, sentiment is neutral."
    if total <= 0:
        return "样本不足，无法判断当日市场宽度。"
    if up > down:
        return "上涨家数占优，市场短线风险偏好偏强。"
    if down > up:
        return "下跌家数占优，市场短线风险偏好偏弱。"
    return "涨跌家数接近，市场情绪偏中性。"


def _explain_feature_metric(key: str, value: float, language: str) -> str:
    if _is_en(language):
        if key == "lookback_days":
            return "Trading-day sample size used for extended context in daily reasoning."
        if key == "ret_lb":
            direction = "positive" if value > 0 else "negative" if value < 0 else "flat"
            return f"Return over the configured lookback window; currently {direction}."
        if key == "range_lb":
            return "High-low price range over lookback window, measuring amplitude."
        if key == "vol_lb":
            return "Annualized realized volatility from lookback daily returns."
        if key == "mdd_lb":
            return "Maximum drawdown within lookback window."
        if key == "vol_ratio_lb":
            return "Latest volume divided by lookback average volume."
        if key == "ret_1":
            direction = "up on the day" if value > 0 else "down on the day" if value < 0 else "flat on the day"
            return f"1-day return for short-term movement; currently {direction}."
        if key == "ret_5":
            direction = "strengthening over 5 days" if value > 0 else "weakening over 5 days" if value < 0 else "sideways over 5 days"
            return f"5-day cumulative return for weekly trend; currently {direction}."
        if key == "ma5_ratio":
            direction = "above" if value > 0 else "below" if value < 0 else "near"
            return f"Distance to MA5; price is {direction} MA5."
        if key == "ma10_ratio":
            direction = "above" if value > 0 else "below" if value < 0 else "near"
            return f"Distance to MA10; price is {direction} MA10."
        if key == "rsi14":
            if value >= 70:
                state = "elevated, watch overheating risk"
            elif value <= 30:
                state = "depressed, watch oversold rebound"
            else:
                state = "in the normal range"
            return f"14-day RSI momentum indicator; currently {state}."
        if key == "macd":
            state = "bullish momentum" if value > 0 else "bearish momentum" if value < 0 else "balanced momentum"
            return f"MACD trend momentum indicator; currently {state}."
        return "Technical indicator snapshot."
    if key == "lookback_days":
        return "用于日度推理扩展上下文的交易日样本数。"
    if key == "ret_lb":
        direction = "区间上涨" if value > 0 else "区间下跌" if value < 0 else "区间持平"
        return f"配置窗口内累计收益率；当前{direction}。"
    if key == "range_lb":
        return "配置窗口内最高/最低价格振幅，用于衡量波动区间。"
    if key == "vol_lb":
        return "配置窗口日收益率年化波动率。"
    if key == "mdd_lb":
        return "配置窗口内最大回撤。"
    if key == "vol_ratio_lb":
        return "最新成交量相对窗口均量的比值。"
    if key == "ret_1":
        direction = "当日上涨" if value > 0 else "当日下跌" if value < 0 else "当日持平"
        return f"1日收益率，反映短线波动；当前{direction}。"
    if key == "ret_5":
        direction = "近5日走强" if value > 0 else "近5日走弱" if value < 0 else "近5日横盘"
        return f"5日累计收益率，反映周内趋势；当前{direction}。"
    if key == "ma5_ratio":
        direction = "高于" if value > 0 else "低于" if value < 0 else "贴近"
        return f"相对5日均线乖离率；价格{direction}MA5。"
    if key == "ma10_ratio":
        direction = "高于" if value > 0 else "低于" if value < 0 else "贴近"
        return f"相对10日均线乖离率；价格{direction}MA10。"
    if key == "rsi14":
        if value >= 70:
            state = "偏高，注意短线过热"
        elif value <= 30:
            state = "偏低，留意超跌反弹"
        else:
            state = "处于常态区间"
        return f"14日RSI动量指标；当前{state}。"
    if key == "macd":
        state = "多头动能" if value > 0 else "空头动能" if value < 0 else "多空均衡"
        return f"MACD趋势动能指标；当前偏{state}。"
    return "技术指标快照。"


def _feature_display_name(key: str, language: str) -> str:
    if _is_en(language):
        mapping = {
            "lookback_days": "Lookback Window",
            "ret_lb": "Lookback Return",
            "range_lb": "Lookback Range",
            "vol_lb": "Lookback Volatility",
            "mdd_lb": "Lookback Max Drawdown",
            "vol_ratio_lb": "Lookback Volume Ratio",
            "ret_1": "1D Return",
            "ret_5": "5D Return",
            "ma5_ratio": "MA5 Distance",
            "ma10_ratio": "MA10 Distance",
            "rsi14": "RSI14",
            "macd": "MACD",
        }
    else:
        mapping = {
            "lookback_days": "回看窗口",
            "ret_lb": "窗口收益率",
            "range_lb": "窗口振幅",
            "vol_lb": "窗口波动率",
            "mdd_lb": "窗口最大回撤",
            "vol_ratio_lb": "窗口量比",
            "ret_1": "1日收益率",
            "ret_5": "5日收益率",
            "ma5_ratio": "MA5乖离率",
            "ma10_ratio": "MA10乖离率",
            "rsi14": "RSI14",
            "macd": "MACD",
        }
    return mapping.get(key, key)


def render_summary_markdown(
    market: str,
    asof_date: str,
    predictions: list[PredictionRecord],
    narratives: dict[str, StockNarrative],
    failed_symbols: list[str],
    market_summary: str | None = None,
    language: str = "zh",
) -> str:
    language = (language or "zh").strip().lower()
    tag = market_tag(market)
    buy = 0
    watch = 0
    trim = 0
    sell = 0

    rows: list[tuple[int, str]] = []
    for p in sorted(predictions, key=lambda x: x.rank):
        n = narratives.get(p.symbol)
        decision = n.decision if n else _default_decision(p)
        trend = n.trend if n else _default_trend(p)
        decision_text = _display_decision(decision, language)
        trend_text = _display_trend(trend, language)
        score_100 = _score_to_dashboard(p.score)
        icon = _decision_icon(decision)
        if _is_en(language):
            pred_text = f"{_format_return_pct(p.pred_return)} ({_side_label(p.side, language)})"
            row_text = f"{icon} {p.symbol}: {decision_text} | Score {score_100} | {trend_text} | Pred {pred_text}"
        else:
            pred_text = f"{_format_return_pct(p.pred_return)}（{_side_label(p.side, language)}）"
            row_text = f"{icon} {p.symbol}: {decision_text} | 评分 {score_100} | {trend_text} | 预测 {pred_text}"
        rows.append(
            (
                score_100,
                row_text,
            )
        )

        if decision == "买入":
            buy += 1
        elif decision == "减仓":
            trim += 1
        elif decision in {"卖出", "卖出/观望"}:
            sell += 1
        else:
            watch += 1

    if _is_en(language):
        lines = [
            f"# 🎯 {asof_date} Decision Dashboard",
            "",
            f"> [{tag}] Analyzed {len(predictions)} symbols | 🟢Buy:{buy} 🟡Hold:{watch} 🟠Trim:{trim} 🔴Sell:{sell}",
        ]
    else:
        lines = [
            f"# 🎯 {asof_date} 决策仪表盘",
            "",
            f"> [{tag}] 共分析 {len(predictions)} 只股票 | 🟢买入:{buy} 🟡观望:{watch} 🟠减仓:{trim} 🔴卖出:{sell}",
        ]
    if failed_symbols:
        lines.append(f"> {'Skipped due to failure' if _is_en(language) else '失败跳过'}: {len(failed_symbols)}")

    lines.extend(["", "## 📊 Analysis Summary" if _is_en(language) else "## 📊 分析结果摘要", ""])
    for _, row in sorted(rows, key=lambda x: x[0], reverse=True):
        lines.append(row)

    if market_summary:
        lines.extend(["", "## 🌐 Market Recap" if _is_en(language) else "## 🌐 大盘复盘", f"- {market_summary}"])

    if failed_symbols:
        lines.extend(["", "## ⚠️ Failed Symbols" if _is_en(language) else "## ⚠️ 失败清单"])
        for s in failed_symbols:
            lines.append(f"- {s}")

    lines.append("")
    lines.append(
        "*For research only. Not investment advice.*"
        if _is_en(language)
        else "*仅供研究参考，不构成投资建议。*"
    )
    return "\n".join(lines)


def render_symbol_detail_markdown(
    market: str,
    asof_date: str,
    prediction: PredictionRecord,
    narrative: StockNarrative,
    language: str = "zh",
) -> str:
    language = (language or "zh").strip().lower()
    tag = market_tag(market)
    score_100 = _score_to_dashboard(prediction.score)
    decision = narrative.decision or _default_decision(prediction)
    trend = narrative.trend or _default_trend(prediction)
    urgency = narrative.urgency or "中"
    decision_text = _display_decision(decision, language)
    trend_text = _display_trend(trend, language)
    urgency_text = _display_urgency(urgency, language)
    icon = _decision_icon(decision)
    if _is_en(language):
        lines = [
            f"# {icon} {prediction.symbol}",
            "",
            f"> [{tag}] {asof_date} | {decision_text} | {trend_text} | Score {score_100}",
            "",
            "## 📰 Key Snapshot",
            f"- 💭 One-line view: {narrative.summary}",
            f"- ⏰ Urgency: {urgency_text}",
            f"- 🔎 News provider: {narrative.used_provider}",
        ]
    else:
        lines = [
            f"# {icon} {prediction.symbol}",
            "",
            f"> [{tag}] {asof_date} | {decision_text} | {trend_text} | 评分 {score_100}",
            "",
            "## 📰 重要信息速览",
            f"- 💭 一句话判断: {narrative.summary}",
            f"- ⏰ 时效性: {urgency_text}",
            f"- 🔎 新闻来源: {narrative.used_provider}",
        ]

    if narrative.catalysts:
        lines.extend(["", "### ✨ Upside Catalysts" if _is_en(language) else "### ✨ 利好催化"])
        for x in narrative.catalysts[:3]:
            lines.append(f"- {x}")

    if narrative.risk_points:
        lines.extend(["", "### 🚨 Risk Alerts" if _is_en(language) else "### 🚨 风险警报"])
        for x in narrative.risk_points[:4]:
            lines.append(f"- {x}")

    if _is_en(language):
        lines.extend(
            [
                "",
                "## 📌 Core Conclusion",
                f"{icon} {decision_text} | {trend_text}",
                f"> One-line decision: {narrative.summary}",
                "",
                "## 📊 Data View",
                f"- Quant score (z): {prediction.score:.4f}",
                f"- Dashboard score: {score_100}/100",
                f"- Predicted return: {prediction.pred_return:.6f}",
                f"- Rank: {prediction.rank}",
                f"- Side label: {prediction.side}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## 📌 核心结论",
                f"{icon} {decision_text} | {trend_text}",
                f"> 一句话决策: {narrative.summary}",
                "",
                "## 📊 数据透视",
                f"- 量化分数(z): {prediction.score:.4f}",
                f"- 量化评分: {score_100}/100",
                f"- 预测收益: {prediction.pred_return:.6f}",
                f"- 排名: {prediction.rank}",
                f"- 多空标签: {prediction.side}",
            ]
        )

    if narrative.latest_close is not None:
        lines.append(
            f"- Latest close: {narrative.latest_close:.4f}"
            if _is_en(language)
            else f"- 最新收盘: {narrative.latest_close:.4f}"
        )

    if narrative.feature_snapshot:
        lines.extend(["", "### Technical Snapshot" if _is_en(language) else "### 技术面快照"])
        for key, value in sorted(narrative.feature_snapshot.items(), key=lambda x: x[0]):
            metric_name = _feature_display_name(key, language)
            explanation = _explain_feature_metric(key, value, language)
            if _is_en(language):
                lines.append(f"- {metric_name}({key}): {value:.6f}. {explanation}")
            else:
                lines.append(f"- {metric_name}({key}): {value:.6f}。{explanation}")

    lines.extend(["", "## 💡 Detailed Reasoning" if _is_en(language) else "## 💡 详细推理", narrative.details])

    if narrative.evidence_used:
        lines.extend(
            [
                "",
                "### Evidence References" if _is_en(language) else "### 证据引用",
                f"- {', '.join(narrative.evidence_used)}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "### Evidence References" if _is_en(language) else "### 证据引用",
                "- None (insufficient news evidence)" if _is_en(language) else "- 无（新闻证据不足）",
            ]
        )

    if narrative.reliability_notes:
        lines.extend(["", "### Reliability Notes" if _is_en(language) else "### 数据可靠性说明"])
        for x in narrative.reliability_notes:
            lines.append(f"- {x}")

    if narrative.news_items:
        lines.extend(["", "## 📢 Latest Updates" if _is_en(language) else "## 📢 最新动态"])
        for item in narrative.news_items:
            lines.append(f"- [{item.title}]({item.url})")

    if _is_en(language):
        lines.extend(
            [
                "",
                "---",
                "",
                "## 🎯 Action Plan (Research Reference)",
                f"- No position: follow the {decision_text} view and wait for trend/volume confirmation.",
                f"- Holding position: if price action deviates from {trend_text}, prioritize risk control.",
                "",
                "*For research only. Not investment advice.*",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "---",
                "",
                "## 🎯 作战计划（研究参考）",
                f"- 空仓者: 以 {decision_text} 观点为主，关注放量与趋势确认后再行动。",
                f"- 持仓者: 若走势偏离 {trend_text} 预期，优先执行风险控制。",
                "",
                "*仅供研究参考，不构成投资建议。*",
            ]
        )
    return "\n".join(lines)


def render_market_detail_markdown(
    market: str,
    asof_date: str,
    market_snapshot: dict,
    narrative: MarketNarrative,
    language: str = "zh",
) -> str:
    language = (language or "zh").strip().lower()
    tag = market_tag(market)
    up = int(market_snapshot.get("up_count", 0))
    down = int(market_snapshot.get("down_count", 0))
    flat = int(market_snapshot.get("flat_count", 0))
    avg_ret_1d = float(market_snapshot.get("avg_ret_1d", 0.0))
    median_ret_1d = float(market_snapshot.get("median_ret_1d", 0.0))
    if _is_en(language):
        lines = [
            f"# 🌐 [{tag}] {asof_date} Market Recap",
            "",
            "## Market Snapshot",
            f"- News provider: {narrative.used_provider}",
            f"- Sample coverage: {int(market_snapshot.get('sample_size', 0))} symbols (for breadth stats)",
            f"- Market breadth: up {up} / down {down} / flat {flat}",
            f"- Average return (1D): {avg_ret_1d * 100:+.2f}%",
            f"- Median return (1D): {median_ret_1d * 100:+.2f}%",
            f"- Quick take: {_market_breadth_comment(up, down, flat, language)}",
            "",
            "## Summary",
            narrative.summary,
            "",
            "## Detailed Reasoning",
            narrative.details,
        ]
    else:
        lines = [
            f"# 🌐 [{tag}] {asof_date} 大盘复盘",
            "",
            "## 市场快照",
            f"- 新闻来源: {narrative.used_provider}",
            f"- 样本覆盖: {int(market_snapshot.get('sample_size', 0))} 只股票（用于宽度统计）",
            f"- 市场宽度: 上涨 {up} / 下跌 {down} / 平盘 {flat}（涨跌家数）",
            f"- 平均涨跌幅: {avg_ret_1d * 100:+.2f}%（样本算术平均）",
            f"- 中位涨跌幅: {median_ret_1d * 100:+.2f}%（样本中位数）",
            f"- 快速解读: {_market_breadth_comment(up, down, flat, language)}",
            "",
            "## 摘要",
            narrative.summary,
            "",
            "## 详细推理",
            narrative.details,
        ]

    benchmarks = market_snapshot.get("benchmarks", []) or []
    if benchmarks:
        lines.extend(["", "## Benchmarks" if _is_en(language) else "## 基准指数"])
        for item in benchmarks:
            lines.append(
                "- "
                + f"{item.get('name')}({item.get('ticker')}): "
                + f"close={float(item.get('latest_close', 0.0)):.2f}, "
                + f"1d={float(item.get('ret_1d', 0.0)):.4f}, "
                + f"5d={float(item.get('ret_5d', 0.0)):.4f}"
            )

    if narrative.news_items:
        lines.extend(["", "## News Evidence" if _is_en(language) else "## 新闻证据"])
        for item in narrative.news_items:
            lines.append(f"- [{item.title}]({item.url})")

    gainers = market_snapshot.get("gainers", []) or []
    losers = market_snapshot.get("losers", []) or []
    if gainers:
        lines.extend(["", "## Top Gainers (Sample)" if _is_en(language) else "## 样本领涨"])
        for x in gainers:
            lines.append(f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}")
    if losers:
        lines.extend(["", "## Top Losers (Sample)" if _is_en(language) else "## 样本领跌"])
        for x in losers:
            lines.append(f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}")

    lines.append("")
    lines.append(
        "*For research only. Not investment advice.*"
        if _is_en(language)
        else "*仅供研究参考，不构成投资建议。*"
    )
    return "\n".join(lines)


def write_outputs(
    output_dir: Path,
    summary_markdown: str,
    details_markdown: str,
    predictions: list[PredictionRecord],
    run_meta: RunMeta,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "summary.md").write_text(summary_markdown, encoding="utf-8")
    (output_dir / "details.md").write_text(details_markdown, encoding="utf-8")

    df = pd.DataFrame([p.to_csv_row() for p in predictions])
    columns = [
        "market",
        "symbol",
        "asof_date",
        "score",
        "rank",
        "side",
        "pred_return",
        "model_version",
        "data_window_start",
        "data_window_end",
    ]
    if df.empty:
        df = pd.DataFrame(columns=columns)
    else:
        df = df[columns]
    df.to_csv(output_dir / "predictions.csv", index=False)

    (output_dir / "run_meta.json").write_text(
        json.dumps(asdict(run_meta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
