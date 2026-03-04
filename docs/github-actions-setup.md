# GitHub Actions 配置手册（中文）

本文档专门说明如何在 GitHub 仓库中配置 Actions、Secrets（key）和 Variables，并完成首次可用运行。

## 1. 前置条件

- 你已将仓库推送到 GitHub。
- 仓库中包含以下 workflow 文件：
  - `.github/workflows/daily_cn.yml`
  - `.github/workflows/daily_hk.yml`
  - `.github/workflows/daily_us.yml`
  - `.github/workflows/weekly_retrain.yml`

## 2. 启用 Actions

1. 打开仓库页面。
2. 点击顶部 `Actions`。
3. 如果提示未启用，点击启用按钮（例如 `Enable` / `I understand my workflows...`）。

## 3. 配置 Secrets（敏感 key）

路径：`Settings` -> `Secrets and variables` -> `Actions` -> `Secrets` -> `New repository secret`

必需 Secrets：
1. `OPENAI_API_KEY`
2. `TAVILY_API_KEY`
3. `BRAVE_API_KEY`
4. `TELEGRAM_BOT_TOKEN`
5. `TELEGRAM_CHAT_ID`

可选 Secrets：
1. `TELEGRAM_MESSAGE_THREAD_ID`

说明：
- Secrets 用于密钥、token、chat id 等敏感字段。
- Secrets 不会在日志中明文展示。

## 4. 配置 Variables（非敏感配置）

路径：`Settings` -> `Secrets and variables` -> `Actions` -> `Variables` -> `New repository variable`

建议 Variables（可直接照抄）：

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

说明：
- `STOCK_LIST_CN/US/HK` 已接入 workflow，会覆盖 `config/universe.yaml`。
- 变量值用英文逗号分隔，不要换行。

## 5. Workflow 与变量映射关系

当前 workflow 已把上述变量注入运行环境：
- `daily_cn.yml`
- `daily_hk.yml`
- `daily_us.yml`
- `weekly_retrain.yml`

因此代码中 `os.getenv(...)` 可以直接读取到配置。

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

## 9. 推荐上线顺序

1. 先只配 `CN`，手动跑通。
2. 再配 `US`、`HK`。
3. 最后观察 3 个交易日的定时稳定性。
