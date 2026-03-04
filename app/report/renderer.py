from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from app.common.schemas import MarketNarrative, PredictionRecord, RunMeta, StockNarrative


def market_tag(market: str) -> str:
    return market.upper()


def render_summary_markdown(
    market: str,
    asof_date: str,
    predictions: list[PredictionRecord],
    narratives: dict[str, StockNarrative],
    failed_symbols: list[str],
    market_summary: str | None = None,
) -> str:
    tag = market_tag(market)
    top = [p for p in predictions if p.side == "top"]
    bottom = [p for p in predictions if p.side == "bottom"]

    lines = [
        f"# [{tag}] {asof_date} 日报摘要",
        "",
        f"- 总股票数: {len(predictions) + len(failed_symbols)}",
        f"- 成功分析: {len(predictions)}",
        f"- 失败跳过: {len(failed_symbols)}",
        "",
        "## Top 信号",
    ]

    for p in top[:10]:
        summary = narratives.get(p.symbol).summary if p.symbol in narratives else ""
        lines.append(f"- {p.symbol}: score={p.score:.3f}, pred_return={p.pred_return:.4f} | {summary}")

    lines.extend(["", "## Bottom 信号"])
    for p in bottom[:10]:
        summary = narratives.get(p.symbol).summary if p.symbol in narratives else ""
        lines.append(f"- {p.symbol}: score={p.score:.3f}, pred_return={p.pred_return:.4f} | {summary}")

    if failed_symbols:
        lines.extend(["", "## 失败清单"])
        for s in failed_symbols:
            lines.append(f"- {s}")

    if market_summary:
        lines.extend(["", "## 大盘复盘", f"- {market_summary}"])

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
    lines = [
        f"# [{tag}] {asof_date} {prediction.symbol}",
        "",
        f"- score: {prediction.score:.4f}",
        f"- pred_return: {prediction.pred_return:.6f}",
        f"- rank: {prediction.rank}",
        f"- side: {prediction.side}",
        f"- news_provider: {narrative.used_provider}",
        "",
        "## 摘要",
        narrative.summary,
        "",
        "## 详细推理",
        narrative.details,
    ]

    if narrative.news_items:
        lines.extend(["", "## 新闻证据"])
        for item in narrative.news_items:
            lines.append(f"- [{item.title}]({item.url})")

    lines.append("")
    lines.append("*仅供研究参考，不构成投资建议。*")
    return "\n".join(lines)


def render_market_detail_markdown(
    market: str,
    asof_date: str,
    market_snapshot: dict,
    narrative: MarketNarrative,
) -> str:
    tag = market_tag(market)
    lines = [
        f"# [{tag}] {asof_date} 大盘复盘",
        "",
        f"- news_provider: {narrative.used_provider}",
        f"- sample_size: {int(market_snapshot.get('sample_size', 0))}",
        f"- breadth: up={int(market_snapshot.get('up_count', 0))}, down={int(market_snapshot.get('down_count', 0))}, flat={int(market_snapshot.get('flat_count', 0))}",
        f"- avg_ret_1d: {float(market_snapshot.get('avg_ret_1d', 0.0)):.4f}",
        f"- median_ret_1d: {float(market_snapshot.get('median_ret_1d', 0.0)):.4f}",
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
