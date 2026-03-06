from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

import yaml


@dataclass
class AppConfig:
    project_root: Path
    timezone: str
    max_stocks_per_run: int
    detail_message_char_limit: int
    model_expire_days: int
    prediction_top_n: int
    llm_model: str
    openai_base_url: str

    openai_api_key: str | None
    tavily_api_key: str | None
    brave_api_key: str | None
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    telegram_message_thread_id: str | None

    outputs_root: Path
    models_root: Path
    qlib_data_root: Path
    market_index_fetch_enabled: bool = False
    llm_provider: str = "openai"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    ollama_api_key: str | None = None
    ollama_model: str = "qwen2.5:7b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    training_window_days: int = 365 * 2
    feature_warmup_days: int = 60
    history_prune_buffer_days: int = 60
    incremental_overlap_days: int = 7
    fetch_max_retries: int = 5
    fetch_retry_base_delay_seconds: float = 15.0
    fetch_retry_max_delay_seconds: float = 300.0
    fetch_retry_jitter_seconds: float = 2.0
    llm_max_retries: int = 6
    llm_retry_base_delay_seconds: float = 5.0
    llm_retry_max_delay_seconds: float = 120.0
    llm_retry_jitter_seconds: float = 1.0
    report_language: str = "zh"
    daily_analysis_lookback_days: int = 30


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be mapping: {path}")
    return data


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_symbol_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_report_language(value: str) -> str:
    raw = (value or "").strip().lower()
    return raw if raw in {"zh", "en"} else "zh"


def load_config(project_root: Path | None = None) -> AppConfig:
    root = project_root or Path(__file__).resolve().parents[2]
    report_cfg = _read_yaml(root / "config" / "report.yaml")

    max_stocks = _env_int("MAX_STOCKS_PER_RUN", int(report_cfg.get("max_stocks_per_run", 30)))
    detail_limit = _env_int(
        "DETAIL_MESSAGE_CHAR_LIMIT",
        int(report_cfg.get("detail_message_char_limit", 3500)),
    )
    model_expire_days = _env_int("MODEL_EXPIRE_DAYS", int(report_cfg.get("model_expire_days", 8)))
    training_window_days = _env_int(
        "TRAINING_WINDOW_DAYS",
        int(report_cfg.get("training_window_days", 365 * 2)),
    )
    feature_warmup_days = _env_int(
        "FEATURE_WARMUP_DAYS",
        int(report_cfg.get("feature_warmup_days", 60)),
    )
    history_prune_buffer_days = _env_int(
        "HISTORY_PRUNE_BUFFER_DAYS",
        int(report_cfg.get("history_prune_buffer_days", 60)),
    )
    incremental_overlap_days = _env_int(
        "INCREMENTAL_OVERLAP_DAYS",
        int(report_cfg.get("incremental_overlap_days", 7)),
    )
    fetch_max_retries = _env_int(
        "FETCH_MAX_RETRIES",
        int(report_cfg.get("fetch_max_retries", 5)),
    )
    fetch_retry_base_delay_seconds = _env_float(
        "FETCH_RETRY_BASE_DELAY_SECONDS",
        float(report_cfg.get("fetch_retry_base_delay_seconds", 15.0)),
    )
    fetch_retry_max_delay_seconds = _env_float(
        "FETCH_RETRY_MAX_DELAY_SECONDS",
        float(report_cfg.get("fetch_retry_max_delay_seconds", 300.0)),
    )
    fetch_retry_jitter_seconds = _env_float(
        "FETCH_RETRY_JITTER_SECONDS",
        float(report_cfg.get("fetch_retry_jitter_seconds", 2.0)),
    )
    llm_max_retries = _env_int(
        "LLM_MAX_RETRIES",
        int(report_cfg.get("llm_max_retries", 6)),
    )
    llm_retry_base_delay_seconds = _env_float(
        "LLM_RETRY_BASE_DELAY_SECONDS",
        float(report_cfg.get("llm_retry_base_delay_seconds", 5.0)),
    )
    llm_retry_max_delay_seconds = _env_float(
        "LLM_RETRY_MAX_DELAY_SECONDS",
        float(report_cfg.get("llm_retry_max_delay_seconds", 120.0)),
    )
    llm_retry_jitter_seconds = _env_float(
        "LLM_RETRY_JITTER_SECONDS",
        float(report_cfg.get("llm_retry_jitter_seconds", 1.0)),
    )
    daily_analysis_lookback_days = _env_int(
        "DAILY_ANALYSIS_LOOKBACK_DAYS",
        int(report_cfg.get("daily_analysis_lookback_days", 30)),
    )
    market_index_fetch_enabled = _env_bool(
        "MARKET_INDEX_FETCH_ENABLED",
        bool(report_cfg.get("market_index_fetch_enabled", True)),
    )
    llm_provider = os.getenv("LLM_PROVIDER", str(report_cfg.get("llm_provider", "openai"))).strip().lower()
    gemini_model = os.getenv("GEMINI_MODEL", str(report_cfg.get("gemini_model", "gemini-2.0-flash")))
    gemini_base_url = os.getenv(
        "GEMINI_BASE_URL",
        str(report_cfg.get("gemini_base_url", "https://generativelanguage.googleapis.com/v1beta")),
    )
    ollama_model = os.getenv("OLLAMA_MODEL", str(report_cfg.get("ollama_model", "qwen2.5:7b")))
    ollama_base_url = os.getenv(
        "OLLAMA_BASE_URL",
        str(report_cfg.get("ollama_base_url", "http://127.0.0.1:11434")),
    )
    report_language = _normalize_report_language(
        os.getenv("REPORT_LANGUAGE", str(report_cfg.get("report_language", "zh")))
    )

    outputs_root = root / os.getenv("OUTPUTS_ROOT", "outputs")
    models_root = root / os.getenv("MODELS_ROOT", "models")
    qlib_data_root = root / os.getenv("QLIB_DATA_ROOT", "qlib_data")

    outputs_root.mkdir(parents=True, exist_ok=True)
    models_root.mkdir(parents=True, exist_ok=True)
    qlib_data_root.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        project_root=root,
        timezone=str(report_cfg.get("timezone", "Asia/Shanghai")),
        max_stocks_per_run=max_stocks,
        detail_message_char_limit=detail_limit,
        model_expire_days=model_expire_days,
        prediction_top_n=int(report_cfg.get("prediction_top_n", 10)),
        llm_model=os.getenv("OPENAI_MODEL", str(report_cfg.get("llm_model", "gpt-4o-mini"))),
        openai_base_url=os.getenv(
            "OPENAI_BASE_URL", str(report_cfg.get("openai_base_url", "https://api.openai.com/v1"))
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        tavily_api_key=os.getenv("TAVILY_API_KEY") or os.getenv("TAVILY_API_KEYS"),
        brave_api_key=os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_API_KEYS"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        telegram_message_thread_id=os.getenv("TELEGRAM_MESSAGE_THREAD_ID"),
        outputs_root=outputs_root,
        models_root=models_root,
        qlib_data_root=qlib_data_root,
        market_index_fetch_enabled=market_index_fetch_enabled,
        llm_provider=llm_provider,
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=gemini_model,
        gemini_base_url=gemini_base_url,
        ollama_api_key=os.getenv("OLLAMA_API_KEY"),
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url,
        training_window_days=training_window_days,
        feature_warmup_days=feature_warmup_days,
        history_prune_buffer_days=history_prune_buffer_days,
        incremental_overlap_days=incremental_overlap_days,
        fetch_max_retries=fetch_max_retries,
        fetch_retry_base_delay_seconds=fetch_retry_base_delay_seconds,
        fetch_retry_max_delay_seconds=fetch_retry_max_delay_seconds,
        fetch_retry_jitter_seconds=fetch_retry_jitter_seconds,
        llm_max_retries=llm_max_retries,
        llm_retry_base_delay_seconds=llm_retry_base_delay_seconds,
        llm_retry_max_delay_seconds=llm_retry_max_delay_seconds,
        llm_retry_jitter_seconds=llm_retry_jitter_seconds,
        report_language=report_language,
        daily_analysis_lookback_days=max(5, daily_analysis_lookback_days),
    )


def load_universe(project_root: Path | None = None) -> dict[str, list[str]]:
    root = project_root or Path(__file__).resolve().parents[2]
    universe_file = os.getenv("UNIVERSE_FILE")
    universe_path = Path(universe_file) if universe_file else root / "config" / "universe.yaml"
    raw = _read_yaml(universe_path)
    report_cfg = _read_yaml(root / "config" / "report.yaml")

    universe: dict[str, list[str]] = {"cn": [], "us": [], "hk": []}
    for market in ("cn", "us", "hk"):
        values = raw.get(market, [])
        if values is not None and not isinstance(values, list):
            raise ValueError(f"{universe_path}::{market} must be a list")
        universe[market] = _parse_symbol_list(values)

    # Optional defaults from report.yaml
    for market in ("cn", "us", "hk"):
        key = f"stock_list_{market}"
        cfg_list = _parse_symbol_list(report_cfg.get(key))
        if cfg_list:
            universe[market] = cfg_list

    # Environment overrides
    env_cn = _parse_symbol_list(os.getenv("STOCK_LIST_CN"))
    env_us = _parse_symbol_list(os.getenv("STOCK_LIST_US"))
    env_hk = _parse_symbol_list(os.getenv("STOCK_LIST_HK"))
    legacy_cn = _parse_symbol_list(os.getenv("STOCK_LIST"))

    if env_cn:
        universe["cn"] = env_cn
    elif legacy_cn:
        universe["cn"] = legacy_cn
    if env_us:
        universe["us"] = env_us
    if env_hk:
        universe["hk"] = env_hk

    return universe
