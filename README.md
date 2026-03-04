# llm_stock_report

LLM daily stock summary + next-day prediction for CN/US/HK markets, with scheduled GitHub Actions and Telegram delivery.

简体中文 | [English](#english)

- 中文完整使用文档: [docs/full-guide.md](docs/full-guide.md)
- English full guide: [docs/full-guide_EN.md](docs/full-guide_EN.md)
- GitHub Actions 配置手册（中文）: [docs/github-actions-setup.md](docs/github-actions-setup.md)
- GitHub Actions setup guide (EN): [docs/github-actions-setup_EN.md](docs/github-actions-setup_EN.md)

## 中文

### 项目功能
- A股使用 `AKShare`，美股/港股使用 `yfinance` 拉取历史行情
- 本地历史缓存 + 增量补齐（避免每次全量拉取）
- 生成技术指标与 `next_day_return` 标签
- 每周训练（Qlib 风格 LightGBM）+ 每日推理
- 抓取失败自动重试（长间隔指数退避，适配反爬限流）
- Tavily 主搜索、Brave 兜底新闻搜索
- 支持 OpenAI / Gemini / Ollama 生成中文摘要与详细推理
- 提示词强化：证据引用、置信度、可靠性说明、风险约束
- Telegram 推送顺序：摘要 1 条 -> 按股票详细分段
- 输出目录：`outputs/{market}/{date}/`

### 快速开始
1. 安装依赖
```bash
python -m pip install -r requirements.txt
```
2. 配置股票池
- 编辑 `config/universe.yaml`
3. 配置环境变量
- 复制 `.env.example` 到 `.env` 并填写密钥
4. 手动训练
```bash
python -m app.jobs.run_retrain --market cn --date 2026-03-04
python -m app.jobs.run_retrain --market us --date 2026-03-04
python -m app.jobs.run_retrain --market hk --date 2026-03-04
```
5. 生成日报
```bash
python -m app.jobs.run_report --market cn --date 2026-03-04
python -m app.jobs.run_report --market us --date 2026-03-04
python -m app.jobs.run_report --market hk --date 2026-03-04
```

### 必需环境变量
- `TAVILY_API_KEY`
- `BRAVE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

LLM 至少配置一组：
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`
- `LLM_PROVIDER=ollama` + `OLLAMA_BASE_URL` + `OLLAMA_MODEL`（本地默认可直接用）

### 关键可选参数（推荐配置）
- `LLM_PROVIDER`（`openai` / `gemini` / `ollama`）
- `STOCK_LIST_CN` / `STOCK_LIST_US` / `STOCK_LIST_HK`（环境变量覆盖股票池）
- `TRAINING_WINDOW_DAYS`（训练窗口天数，默认 730）
- `FEATURE_WARMUP_DAYS`（特征预热天数，默认 60）
- `FETCH_MAX_RETRIES`（抓取最大重试次数，默认 5）
- `FETCH_RETRY_BASE_DELAY_SECONDS`（重试基础间隔，默认 15 秒）
- `FETCH_RETRY_MAX_DELAY_SECONDS`（重试最大间隔，默认 300 秒）
- `LLM_MAX_RETRIES`（LLM 最大重试次数，默认 6）
- `LLM_RETRY_BASE_DELAY_SECONDS`（LLM 重试基础间隔，默认 5 秒）
- `LLM_RETRY_MAX_DELAY_SECONDS`（LLM 重试最大间隔，默认 120 秒）
- `GEMINI_MODEL`（默认 `gemini-2.0-flash`）
- `OLLAMA_MODEL`（默认 `qwen2.5:7b`）
- `OLLAMA_BASE_URL`（默认 `http://127.0.0.1:11434`）

### GitHub Actions
- `daily_cn.yml`：UTC `0 8 * * 1-5`（北京时间工作日 16:00）
- `daily_hk.yml`：UTC `30 9 * * 1-5`（北京时间工作日 17:30）
- `daily_us.yml`：UTC `30 23 * * 1-5`（北京时间次日 07:30）
- 以上定时均为自动运行；CN/HK 在北京时间工作日触发，US 在北京时间周二到周六早晨触发（覆盖美股前一交易日）
- GitHub Hosted Runner 默认无法访问你本机 Ollama；Ollama 仅建议本地运行或 self-hosted runner 使用
- `weekly_retrain.yml`：每周重训 CN/US/HK

### 输出文件
- `summary.md`
- `details.md`
- `predictions.csv`
- `run_meta.json`

### 文档
- 中文完整指南: [docs/full-guide.md](docs/full-guide.md)
- 英文完整指南: [docs/full-guide_EN.md](docs/full-guide_EN.md)
- GitHub Actions 配置手册: [docs/github-actions-setup.md](docs/github-actions-setup.md)

---

## English

### Features
- Fetches CN history via `AKShare` and US/HK history via `yfinance`
- Uses local history cache with incremental top-up (instead of full re-download each run)
- Builds technical factors and `next_day_return` labels
- Weekly retraining (Qlib-style LightGBM) and daily inference
- Adds long-interval exponential retry for data fetch failures
- News search with Tavily primary and Brave fallback
- Chinese report generation with OpenAI / Gemini / Ollama
- Prompt hardening for reliability: evidence refs, confidence score, reliability notes
- Telegram send order: one summary message, then per-symbol chunked details
- Output path: `outputs/{market}/{date}/`

### Quick Start
1. Install dependencies
```bash
python -m pip install -r requirements.txt
```
2. Configure symbol universe
- Edit `config/universe.yaml`
3. Configure env vars
- Copy `.env.example` to `.env` and fill secrets
4. Retrain models
```bash
python -m app.jobs.run_retrain --market cn --date 2026-03-04
python -m app.jobs.run_retrain --market us --date 2026-03-04
python -m app.jobs.run_retrain --market hk --date 2026-03-04
```
5. Run daily reports
```bash
python -m app.jobs.run_report --market cn --date 2026-03-04
python -m app.jobs.run_report --market us --date 2026-03-04
python -m app.jobs.run_report --market hk --date 2026-03-04
```

### Required environment variables
- `TAVILY_API_KEY`
- `BRAVE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Configure at least one LLM path:
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`
- `LLM_PROVIDER=ollama` + `OLLAMA_BASE_URL` + `OLLAMA_MODEL` (local defaults available)

### Important optional knobs
- `LLM_PROVIDER` (`openai` / `gemini` / `ollama`)
- `STOCK_LIST_CN` / `STOCK_LIST_US` / `STOCK_LIST_HK` (env override for universe)
- `TRAINING_WINDOW_DAYS` (default `730`)
- `FEATURE_WARMUP_DAYS` (default `60`)
- `FETCH_MAX_RETRIES` (default `5`)
- `FETCH_RETRY_BASE_DELAY_SECONDS` (default `15`)
- `FETCH_RETRY_MAX_DELAY_SECONDS` (default `300`)
- `LLM_MAX_RETRIES` (default `6`)
- `LLM_RETRY_BASE_DELAY_SECONDS` (default `5`)
- `LLM_RETRY_MAX_DELAY_SECONDS` (default `120`)
- `GEMINI_MODEL` (default `gemini-2.0-flash`)
- `OLLAMA_MODEL` (default `qwen2.5:7b`)
- `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)

### GitHub Actions
- `daily_cn.yml`: UTC `0 8 * * 1-5` (16:00 Asia/Shanghai on weekdays)
- `daily_hk.yml`: UTC `30 9 * * 1-5` (17:30 Asia/Shanghai on weekdays)
- `daily_us.yml`: UTC `30 23 * * 1-5` (07:30 Asia/Shanghai next day)
- All schedules run automatically every trading day window: CN/HK on Asia/Shanghai weekdays, US on Asia/Shanghai Tue-Sat morning.
- GitHub-hosted runners cannot access your local Ollama by default; use Ollama locally or on self-hosted runners.
- `weekly_retrain.yml`: weekly retraining for CN/US/HK models

### Outputs
- `summary.md`
- `details.md`
- `predictions.csv`
- `run_meta.json`

### Documentation
- Chinese full guide: [docs/full-guide.md](docs/full-guide.md)
- English full guide: [docs/full-guide_EN.md](docs/full-guide_EN.md)
- GitHub Actions setup guide: [docs/github-actions-setup_EN.md](docs/github-actions-setup_EN.md)
