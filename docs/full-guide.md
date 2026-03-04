# llm_stock_report 完整使用指南（中文）

本文档覆盖从 0 到 1 的完整使用流程，包括本地运行、GitHub Actions 自动化、环境变量、数据与模型说明、常见问题排查。

GitHub Actions 详细配置步骤请看：
- [docs/github-actions-setup.md](github-actions-setup.md)

## 1. 项目定位

`llm_stock_report` 是一个研究与信息推送系统，目标是：
- 每周重训 CN/US/HK 三个市场模型
- 每日生成下一交易日预测
- 结合新闻检索与 LLM 输出摘要+详细推理
- 通过 Telegram 自动发送日报

注意：项目仅用于研究和复盘，不包含下单执行。

## 2. 核心流程

一次日报执行（`run_report`）包含以下阶段：
1. 从 `config/universe.yaml` 读取股票池
2. 依据市场抓取历史行情
   - 优先使用本地缓存，按缺口增量补齐
   - 抓取失败会按指数退避重试
3. 计算技术指标与 `next_day_return`
4. 加载最新模型，若缺失/过期则自动重训
5. 输出预测分数、排序、Top/Bottom 标签
6. 新闻检索（Tavily 主，Brave 备）
7. 调用 OpenAI 生成中文摘要与详细推理
8. 生成输出文件并发送 Telegram

模型训练（`run_retrain`）只负责：数据抓取 -> 特征计算 -> 训练 -> 保存模型。

## 3. 目录说明

```text
app/
  common/      配置、日志、数据结构
  data/        行情抓取与代码归一化
  features/    技术指标
  model/       数据构建、训练、预测、模型注册
  news/        Tavily/Brave 搜索与兜底
  llm/         OpenAI 调用与提示词
  report/      摘要/详情渲染与 Telegram 发送
  jobs/        CLI 入口（run_report/run_retrain）

config/
  universe.yaml   股票池（cn/us/hk）
  report.yaml     运行默认参数

outputs/{market}/{date}/
  summary.md
  details.md
  predictions.csv
  run_meta.json

models/{market}/{model_version}/
  model.pkl
  metadata.json
```

## 4. 环境准备

## 4.1 Python 版本
- 推荐 Python 3.11

## 4.2 安装依赖
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4.3 配置环境变量
```bash
cp .env.example .env
```
然后在 `.env` 填写必需项：
- `TAVILY_API_KEY`
- `BRAVE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

LLM 至少配置一组：
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`
- `LLM_PROVIDER=ollama` + `OLLAMA_BASE_URL` + `OLLAMA_MODEL`

可选项：
- `TELEGRAM_MESSAGE_THREAD_ID`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `GEMINI_MODEL`
- `GEMINI_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_BASE_URL`
- `LLM_PROVIDER`
- `MAX_STOCKS_PER_RUN`
- `DETAIL_MESSAGE_CHAR_LIMIT`
- `MODEL_EXPIRE_DAYS`
- `STOCK_LIST_CN` / `STOCK_LIST_US` / `STOCK_LIST_HK`
- `LLM_MAX_RETRIES`
- `LLM_RETRY_BASE_DELAY_SECONDS`
- `LLM_RETRY_MAX_DELAY_SECONDS`
- `LLM_RETRY_JITTER_SECONDS`

## 5. 股票池配置

编辑 `config/universe.yaml`：
```yaml
cn:
  - SH600519
  - SZ000001
  - SZ300750
us:
  - AAPL
  - MSFT
  - NVDA
hk:
  - HK00700
  - HK03690
  - HK09988
```

说明：
- CN 支持 `SHxxxxxx` / `SZxxxxxx` 或 6 位数字（会自动归一化）
- US 用标准 ticker
- HK 支持 `HK00700`、`00700`、`0700`、`700`（会归一化到 `HK00700`）
- 单次运行最多处理 `MAX_STOCKS_PER_RUN`（默认 30）

## 6. 本地运行

## 6.1 手动重训
```bash
python -m app.jobs.run_retrain --market cn --date 2026-03-04
python -m app.jobs.run_retrain --market us --date 2026-03-04
python -m app.jobs.run_retrain --market hk --date 2026-03-04
```

说明：训练前会先检查本地历史缓存（`qlib_data/history/`），只拉取缺失区间并自动淘汰超出保留窗口的旧数据。

## 6.2 生成日报
```bash
python -m app.jobs.run_report --market cn --date 2026-03-04
python -m app.jobs.run_report --market us --date 2026-03-04
python -m app.jobs.run_report --market hk --date 2026-03-04
```

如果只想生成本地文件，不发送 Telegram：
```bash
python -m app.jobs.run_report --market cn --date 2026-03-04 --no-telegram
```

## 7. 输出文件说明

`predictions.csv` 固定列：
- `market`
- `symbol`
- `asof_date`
- `score`
- `rank`
- `side`
- `pred_return`
- `model_version`
- `data_window_start`
- `data_window_end`

`run_meta.json` 固定字段：
- `run_id`
- `market`
- `status`
- `total_symbols`
- `success_symbols`
- `failed_symbols`
- `failed_list`
- `model_version`
- `llm_model`
- `search_provider_primary`
- `search_provider_fallback`
- `start_time`
- `end_time`

## 8. Telegram 推送协议

推送顺序固定：
1. 摘要消息（标题如 `[CN] 2026-03-04 日报摘要`）
2. 逐股票详细消息（标题如 `[CN][SH600519][1/2]`）
3. 大盘复盘消息（标题如 `[CN][MARKET][1/1]`）

细节：
- 单条消息默认最多 3500 字符
- 超长自动切段并标注 `(i/n)`
- Markdown 会做转义，降低格式报错概率

## 9. GitHub Actions 自动化

## 9.1 Workflow 文件
- `.github/workflows/daily_cn.yml`
- `.github/workflows/daily_hk.yml`
- `.github/workflows/daily_us.yml`
- `.github/workflows/weekly_retrain.yml`

## 9.2 定时规则（UTC）
- `daily_cn.yml`: `0 8 * * 1-5`（北京时间工作日 16:00）
- `daily_hk.yml`: `30 9 * * 1-5`（北京时间工作日 17:30）
- `daily_us.yml`: `30 23 * * 1-5`（北京时间次日 07:30）
- 以上为自动定时运行：CN/HK 为北京时间工作日；US 为北京时间周二到周六早晨（覆盖美股前一交易日）
- `weekly_retrain.yml`: 周日定时
- 使用 GitHub Hosted Runner 时，默认无法连到你本机 Ollama；Ollama 建议本地跑或用 self-hosted runner

## 9.3 GitHub Secrets
必需：
- `TAVILY_API_KEY`
- `BRAVE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

可选：
- `OPENAI_API_KEY`（`LLM_PROVIDER=openai` 时必需）
- `GEMINI_API_KEY`（`LLM_PROVIDER=gemini` 时必需）
- `OLLAMA_API_KEY`（仅远程 Ollama 需要）
- `TELEGRAM_MESSAGE_THREAD_ID`

## 9.4 GitHub Variables（可选）
- `MAX_STOCKS_PER_RUN`（默认 30）
- `DETAIL_MESSAGE_CHAR_LIMIT`（默认 3500）
- `MODEL_EXPIRE_DAYS`（默认 8）
- `MARKET_INDEX_FETCH_ENABLED`（默认 true，是否拉取指数基准）
- `STOCK_LIST_CN` / `STOCK_LIST_US` / `STOCK_LIST_HK`（环境变量覆盖股票池）
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `LLM_PROVIDER`（`openai` / `gemini` / `ollama`）
- `GEMINI_MODEL`
- `GEMINI_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_BASE_URL`
- `LLM_MAX_RETRIES`（默认 6）
- `LLM_RETRY_BASE_DELAY_SECONDS`（默认 5）
- `LLM_RETRY_MAX_DELAY_SECONDS`（默认 120）
- `LLM_RETRY_JITTER_SECONDS`（默认 1）
- `MARKET_INDEX_FETCH_ENABLED`（默认 true）

## 9.5 Artifact
每次运行上传：
- `outputs/**`
- `models/**`
保留 14 天。

## 9.6 训练窗口与重试参数（强烈建议了解）

- `TRAINING_WINDOW_DAYS`：训练主窗口（默认 730 天）
- `FEATURE_WARMUP_DAYS`：特征预热窗口（默认 60 天）
- `HISTORY_PRUNE_BUFFER_DAYS`：历史缓存额外保留天数（默认 60 天）
- `INCREMENTAL_OVERLAP_DAYS`：增量拉取时与已有数据重叠天数（默认 7 天）
- `FETCH_MAX_RETRIES`：抓取最大重试次数（默认 5）
- `FETCH_RETRY_BASE_DELAY_SECONDS`：重试基础间隔秒数（默认 15）
- `FETCH_RETRY_MAX_DELAY_SECONDS`：重试最大间隔秒数（默认 300）
- `FETCH_RETRY_JITTER_SECONDS`：重试随机抖动秒数（默认 2）
- `LLM_MAX_RETRIES`：LLM 请求最大重试次数（默认 6）
- `LLM_RETRY_BASE_DELAY_SECONDS`：LLM 重试基础间隔秒数（默认 5）
- `LLM_RETRY_MAX_DELAY_SECONDS`：LLM 重试最大间隔秒数（默认 120）
- `LLM_RETRY_JITTER_SECONDS`：LLM 重试随机抖动秒数（默认 1）
- `LLM_PROVIDER`：LLM 供应商（`openai` / `gemini` / `ollama`）
- `GEMINI_MODEL`：Gemini 模型名（默认 `gemini-2.0-flash`）
- `OLLAMA_MODEL`：Ollama 模型名（默认 `qwen2.5:7b`）
- `OLLAMA_BASE_URL`：Ollama 地址（默认 `http://127.0.0.1:11434`）
- `MARKET_INDEX_FETCH_ENABLED`：是否抓取大盘指数（默认 true）

## 9.7 LLM 输出可靠性增强

提示词与解析层已加入以下约束：
- 必须基于输入数据，不得编造未给出的数值
- 必须输出证据引用编号（`N1/N2...`）或明确“证据不足”
- 必须输出置信度（0-100）与可靠性说明
- 风险点必须具体且可执行（避免泛化结论）

## 10. 常见问题排查

## 10.1 全部股票抓取失败
检查：
- 网络是否可访问对应数据源
- 股票代码格式是否正确
- 目标日期是否为交易日附近

## 10.2 预测为空
检查：
- 历史窗口是否过短（至少覆盖若干周）
- 特征列是否大量缺失
- `predict_frame.csv`（`outputs/debug/...`）是否有行

## 10.3 Telegram 发送失败
检查：
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 是否正确
- bot 是否在群里且有发言权限
- 是否启用了 topic，若启用要配置 `TELEGRAM_MESSAGE_THREAD_ID`

## 10.4 LLM 调用失败
检查：
- `LLM_PROVIDER` 是否配置为 `openai/gemini/ollama`
- 若 `openai`：`OPENAI_API_KEY` / `OPENAI_BASE_URL` 是否正确
- 若 `gemini`：`GEMINI_API_KEY` / `GEMINI_BASE_URL` 是否正确
- 若 `ollama`：`OLLAMA_BASE_URL` 可否访问、`OLLAMA_MODEL` 是否已拉取
- 模型名是否可用

## 10.5 新闻检索为空
- Tavily 配额或网络异常时会自动切 Brave
- 两者都失败时会继续生成报告，但新闻证据为空

## 11. 生产建议

- 每周至少跑一次重训
- 保持股票池稳定，不要频繁大改
- 先在 `--no-telegram` 模式做冒烟测试
- 保留 `outputs` 和 `models` 的历史用于回溯
- 对 `status=partial` 的报告重点检查 `failed_list`
