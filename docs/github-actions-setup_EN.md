# GitHub Actions Setup Guide (English)

This document explains how to configure Actions, Secrets (keys), and Variables for this repository, then run a first successful job.

## 1. Prerequisites

- The repository is pushed to GitHub.
- Workflow files exist:
  - `.github/workflows/ci.yml`
  - `.github/workflows/daily_cn.yml`
  - `.github/workflows/daily_hk.yml`
  - `.github/workflows/daily_us.yml`
  - `.github/workflows/weekly_retrain.yml`
  - `.github/workflows/deploy_pages.yml`

## 2. Enable Actions

1. Open your repository page.
2. Click `Actions` tab.
3. If disabled, click the enable button.

## 3. Configure Secrets (sensitive keys)

Path: `Settings` -> `Secrets and variables` -> `Actions` -> `Secrets` -> `New repository secret`

Required Secrets:
1. `TAVILY_API_KEY`
2. `BRAVE_API_KEY`
3. `TELEGRAM_BOT_TOKEN`
4. `TELEGRAM_CHAT_ID`

Optional:
1. `OPENAI_API_KEY` (required when `LLM_PROVIDER=openai`)
2. `GEMINI_API_KEY` (required when `LLM_PROVIDER=gemini`)
3. `OLLAMA_API_KEY` (only for protected remote Ollama)
4. `TELEGRAM_MESSAGE_THREAD_ID`

Notes:
- Keep API keys and tokens in Secrets only.
- Secret values are masked in logs.

## 4. Configure Variables (non-sensitive runtime knobs)

Path: `Settings` -> `Secrets and variables` -> `Actions` -> `Variables` -> `New repository variable`

Recommended Variables:

```text
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=openai
REPORT_LANGUAGE=zh
PAGES_SITE_BASE_URL=https://miaohancheng.com/llm_stock_report
PAGES_DEFAULT_LANGUAGE=zh
PAGES_CASE_RETENTION_DAYS=3
GEMINI_MODEL=gemini-2.0-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b

MAX_STOCKS_PER_RUN=30
DETAIL_MESSAGE_CHAR_LIMIT=3500
MODEL_EXPIRE_DAYS=8
MARKET_INDEX_FETCH_ENABLED=true

TRAINING_WINDOW_DAYS=730
DAILY_ANALYSIS_LOOKBACK_DAYS=30
FEATURE_WARMUP_DAYS=60
HISTORY_PRUNE_BUFFER_DAYS=60
INCREMENTAL_OVERLAP_DAYS=7

FETCH_MAX_RETRIES=5
FETCH_RETRY_BASE_DELAY_SECONDS=15
FETCH_RETRY_MAX_DELAY_SECONDS=300
FETCH_RETRY_JITTER_SECONDS=2
LLM_MAX_RETRIES=6
LLM_RETRY_BASE_DELAY_SECONDS=5
LLM_RETRY_MAX_DELAY_SECONDS=120
LLM_RETRY_JITTER_SECONDS=1
LLM_MAX_OUTPUT_TOKENS=800
# OPENAI_USE_RESPONSE_FORMAT=false
# OPENROUTER_HTTP_REFERER=https://github.com/<owner>/<repo>
# OPENROUTER_APP_TITLE=llm_stock_report

STOCK_LIST_CN=SH600519,SZ000001,SZ300750
STOCK_LIST_US=AAPL,MSFT,NVDA
STOCK_LIST_HK=HK00700,HK03690,HK09988
```

Notes:
- `STOCK_LIST_CN/US/HK` already override `config/universe.yaml` in workflows.
- `REPORT_LANGUAGE` supports `zh` or `en` for Telegram/report output language.
- `PAGES_SITE_BASE_URL` is used to append the matching Pages case link to Telegram card footers.
- `PAGES_DEFAULT_LANGUAGE` supports `zh` or `en` for default Pages entry route (`/zh/` or `/en/`).
- `PAGES_CASE_RETENTION_DAYS` controls how many recent days are shown on Pages cases (default `3`).
- `DAILY_ANALYSIS_LOOKBACK_DAYS` controls the lookback window for daily reasoning context (default `30`).
- Use comma-separated values, no line breaks.
- GitHub-hosted runners usually cannot reach your local `127.0.0.1:11434`; use Ollama on self-hosted runners if needed.
- For OpenRouter free models, set `LLM_MAX_OUTPUT_TOKENS` to around `500-900`, and prefer non-`:free` models to reduce 429/timeout failures.

## 5. Workflow-to-env mapping

These workflows already inject the variables/secrets into runtime env:
- `daily_cn.yml`
- `daily_hk.yml`
- `daily_us.yml`
- `weekly_retrain.yml`

So application code can read them via `os.getenv(...)`.
`ci.yml` only installs the project and runs `python -m pytest`; it does not depend on the runtime variable set above.
Production workflows also run a fixed smoke-test suite before the actual report / retrain steps.

## 5.1 Trading-day schedule confirmation

Current schedules (UTC):
- `daily_cn.yml`: `0 8 * * 1-5` (16:00 Asia/Shanghai weekdays)
- `daily_hk.yml`: `30 9 * * 1-5` (17:30 Asia/Shanghai weekdays)
- `daily_us.yml`: `30 23 * * 1-5` (07:30 Asia/Shanghai Tue-Sat; covers prior US trading day)

Notes:
- These are automatic triggers; no manual run is required.
- CN and HK runs are staggered by 1.5 hours to reduce contention.

## 5.2 GitHub Pages deployment and auto case updates

The repository now includes two connected pieces:
1. `daily_cn/hk/us.yml` runs `python -m app.jobs.export_case` after each report, then commits `pages_data/cases/**` back to the repo.
2. `deploy_pages.yml` auto-builds and publishes the Pages site when `docs/**` or `pages_data/**` changes, and it also runs after `Daily CN/HK/US Report` completes (covers manual rerun scenarios).

First-time enablement:
1. Go to `Settings` -> `Pages`.
2. Under `Build and deployment`, set `Source` to `GitHub Actions`.
3. Trigger `Deploy GitHub Pages` manually once (or wait for the next daily run push).

Published site contains:
- detailed usage docs (ZH/EN)
- daily case updates (newest first)

## 6. First manual run (recommended)

1. Open `Actions` tab.
2. Choose `Daily CN Report` (or HK/US).
3. Click `Run workflow`.
4. Leave `date` empty (default to current day in Asia/Shanghai) or set `2026-03-04`.
5. Inspect logs and artifacts.

## 7. Validation checklist

After one successful run:
1. Logs include `Outputs written:`.
2. Artifacts contain:
   - `outputs/**`
   - `models/**`
3. Telegram receives:
   - one summary message
   - per-symbol chunked detail messages

## 8. Common issues

## 8.1 Variable exists but not applied
Check:
- exact variable name (case-sensitive),
- variable configured in the same repository,
- workflow has corresponding `env:` mapping (already included in this project).

## 8.2 Telegram messages not delivered
Check:
- `TELEGRAM_BOT_TOKEN`,
- `TELEGRAM_CHAT_ID`,
- bot membership and posting permission,
- `TELEGRAM_MESSAGE_THREAD_ID` for forum topics.

## 8.3 Data fetch still fails occasionally
Try higher values:
- `FETCH_MAX_RETRIES` (e.g. 6-8)
- `FETCH_RETRY_BASE_DELAY_SECONDS` (e.g. 20)
- `FETCH_RETRY_MAX_DELAY_SECONDS` (e.g. 360)

## 8.4 Universe config conflict
Priority:
1. `STOCK_LIST_CN/US/HK` (Variables)
2. `STOCK_LIST` (legacy CN only)
3. `config/universe.yaml`

## 8.5 LLM 429 rate-limit skips
Try higher values:
- `LLM_MAX_RETRIES` (e.g. 8-10)
- `LLM_RETRY_BASE_DELAY_SECONDS` (e.g. 8-15)
- `LLM_RETRY_MAX_DELAY_SECONDS` (e.g. 180-300)

Notes:
- The code retries on `429/408/409/5xx` and transient network failures.
- A symbol is skipped only after retry budget is exhausted.

## 8.6 Switch LLM provider
Examples:
- OpenAI: `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- Gemini: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`
- Ollama: `LLM_PROVIDER=ollama` + `OLLAMA_BASE_URL` + `OLLAMA_MODEL`

## 9. Recommended rollout

1. Configure and validate CN first.
2. Then enable US and HK.
3. Observe scheduled stability for at least 3 trading days.
