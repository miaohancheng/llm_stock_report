from __future__ import annotations

import json

from app.common.schemas import NewsItem, PredictionRecord


SYSTEM_PROMPT = (
    "你是一名严谨的中文股票策略研究员。"
    "你只能基于用户给出的结构化输入作答，禁止编造数据。"
    "不允许输出买卖保证、收益承诺、内幕信息或确定性措辞。"
    "若信息不足必须明确写出不确定性来源。"
    "输出必须是严格 JSON，不包含 markdown 代码块。"
)


def build_stock_reasoning_prompt(
    market: str,
    symbol: str,
    prediction: PredictionRecord,
    latest_close: float,
    feature_snapshot: dict[str, float],
    news_items: list[NewsItem],
) -> str:
    ordered_features = sorted(feature_snapshot.items(), key=lambda x: x[0])
    feature_lines = [f"- {k}: {v:.6f}" for k, v in ordered_features]
    feature_block = "\n".join(feature_lines) if feature_lines else "- 无可用技术特征"

    news_lines = []
    for idx, item in enumerate(news_items, start=1):
        news_lines.append(
            f"[N{idx}] 标题: {item.title}\n"
            f"      摘要: {item.snippet[:180]}\n"
            f"      链接: {item.url}"
        )

    news_block = "\n".join(news_lines) if news_lines else "无相关新闻"

    return f"""
请基于以下输入生成中文研究简报，并遵守“可解释、可追溯、不过度结论”的原则。

市场: {market}
股票: {symbol}
收盘价: {latest_close:.4f}
预测分数(score): {prediction.score:.6f}
预测收益(pred_return): {prediction.pred_return:.6f}
排名: {prediction.rank}
	多空标签(side): {prediction.side}

	技术面快照:
	{feature_block}

新闻证据:
{news_block}

输出要求（必须同时满足）：
1) summary 不超过 50 字，包含方向判断与不确定性提示
2) details 必须覆盖：
   - 技术面结论（至少引用2个指标）
   - 消息面结论（如无新闻需明确“新闻证据不足”）
   - 风险控制（触发条件或观察点）
3) risk_points 必须给出 2-4 条具体风险，不要写空泛句
4) confidence 为 0-100 的整数，体现当前结论可靠性
5) evidence_used 只允许填 [N1], [N2] 这类已提供编号；无新闻则填空数组
6) reliability_notes 给出数据可靠性说明（例如“仅技术面”“新闻时效不足”）

仅输出 JSON，格式如下：
{{
  "summary": "一句话摘要，不超过50字",
  "details": "2-4段详细分析，必须包含技术面+消息面+风险",
  "risk_points": ["风险1", "风险2"],
  "action_bias": "偏多|中性|偏空",
  "confidence": 66,
  "evidence_used": ["N1", "N2"],
  "reliability_notes": ["说明1", "说明2"]
}}
""".strip()


def build_market_reasoning_prompt(
    market: str,
    asof_date: str,
    market_snapshot: dict,
    news_items: list[NewsItem],
) -> str:
    benchmark_lines: list[str] = []
    for item in market_snapshot.get("benchmarks", []):
        benchmark_lines.append(
            (
                f"- {item.get('name')}({item.get('ticker')}): "
                f"close={float(item.get('latest_close', 0.0)):.2f}, "
                f"1d={float(item.get('ret_1d', 0.0)):.4f}, "
                f"5d={float(item.get('ret_5d', 0.0)):.4f}, "
                f"ma20_ratio={float(item.get('ma20_ratio', 0.0)):.4f}"
            )
        )
    benchmark_block = "\n".join(benchmark_lines) if benchmark_lines else "- 无可用基准指数数据"

    gainers = market_snapshot.get("gainers", []) or []
    losers = market_snapshot.get("losers", []) or []
    breadth_block = (
        f"样本数={int(market_snapshot.get('sample_size', 0))}, "
        f"上涨={int(market_snapshot.get('up_count', 0))}, "
        f"下跌={int(market_snapshot.get('down_count', 0))}, "
        f"平盘={int(market_snapshot.get('flat_count', 0))}, "
        f"均值涨跌={float(market_snapshot.get('avg_ret_1d', 0.0)):.4f}, "
        f"中位涨跌={float(market_snapshot.get('median_ret_1d', 0.0)):.4f}"
    )
    gainers_block = "\n".join(
        [f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}" for x in gainers]
    ) or "- 无"
    losers_block = "\n".join(
        [f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}" for x in losers]
    ) or "- 无"

    news_lines = []
    for idx, item in enumerate(news_items, start=1):
        news_lines.append(
            f"[N{idx}] 标题: {item.title}\n"
            f"      摘要: {item.snippet[:180]}\n"
            f"      链接: {item.url}"
        )
    news_block = "\n".join(news_lines) if news_lines else "无相关新闻"

    snapshot_json = json.dumps(market_snapshot, ensure_ascii=False)

    return f"""
请基于以下输入生成{market.upper()}市场的大盘复盘，要求“客观、可追溯、不过度结论”。

日期: {asof_date}
市场: {market}

基准指数:
{benchmark_block}

样本宽度:
{breadth_block}

样本领涨:
{gainers_block}

样本领跌:
{losers_block}

新闻证据:
{news_block}

结构化快照(JSON):
{snapshot_json}

输出要求（必须同时满足）：
1) summary 不超过 70 字，给出市场风险偏好判断与不确定性
2) details 必须包含：
   - 指数/宽度两方面结论
   - 新闻面影响与证据边界
   - 次日观察点（2-3条）
3) risk_points 必须给出 2-4 条具体风险
4) confidence 为 0-100 的整数
5) evidence_used 仅允许填 N1/N2...；无新闻则空数组
6) reliability_notes 给出数据可靠性说明

仅输出 JSON，格式如下：
{{
  "summary": "一句话摘要，不超过70字",
  "details": "2-4段大盘复盘",
  "risk_points": ["风险1", "风险2"],
  "action_bias": "偏多|中性|偏空",
  "confidence": 62,
  "evidence_used": ["N1"],
  "reliability_notes": ["说明1", "说明2"]
}}
""".strip()
