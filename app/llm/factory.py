from __future__ import annotations

from app.common.config import AppConfig
from app.llm.base import LLMClient, LLMError
from app.llm.gemini_client import GeminiClient
from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient


def create_llm_client(cfg: AppConfig) -> tuple[LLMClient, str]:
    provider = (cfg.llm_provider or "openai").strip().lower()

    if provider == "openai":
        if not cfg.openai_api_key:
            raise LLMError("LLM provider openai requires OPENAI_API_KEY")
        client: LLMClient = OpenAIClient(
            api_key=cfg.openai_api_key,
            base_url=cfg.openai_base_url,
            model=cfg.llm_model,
            max_retries=cfg.llm_max_retries,
            retry_base_delay_seconds=cfg.llm_retry_base_delay_seconds,
            retry_max_delay_seconds=cfg.llm_retry_max_delay_seconds,
            retry_jitter_seconds=cfg.llm_retry_jitter_seconds,
        )
        return client, client.model_id()

    if provider == "gemini":
        if not cfg.gemini_api_key:
            raise LLMError("LLM provider gemini requires GEMINI_API_KEY")
        client = GeminiClient(
            api_key=cfg.gemini_api_key,
            base_url=cfg.gemini_base_url,
            model=cfg.gemini_model,
            max_retries=cfg.llm_max_retries,
            retry_base_delay_seconds=cfg.llm_retry_base_delay_seconds,
            retry_max_delay_seconds=cfg.llm_retry_max_delay_seconds,
            retry_jitter_seconds=cfg.llm_retry_jitter_seconds,
        )
        return client, client.model_id()

    if provider == "ollama":
        client = OllamaClient(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_model,
            api_key=cfg.ollama_api_key,
            max_retries=cfg.llm_max_retries,
            retry_base_delay_seconds=cfg.llm_retry_base_delay_seconds,
            retry_max_delay_seconds=cfg.llm_retry_max_delay_seconds,
            retry_jitter_seconds=cfg.llm_retry_jitter_seconds,
        )
        return client, client.model_id()

    raise LLMError(
        "Unsupported LLM_PROVIDER. Expected one of: openai, gemini, ollama"
    )
