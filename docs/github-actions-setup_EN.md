# GitHub Actions Setup Guide (English)

This document explains how to configure Actions, Secrets (keys), and Variables for this repository, then run a first successful job.

## 1. Prerequisites

- The repository is pushed to GitHub.
- Workflow files exist:
  - `.github/workflows/daily_cn.yml`
  - `.github/workflows/daily_hk.yml`
  - `.github/workflows/daily_us.yml`
  - `.github/workflows/weekly_retrain.yml`

## 2. Enable Actions

1. Open your repository page.
2. Click `Actions` tab.
3. If disabled, click the enable button.

## 3. Configure Secrets (sensitive keys)

Path: `Settings` -> `Secrets and variables` -> `Actions` -> `Secrets` -> `New repository secret`

Required Secrets:
1. `OPENAI_API_KEY`
2. `TAVILY_API_KEY`
3. `BRAVE_API_KEY`
4. `TELEGRAM_BOT_TOKEN`
5. `TELEGRAM_CHAT_ID`

Optional:
1. `TELEGRAM_MESSAGE_THREAD_ID`

Notes:
- Keep API keys and tokens in Secrets only.
- Secret values are masked in logs.

## 4. Configure Variables (non-sensitive runtime knobs)

Path: `Settings` -> `Secrets and variables` -> `Actions` -> `Variables` -> `New repository variable`

Recommended Variables:

```text
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

MAX_STOCKS_PER_RUN=30
DETAIL_MESSAGE_CHAR_LIMIT=3500
MODEL_EXPIRE_DAYS=8

TRAINING_WINDOW_DAYS=730
FEATURE_WARMUP_DAYS=60
HISTORY_PRUNE_BUFFER_DAYS=60
INCREMENTAL_OVERLAP_DAYS=7

FETCH_MAX_RETRIES=5
FETCH_RETRY_BASE_DELAY_SECONDS=15
FETCH_RETRY_MAX_DELAY_SECONDS=300
FETCH_RETRY_JITTER_SECONDS=2

STOCK_LIST_CN=SH600519,SZ000001,SZ300750
STOCK_LIST_US=AAPL,MSFT,NVDA
STOCK_LIST_HK=HK00700,HK03690,HK09988
```

Notes:
- `STOCK_LIST_CN/US/HK` already override `config/universe.yaml` in workflows.
- Use comma-separated values, no line breaks.

## 5. Workflow-to-env mapping

These workflows already inject the variables/secrets into runtime env:
- `daily_cn.yml`
- `daily_hk.yml`
- `daily_us.yml`
- `weekly_retrain.yml`

So application code can read them via `os.getenv(...)`.

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

## 9. Recommended rollout

1. Configure and validate CN first.
2. Then enable US and HK.
3. Observe scheduled stability for at least 3 trading days.
