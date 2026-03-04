# llm_stock_report Full Guide (English)

This guide covers end-to-end usage: local runs, GitHub Actions automation, configuration, model/data behavior, and troubleshooting.

For a step-by-step GitHub Actions setup walkthrough:
- [docs/github-actions-setup_EN.md](github-actions-setup_EN.md)

## 1. Scope

`llm_stock_report` is a research/reporting pipeline that:
- retrains CN/US/HK models weekly,
- runs next-day prediction daily,
- combines news evidence and LLM reasoning,
- sends summary + detailed messages to Telegram.

It is not an auto-trading system.

## 2. Runtime Pipeline

A daily report run (`run_report`) executes:
1. Load symbol universe from `config/universe.yaml`
2. Fetch historical market data
   - use local cache first and fetch only missing ranges
   - apply exponential retry on fetch failures
3. Build technical features and `next_day_return`
4. Load latest model (auto-retrain if missing/expired)
5. Predict and rank symbols
6. Fetch news (Tavily primary, Brave fallback)
7. Generate Chinese narratives via OpenAI
8. Render outputs and send Telegram messages

A retrain run (`run_retrain`) executes:
- fetch data -> build features -> train -> save model.

## 3. Project Layout

```text
app/
  common/      config, logging, schemas
  data/        data fetchers and symbol normalization
  features/    technical indicators
  model/       frame builder, trainer, predictor, registry
  news/        Tavily/Brave search + fallback
  llm/         OpenAI client + prompts + reasoner
  report/      markdown rendering + Telegram sender
  jobs/        CLI entrypoints

config/
  universe.yaml
  report.yaml

outputs/{market}/{date}/
  summary.md
  details.md
  predictions.csv
  run_meta.json

models/{market}/{model_version}/
  model.pkl
  metadata.json
```

## 4. Environment Setup

## 4.1 Python
- Python 3.11 recommended

## 4.2 Install
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4.3 Environment Variables
```bash
cp .env.example .env
```
Fill required values:
- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `BRAVE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:
- `TELEGRAM_MESSAGE_THREAD_ID`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `MAX_STOCKS_PER_RUN`
- `DETAIL_MESSAGE_CHAR_LIMIT`
- `MODEL_EXPIRE_DAYS`
- `STOCK_LIST_CN` / `STOCK_LIST_US` / `STOCK_LIST_HK`

## 5. Universe Configuration

Edit `config/universe.yaml`:
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

Notes:
- CN accepts `SHxxxxxx` / `SZxxxxxx` or plain 6-digit symbols (normalized internally).
- US uses normal tickers.
- HK accepts `HK00700`, `00700`, `0700`, or `700` (normalized to `HK00700`).
- Per-run symbol count is capped by `MAX_STOCKS_PER_RUN` (default 30).

## 6. Local Commands

## 6.1 Retrain
```bash
python -m app.jobs.run_retrain --market cn --date 2026-03-04
python -m app.jobs.run_retrain --market us --date 2026-03-04
python -m app.jobs.run_retrain --market hk --date 2026-03-04
```

Note: retraining checks local cache under `qlib_data/history/`, incrementally tops up missing history, and prunes stale rows outside retention.

## 6.2 Daily Report
```bash
python -m app.jobs.run_report --market cn --date 2026-03-04
python -m app.jobs.run_report --market us --date 2026-03-04
python -m app.jobs.run_report --market hk --date 2026-03-04
```

Run without Telegram sending:
```bash
python -m app.jobs.run_report --market cn --date 2026-03-04 --no-telegram
```

## 7. Output Contract

`predictions.csv` columns:
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

`run_meta.json` keys:
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

## 8. Telegram Protocol

Send order:
1. Summary message (`[CN] YYYY-MM-DD 日报摘要`)
2. Per-symbol detail chunks (`[CN][symbol][i/n]`)

Behavior:
- Max message length default: 3500 chars
- Long content is force-chunked with `(i/n)` markers
- Markdown content is escaped before sending

## 9. GitHub Actions

## 9.1 Workflow files
- `.github/workflows/daily_cn.yml`
- `.github/workflows/daily_hk.yml`
- `.github/workflows/daily_us.yml`
- `.github/workflows/weekly_retrain.yml`

## 9.2 Schedules (UTC)
- `daily_cn.yml`: `30 9 * * 1-5` (17:30 Asia/Shanghai weekdays)
- `daily_hk.yml`: `30 9 * * 1-5` (17:30 Asia/Shanghai weekdays)
- `daily_us.yml`: `30 23 * * 1-5` (07:30 Asia/Shanghai next day)
- `weekly_retrain.yml`: scheduled Sunday retraining

## 9.3 GitHub Secrets
Required:
- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `BRAVE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:
- `TELEGRAM_MESSAGE_THREAD_ID`

## 9.4 GitHub Variables (optional)
- `MAX_STOCKS_PER_RUN` (default 30)
- `DETAIL_MESSAGE_CHAR_LIMIT` (default 3500)
- `MODEL_EXPIRE_DAYS` (default 8)
- `STOCK_LIST_CN` / `STOCK_LIST_US` / `STOCK_LIST_HK` (env override for universe)
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

## 9.5 Artifacts
Each workflow uploads:
- `outputs/**`
- `models/**`
Retention: 14 days.

## 9.6 Training Window and Retry Knobs

- `TRAINING_WINDOW_DAYS`: main training window (default `730`)
- `FEATURE_WARMUP_DAYS`: extra warmup days for indicators (default `60`)
- `HISTORY_PRUNE_BUFFER_DAYS`: extra cache retention (default `60`)
- `INCREMENTAL_OVERLAP_DAYS`: overlap days for incremental sync (default `7`)
- `FETCH_MAX_RETRIES`: max retries for data fetch (default `5`)
- `FETCH_RETRY_BASE_DELAY_SECONDS`: base retry delay (default `15`)
- `FETCH_RETRY_MAX_DELAY_SECONDS`: max retry delay (default `300`)
- `FETCH_RETRY_JITTER_SECONDS`: random jitter seconds (default `2`)

## 9.7 LLM Reliability Hardening

Prompt and parser now enforce:
- no fabricated metrics beyond provided inputs,
- explicit evidence references (`N1/N2...`) or clear evidence shortage,
- confidence score (0-100) and reliability notes,
- concrete, actionable risk points instead of generic statements.

## 10. Troubleshooting

## 10.1 Data fetch fails for all symbols
Check:
- Network access
- Symbol format
- Date validity around market trading days

## 10.2 Empty predictions
Check:
- Insufficient lookback history
- Feature columns full of NaN
- `predict_frame.csv` in `outputs/debug/...`

## 10.3 Telegram send errors
Check:
- bot token/chat id correctness
- bot permissions in target group
- topic id if sending to a thread

## 10.4 LLM errors
Check:
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- model availability

## 10.5 News is empty
- Tavily failure automatically falls back to Brave
- If both fail, report still runs with empty news evidence

## 11. Operational Advice

- Keep weekly retraining enabled
- Avoid frequent large universe changes
- Run `--no-telegram` smoke tests before production
- Keep `outputs` and `models` artifacts for audit/replay
- Investigate `failed_list` when `status=partial`
