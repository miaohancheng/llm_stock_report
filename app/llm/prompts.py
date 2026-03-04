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

SYSTEM_PROMPT_EN = (
    "You are a rigorous equity research analyst."
    "Use only the provided structured inputs and never fabricate facts."
    "Do not provide guaranteed returns, certainty claims, or insider-information style advice."
    "If evidence is insufficient, explicitly state uncertainty sources."
    "Output must be strict JSON without markdown code fences."
)


def get_system_prompt(language: str = "zh") -> str:
    return SYSTEM_PROMPT_EN if (language or "").strip().lower() == "en" else SYSTEM_PROMPT


def build_stock_reasoning_prompt(
    market: str,
    symbol: str,
    prediction: PredictionRecord,
    latest_close: float,
    feature_snapshot: dict[str, float],
    news_items: list[NewsItem],
    language: str = "zh",
) -> str:
    language = (language or "zh").strip().lower()
    ordered_features = sorted(feature_snapshot.items(), key=lambda x: x[0])
    feature_lines = [f"- {k}: {v:.6f}" for k, v in ordered_features]
    feature_block = "\n".join(feature_lines) if feature_lines else (
        "- no technical features available" if language == "en" else "- 无可用技术特征"
    )

    news_lines = []
    for idx, item in enumerate(news_items, start=1):
        if language == "en":
            news_lines.append(
                f"[N{idx}] Title: {item.title}\n"
                f"      Snippet: {item.snippet[:180]}\n"
                f"      URL: {item.url}"
            )
        else:
            news_lines.append(
                f"[N{idx}] 标题: {item.title}\n"
                f"      摘要: {item.snippet[:180]}\n"
                f"      链接: {item.url}"
            )

    news_block = "\n".join(news_lines) if news_lines else ("No related news" if language == "en" else "无相关新闻")

    if language == "en":
        return f"""
Generate an English equity brief from the inputs below. Keep it explainable, traceable, and conservative.

Market: {market}
Symbol: {symbol}
Close: {latest_close:.4f}
Predicted score (score): {prediction.score:.6f}
Predicted return (pred_return): {prediction.pred_return:.6f}
Rank: {prediction.rank}
Long/short label (side): {prediction.side}

Technical snapshot:
{feature_block}

News evidence:
{news_block}

Output requirements (all required):
1) summary <= 50 words, include directional view and uncertainty note
2) details must cover:
   - technical conclusion (cite at least 2 indicators)
   - news conclusion (if no news, state "insufficient news evidence")
   - risk control trigger or monitor points
3) risk_points must be 2-4 concrete risks
4) decision must be one of: Buy|Hold|Trim|Sell|Sell/Hold
5) trend must be one of: Bullish|Sideways|Bearish|Strong Bearish
6) urgency must be one of: High|Medium|Low
7) catalysts must include 1-3 upside catalysts (can be empty)
8) confidence must be an integer 0-100
9) evidence_used only allows N1/N2... references from provided news; empty array if none
10) reliability_notes should explain evidence/data reliability limits
11) If earnings/guidance/results appear in news, prioritize them in details and catalysts

Output JSON only:
{{
  "summary": "single sentence summary",
  "details": "2-4 paragraph analysis",
  "decision": "Buy|Hold|Trim|Sell|Sell/Hold",
  "trend": "Bullish|Sideways|Bearish|Strong Bearish",
  "urgency": "High|Medium|Low",
  "risk_points": ["risk 1", "risk 2"],
  "catalysts": ["catalyst 1", "catalyst 2"],
  "action_bias": "Bullish|Neutral|Bearish",
  "confidence": 66,
  "evidence_used": ["N1", "N2"],
  "reliability_notes": ["note 1", "note 2"]
}}
""".strip()

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
4) decision 必须是: 买入|观望|减仓|卖出|卖出/观望
5) trend 必须是: 看多|震荡|看空|强烈看空
6) urgency 必须是: 高|中|低
7) catalysts 给出 1-3 条利好/催化点（可为空数组）
8) confidence 为 0-100 的整数，体现当前结论可靠性
9) evidence_used 只允许填 [N1], [N2] 这类已提供编号；无新闻则填空数组
10) reliability_notes 给出数据可靠性说明（例如“仅技术面”“新闻时效不足”）
11) 如果新闻中包含财报/业绩/指引信息，优先在 details 与 catalysts 中体现

仅输出 JSON，格式如下：
{{
  "summary": "一句话摘要，不超过50字",
  "details": "2-4段详细分析，必须包含技术面+消息面+风险",
  "decision": "买入|观望|减仓|卖出|卖出/观望",
  "trend": "看多|震荡|看空|强烈看空",
  "urgency": "高|中|低",
  "risk_points": ["风险1", "风险2"],
  "catalysts": ["催化1", "催化2"],
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
    language: str = "zh",
) -> str:
    language = (language or "zh").strip().lower()
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
    benchmark_block = "\n".join(benchmark_lines) if benchmark_lines else (
        "- no benchmark index data available" if language == "en" else "- 无可用基准指数数据"
    )

    gainers = market_snapshot.get("gainers", []) or []
    losers = market_snapshot.get("losers", []) or []
    if language == "en":
        breadth_block = (
            f"sample={int(market_snapshot.get('sample_size', 0))}, "
            f"up={int(market_snapshot.get('up_count', 0))}, "
            f"down={int(market_snapshot.get('down_count', 0))}, "
            f"flat={int(market_snapshot.get('flat_count', 0))}, "
            f"avg_ret_1d={float(market_snapshot.get('avg_ret_1d', 0.0)):.4f}, "
            f"median_ret_1d={float(market_snapshot.get('median_ret_1d', 0.0)):.4f}"
        )
    else:
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
    ) or ("- None" if language == "en" else "- 无")
    losers_block = "\n".join(
        [f"- {x.get('symbol')}: {float(x.get('ret_1d', 0.0)):.4f}" for x in losers]
    ) or ("- None" if language == "en" else "- 无")

    news_lines = []
    for idx, item in enumerate(news_items, start=1):
        if language == "en":
            news_lines.append(
                f"[N{idx}] Title: {item.title}\n"
                f"      Snippet: {item.snippet[:180]}\n"
                f"      URL: {item.url}"
            )
        else:
            news_lines.append(
                f"[N{idx}] 标题: {item.title}\n"
                f"      摘要: {item.snippet[:180]}\n"
                f"      链接: {item.url}"
            )
    news_block = "\n".join(news_lines) if news_lines else ("No related news" if language == "en" else "无相关新闻")

    snapshot_json = json.dumps(market_snapshot, ensure_ascii=False)

    if language == "en":
        return f"""
Generate an English market recap for {market.upper()} from the inputs below. Keep it objective and traceable.

Date: {asof_date}
Market: {market}

Benchmarks:
{benchmark_block}

Breadth:
{breadth_block}

Top gainers:
{gainers_block}

Top losers:
{losers_block}

News evidence:
{news_block}

Structured snapshot(JSON):
{snapshot_json}

Output requirements (all required):
1) summary <= 70 words with market risk preference and uncertainty
2) details must include:
   - benchmark + breadth conclusions
   - news impact and evidence boundary
   - 2-3 next-session watchpoints
3) risk_points: 2-4 concrete risks
4) confidence: integer 0-100
5) evidence_used: only N1/N2... references; empty array if none
6) reliability_notes: reliability caveats

Output JSON only:
{{
  "summary": "single sentence summary",
  "details": "2-4 paragraph recap",
  "risk_points": ["risk 1", "risk 2"],
  "action_bias": "Bullish|Neutral|Bearish",
  "confidence": 62,
  "evidence_used": ["N1"],
  "reliability_notes": ["note 1", "note 2"]
}}
""".strip()

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
