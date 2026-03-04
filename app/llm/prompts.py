from __future__ import annotations

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
{"\n".join(feature_lines)}

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
