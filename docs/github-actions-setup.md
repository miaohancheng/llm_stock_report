# GitHub Actions 配置手册（中文）

本文档专门说明如何在 GitHub 仓库中配置 Actions、Secrets（key）和 Variables，并完成首次可用运行。

## 1. 前置条件

- 你已将仓库推送到 GitHub。
- 仓库中包含以下 workflow 文件：
  - `.github/workflows/daily_cn.yml`
  - `.github/workflows/daily_hk.yml`
  - `.github/workflows/daily_us.yml`
  - `.github/workflows/weekly_retrain.yml`
  - `.github/workflows/deploy_pages.yml`

## 2. 启用 Actions

1. 打开仓库页面。
2. 点击顶部 `Actions`。
3. 如果提示未启用，点击启用按钮（例如 `Enable` / `I understand my workflows...`）。

## 3. 配置 Secrets（敏感 key）

路径：`Settings` -> `Secrets and variables` -> `Actions` -> `Secrets` -> `New repository secret`

必需 Secrets：
1. `TAVILY_API_KEY`
2. `BRAVE_API_KEY`
3. `TELEGRAM_BOT_TOKEN`
4. `TELEGRAM_CHAT_ID`

可选 Secrets：
1. `OPENAI_API_KEY`（`LLM_PROVIDER=openai` 时必需）
2. `GEMINI_API_KEY`（`LLM_PROVIDER=gemini` 时必需）
3. `OLLAMA_API_KEY`（仅远程受保护 Ollama 需要）
4. `TELEGRAM_MESSAGE_THREAD_ID`

说明：
- Secrets 用于密钥、token、chat id 等敏感字段。
- Secrets 不会在日志中明文展示。

## 4. 配置 Variables（非敏感配置）

路径：`Settings` -> `Secrets and variables` -> `Actions` -> `Variables` -> `New repository variable`

建议 Variables（可直接照抄）：

```text
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=openai
REPORT_LANGUAGE=zh
GEMINI_MODEL=gemini-2.0-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b

MAX_STOCKS_PER_RUN=30
DETAIL_MESSAGE_CHAR_LIMIT=3500
MODEL_EXPIRE_DAYS=8
MARKET_INDEX_FETCH_ENABLED=true

TRAINING_WINDOW_DAYS=730
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

STOCK_LIST_CN=SH600519,SZ000001,SZ300750
STOCK_LIST_US=AAPL,MSFT,NVDA
STOCK_LIST_HK=HK00700,HK03690,HK09988
```

说明：
- `STOCK_LIST_CN/US/HK` 已接入 workflow，会覆盖 `config/universe.yaml`。
- `REPORT_LANGUAGE` 支持 `zh` 或 `en`，用于控制 Telegram 推送语言。
- 变量值用英文逗号分隔，不要换行。
- GitHub Hosted Runner 通常无法访问你本地 `127.0.0.1:11434`，若要在 Actions 用 Ollama 建议 self-hosted runner。

## 5. Workflow 与变量映射关系

当前 workflow 已把上述变量注入运行环境：
- `daily_cn.yml`
- `daily_hk.yml`
- `daily_us.yml`
- `weekly_retrain.yml`

因此代码中 `os.getenv(...)` 可以直接读取到配置。

## 5.1 交易日自动调度确认

当前定时（UTC）：
- `daily_cn.yml`: `0 8 * * 1-5`（北京时间工作日 16:00）
- `daily_hk.yml`: `30 9 * * 1-5`（北京时间工作日 17:30）
- `daily_us.yml`: `30 23 * * 1-5`（北京时间周二到周六 07:30，覆盖美股前一交易日）

说明：
- 以上为自动触发，不需要手动运行。
- A 股与港股相隔 1.5 小时，避免同一时刻并发拥塞。

## 5.2 GitHub Pages 部署与案例自动更新

项目已内置两段能力：
1. `daily_cn/hk/us.yml` 会在日报结束后执行 `python -m app.jobs.export_case`，把结果写入 `pages_data/cases/**` 并自动提交回仓库。
2. `deploy_pages.yml` 在 `docs/**` 或 `pages_data/**` 变更时自动构建并发布站点。

首次启用步骤：
1. 打开 `Settings` -> `Pages`。
2. 在 `Build and deployment` 中把 `Source` 设为 `GitHub Actions`。
3. 回到 `Actions` 手动触发一次 `Deploy GitHub Pages`（或等待下一次日报后自动触发）。

发布后站点包含两块内容：
- 详细使用文档（中英文）
- 每日案例更新（按日期倒序展示）

## 6. 首次手动触发（推荐）

建议先手动跑一次确认配置正确。

1. 打开 `Actions`。
2. 选择 `Daily CN Report`（或 HK/US）。
3. 点击 `Run workflow`。
4. `date` 可留空（默认按北京时间当天），也可填如 `2026-03-04`。
5. 观察日志是否完成，并检查 Artifact 是否上传。

## 7. 验证检查清单

一次成功运行后检查：
1. Actions 日志里是否出现 `Outputs written:`。
2. Artifact 是否包含：
   - `outputs/**`
   - `models/**`
3. Telegram 是否收到：
   - 一条摘要
   - 若干条分段详情

## 8. 常见问题

## 8.1 配了 Variable 但不生效
检查：
- 名称是否完全一致（区分大小写）。
- 是否配置在当前仓库，而不是别的仓库/环境。
- workflow 里是否有对应 `env:` 注入（本项目已配置）。

## 8.2 Telegram 没收到消息
检查：
- `TELEGRAM_BOT_TOKEN` 是否正确。
- `TELEGRAM_CHAT_ID` 是否正确。
- 机器人是否已加入目标群并有发言权限。
- 使用 Topic 时是否正确设置 `TELEGRAM_MESSAGE_THREAD_ID`。

## 8.3 数据抓取仍偶发失败
建议提高：
- `FETCH_MAX_RETRIES`（如 6-8）
- `FETCH_RETRY_BASE_DELAY_SECONDS`（如 20）
- `FETCH_RETRY_MAX_DELAY_SECONDS`（如 360）

## 8.4 股票池配置冲突
优先级：
1. `STOCK_LIST_CN/US/HK`（Variables）
2. `STOCK_LIST`（仅 CN 兼容）
3. `config/universe.yaml`

## 8.5 LLM 429 限流导致跳股
建议提高：
- `LLM_MAX_RETRIES`（如 8-10）
- `LLM_RETRY_BASE_DELAY_SECONDS`（如 8-15）
- `LLM_RETRY_MAX_DELAY_SECONDS`（如 180-300）

说明：
- 代码已对 `429/408/409/5xx` 和瞬时网络异常做重试。
- 若重试后仍失败，才会按单股失败策略记录并跳过该股。

## 8.6 切换 LLM 供应商
示例：
- OpenAI：`LLM_PROVIDER=openai` + 配置 `OPENAI_API_KEY`
- Gemini：`LLM_PROVIDER=gemini` + 配置 `GEMINI_API_KEY`
- Ollama：`LLM_PROVIDER=ollama` + 配置 `OLLAMA_BASE_URL` 与 `OLLAMA_MODEL`

## 9. 推荐上线顺序

1. 先只配 `CN`，手动跑通。
2. 再配 `US`、`HK`。
3. 最后观察 3 个交易日的定时稳定性。
