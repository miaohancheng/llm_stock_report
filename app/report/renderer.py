from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from app.common.schemas import MarketNarrative, PredictionRecord, RunMeta, StockNarrative


def market_tag(market: str) -> str:
    return market.upper()


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


def _side_label(side: str) -> str:
    mapping = {
        "top": "偏多",
        "bottom": "偏空",
        "mid": "中性",
    }
    return mapping.get((side or "").strip().lower(), "中性")


def _format_return_pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _market_breadth_comment(up: int, down: int, flat: int) -> str:
    total = up + down + flat
    if total <= 0:
        return "样本不足，无法判断当日市场宽度。"
    if up > down:
        return "上涨家数占优，市场短线风险偏好偏强。"
    if down > up:
        return "下跌家数占优，市场短线风险偏好偏弱。"
    return "涨跌家数接近，市场情绪偏中性。"


def _explain_feature_metric(key: str, value: float) -> str:
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


def _feature_display_name(key: str) -> str:
    mapping = {
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
) -> str:
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
        score_100 = _score_to_dashboard(p.score)
        icon = _decision_icon(decision)
        pred_text = f"{_format_return_pct(p.pred_return)}（{_side_label(p.side)}）"
        rows.append(
            (
                score_100,
                f"{icon} {p.symbol}: {decision} | 评分 {score_100} | {trend} | 预测 {pred_text}",
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

    lines = [
        f"# 🎯 {asof_date} 决策仪表盘",
        "",
        f"> [{tag}] 共分析 {len(predictions)} 只股票 | 🟢买入:{buy} 🟡观望:{watch} 🟠减仓:{trim} 🔴卖出:{sell}",
    ]
    if failed_symbols:
        lines.append(f"> 失败跳过: {len(failed_symbols)}")

    lines.extend(["", "## 📊 分析结果摘要", ""])
    for _, row in sorted(rows, key=lambda x: x[0], reverse=True):
        lines.append(row)

    if market_summary:
        lines.extend(["", "## 🌐 大盘复盘", f"- {market_summary}"])

    if failed_symbols:
        lines.extend(["", "## ⚠️ 失败清单"])
        for s in failed_symbols:
            lines.append(f"- {s}")

    lines.append("")
    lines.append("*仅供研究参考，不构成投资建议。*")
    return "\n".join(lines)


def render_symbol_detail_markdown(
    market: str,
    asof_date: str,
    prediction: PredictionRecord,
    narrative: StockNarrative,
) -> str:
    tag = market_tag(market)
    score_100 = _score_to_dashboard(prediction.score)
    decision = narrative.decision or _default_decision(prediction)
    trend = narrative.trend or _default_trend(prediction)
    urgency = narrative.urgency or "中"
    icon = _decision_icon(decision)

    lines = [
        f"# {icon} {prediction.symbol}",
        "",
        f"> [{tag}] {asof_date} | {decision} | {trend} | 评分 {score_100}",
        "",
        "## 📰 重要信息速览",
        f"- 💭 一句话判断: {narrative.summary}",
        f"- ⏰ 时效性: {urgency}",
        f"- 🔎 新闻来源: {narrative.used_provider}",
    ]

    if narrative.catalysts:
        lines.extend(["", "### ✨ 利好催化"])
        for x in narrative.catalysts[:3]:
            lines.append(f"- {x}")

    if narrative.risk_points:
        lines.extend(["", "### 🚨 风险警报"])
        for x in narrative.risk_points[:4]:
            lines.append(f"- {x}")

    lines.extend(
        [
            "",
            "## 📌 核心结论",
            f"{icon} {decision} | {trend}",
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
        lines.append(f"- 最新收盘: {narrative.latest_close:.4f}")

    if narrative.feature_snapshot:
        lines.extend(["", "### 技术面快照"])
        for key, value in sorted(narrative.feature_snapshot.items(), key=lambda x: x[0]):
            metric_name = _feature_display_name(key)
            explanation = _explain_feature_metric(key, value)
            lines.append(f"- {metric_name}({key}): {value:.6f}。{explanation}")

    lines.extend(["", "## 💡 详细推理", narrative.details])

    if narrative.evidence_used:
        lines.extend(["", "### 证据引用", f"- {', '.join(narrative.evidence_used)}"])
    else:
        lines.extend(["", "### 证据引用", "- 无（新闻证据不足）"])

    if narrative.reliability_notes:
        lines.extend(["", "### 数据可靠性说明"])
        for x in narrative.reliability_notes:
            lines.append(f"- {x}")

    if narrative.news_items:
        lines.extend(["", "## 📢 最新动态"])
        for item in narrative.news_items:
            lines.append(f"- [{item.title}]({item.url})")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 🎯 作战计划（研究参考）",
            f"- 空仓者: 以 {decision} 观点为主，关注放量与趋势确认后再行动。",
            f"- 持仓者: 若走势偏离 {trend} 预期，优先执行风险控制。",
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
) -> str:
    tag = market_tag(market)
    up = int(market_snapshot.get("up_count", 0))
    down = int(market_snapshot.get("down_count", 0))
    flat = int(market_snapshot.get("flat_count", 0))
    avg_ret_1d = float(market_snapshot.get("avg_ret_1d", 0.0))
    median_ret_1d = float(market_snapshot.get("median_ret_1d", 0.0))
    lines = [
        f"# 🌐 [{tag}] {asof_date} 大盘复盘",
        "",
        "## 市场快照",
        f"- 新闻来源: {narrative.used_provider}",
        f"- 样本覆盖: {int(market_snapshot.get('sample_size', 0))} 只股票（用于宽度统计）",
        f"- 市场宽度: 上涨 {up} / 下跌 {down} / 平盘 {flat}（涨跌家数）",
        f"- 平均涨跌幅: {avg_ret_1d * 100:+.2f}%（样本算术平均）",
        f"- 中位涨跌幅: {median_ret_1d * 100:+.2f}%（样本中位数）",
        f"- 快速解读: {_market_breadth_comment(up, down, flat)}",
        "",
        "## 摘要",
        narrative.summary,
        "",
        "## 详细推理",
        narrative.details,
    ]

    benchmarks = market_snapshot.get("benchmarks", []) or []
    if benchmarks:
        lines.extend(["", "## 基准指数"])
        for item in benchmarks:
            lines.append(
                "- "
                + f"{item.get('name')}({item.get('ticker')}): "
                + f"close={float(item.get('latest_close', 0.0)):.2f}, "
                + f"1d={float(item.get('ret_1d', 0.0)):.4f}, "
                + f"5d={float(item.get('ret_5d', 0.0)):.4f}"
            )

    if narrative.news_items:
        lines.extend(["", "## 新闻证据"])
        for item in narrative.news_items:
            lines.append(f"- [{item.title}]({item.url})")

    gainers = market_snapshot.get("gainers", []) or []
    losers = market_snapshot.get("losers", []) or []
    if gainers:
        lines.extend(["", "## 样本领涨"])
        for x in gainers:
            lines.append(f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}")
    if losers:
        lines.extend(["", "## 样本领跌"])
        for x in losers:
            lines.append(f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}")

    lines.append("")
    lines.append("*仅供研究参考，不构成投资建议。*")
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
