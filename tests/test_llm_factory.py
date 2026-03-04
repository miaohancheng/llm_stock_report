from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.common.config import AppConfig
from app.llm.base import LLMError
from app.llm.factory import create_llm_client


def _make_cfg(root: Path, **kwargs) -> AppConfig:
    outputs = root / "outputs"
    models = root / "models"
    qlib_data = root / "qlib_data"
    outputs.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    qlib_data.mkdir(parents=True, exist_ok=True)

    base = dict(
        project_root=root,
        timezone="Asia/Shanghai",
        max_stocks_per_run=30,
        detail_message_char_limit=3500,
        model_expire_days=8,
        prediction_top_n=10,
        llm_model="gpt-4o-mini",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="openai-key",
        tavily_api_key=None,
        brave_api_key=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        telegram_message_thread_id=None,
        outputs_root=outputs,
        models_root=models,
        qlib_data_root=qlib_data,
        llm_provider="openai",
        gemini_api_key="gemini-key",
        gemini_model="gemini-2.0-flash",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        ollama_api_key=None,
        ollama_model="qwen2.5:7b",
        ollama_base_url="http://127.0.0.1:11434",
    )
    base.update(kwargs)
    return AppConfig(**base)


class LLMFactoryTest(unittest.TestCase):
    def test_select_openai_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp), llm_provider="openai")
            client, label = create_llm_client(cfg)
            self.assertEqual("openai", client.provider)
            self.assertTrue(label.startswith("openai:"))

    def test_select_gemini_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp), llm_provider="gemini")
            client, label = create_llm_client(cfg)
            self.assertEqual("gemini", client.provider)
            self.assertTrue(label.startswith("gemini:"))

    def test_select_ollama_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp), llm_provider="ollama")
            client, label = create_llm_client(cfg)
            self.assertEqual("ollama", client.provider)
            self.assertTrue(label.startswith("ollama:"))

    def test_openai_provider_requires_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp), llm_provider="openai", openai_api_key=None)
            with self.assertRaises(LLMError):
                create_llm_client(cfg)


if __name__ == "__main__":
    unittest.main()
