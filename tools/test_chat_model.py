"""Unit tests for orpath.control_plane.get_chat_model (offline — no network calls).

Covers:
  - returns a real ``ChatOpenAI`` instance
  - provider defaults (DeepSeek / iFlytek Spark / OpenAI)
  - env var precedence for API keys and base URLs
  - explicit model_name override
  - temperature passthrough
  - placeholder (``mock_key``) fallback when no credentials are configured
"""
from __future__ import annotations

import os
from typing import Any

import pytest
from langchain_openai import ChatOpenAI

from orpath.control_plane import get_chat_model

# Every env var the factory consults, so tests can control them deterministically.
ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "XFYUN_API_KEY",
    "XFYUN_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no ambient credentials leak into the factory resolution."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _secret(model: Any) -> str:
    return model.openai_api_key.get_secret_value()  # type: ignore[attr-defined]


def test_returns_chat_openai_instance(clean_env: Any) -> None:
    model = get_chat_model()
    assert isinstance(model, ChatOpenAI)


def test_default_deepseek_model_and_base_url(clean_env: Any) -> None:
    model = get_chat_model()
    assert model.model_name == "deepseek-chat"
    assert model.openai_api_base == "https://api.deepseek.com/v1"
    assert model.temperature == 0.2


def test_mock_key_fallback_when_no_credentials(clean_env: Any) -> None:
    model = get_chat_model()
    assert _secret(model) == "mock_key"


def test_explicit_model_name_and_temperature(clean_env: Any) -> None:
    model = get_chat_model(model_name="deepseek-reasoner", temperature=0.7)
    assert model.model_name == "deepseek-reasoner"
    assert model.temperature == 0.7


def test_xfyun_provider_from_model_hint(clean_env: Any) -> None:
    model = get_chat_model(model_name="spark-x2.6")
    assert model.model_name == "spark-x2.6"
    assert model.openai_api_base == "https://spark-api-open.xf-yun.com/v1"


def test_deepseek_env_key_and_base_url(clean_env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test/v1")
    model = get_chat_model()
    assert _secret(model) == "sk-deepseek-test"
    assert model.openai_api_base == "https://example.test/v1"


def test_xfyun_env_key(clean_env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XFYUN_API_KEY", "ak-xf-test")
    model = get_chat_model()
    assert _secret(model) == "ak-xf-test"
    assert model.openai_api_base == "https://spark-api-open.xf-yun.com/v1"


def test_deepseek_takes_precedence_over_xfyun(clean_env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("XFYUN_API_KEY", "ak-xf-test")
    model = get_chat_model()
    assert _secret(model) == "sk-deepseek-test"


def test_openai_env_key(clean_env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    model = get_chat_model()
    assert _secret(model) == "sk-openai-test"


def test_os_environ_absent_keys_do_not_raise(clean_env: Any) -> None:
    # Sanity: none of the configured keys should be present in the test process.
    for key in ENV_KEYS:
        assert not os.environ.get(key)
    assert isinstance(get_chat_model(), ChatOpenAI)
