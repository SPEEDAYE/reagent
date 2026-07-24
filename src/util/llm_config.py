"""
文件定位：多 LLM 提供商配置解析与 crewAI LLM 构建

主要功能：
- load_project_env(): 加载 .env 文件（workspace 级 + 项目级，后者可覆盖前者）
- LLMConfig: 冻结数据类，存储 provider/model/api_key/base_url 等配置
- resolve_llm_config(): 从环境变量解析完整的 LLMConfig
- build_llm(): 构建 crewAI LLM 实例

支持的提供商：OpenAI/GPT, DeepSeek, Qwen（通义千问）, UCloud
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from crewai import LLM
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent


def load_project_env() -> None:
    """Load env files from workspace root and project root.

    Workspace-level values are loaded first so repo-local `.env` values can
    override them when present.
    """

    for env_path, override in (
        (WORKSPACE_ROOT / ".env", False),
        (PROJECT_ROOT / ".env", True),
    ):
        if env_path.exists():
            load_dotenv(env_path, override=override)


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float | None = None
    timeout: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None


PROVIDER_ALIASES = {
    "gpt": "openai",
    "openai": "openai",
    "deepseek": "deepseek",
    "qwen": "qwen",
    "ucloud": "ucloud",
    "zhiyuan": "zhiyuan",
}

PROVIDER_ENV_CANDIDATES = (
    "LLM_PROVIDER",
    "MODEL_PROVIDER",
    "DEFAULT_LLM_PROVIDER",
)
DEFAULT_LLM_TIMEOUT_SECONDS = 180.0

PROVIDER_SETTINGS = {
    "openai": {
        "model": ("LLM_MODEL", "OPENAI_MODEL"),
        "api_key": ("LLM_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY"),
        "base_url": ("LLM_BASE_URL", "OPENAI_BASE_URL", "OPENAI_URL"),
        "default_model": "o1",
    },
    "deepseek": {
        "model": ("LLM_MODEL", "DEEPSEEK_MODEL", "my_deepseek_model"),
        "api_key": (
            "LLM_API_KEY",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_KEY",
            "my_deepseek_key",
        ),
        "base_url": (
            "LLM_BASE_URL",
            "DEEPSEEK_BASE_URL",
            "DEEPSEEK_URL",
            "my_deepseek_url",
        ),
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "model": ("LLM_MODEL", "QWEN_MODEL", "my_qwen_model"),
        "api_key": ("LLM_API_KEY", "QWEN_API_KEY", "QWEN_KEY", "my_qwen_key"),
        "base_url": ("LLM_BASE_URL", "QWEN_BASE_URL", "QWEN_URL", "my_qwen_url"),
        "default_model": "qwen-plus",
    },
    "ucloud": {
        "model": ("LLM_MODEL", "UCLOUD_MODEL", "ucloud_model"),
        "api_key": ("LLM_API_KEY", "UCLOUD_API_KEY", "UCLOUD_KEY", "ucloud_key"),
        "base_url": ("LLM_BASE_URL", "UCLOUD_BASE_URL", "UCLOUD_URL", "ucloud_url"),
        "default_model": "gpt-4o-mini",
    },
    "zhiyuan": {
        "model": ("LLM_MODEL", "zhiyuan_MODEL"),
        "api_key": ("LLM_API_KEY", "zhiyuan_API_KEY"),
        "base_url": ("LLM_BASE_URL", "zhiyuan_BASE_URL"),
        "default_model": "qwen3-max",
    },
}


def _first_env_value(keys: Iterable[str]) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value.strip()
    return None


def _normalize_provider(raw_provider: str | None) -> str:
    provider = (raw_provider or "openai").strip().lower()
    return PROVIDER_ALIASES.get(provider, provider)


def _resolve_provider() -> str:
    for key in PROVIDER_ENV_CANDIDATES:
        value = os.getenv(key)
        if value:
            provider = _normalize_provider(value)
            if provider in PROVIDER_SETTINGS:
                return provider
            supported = ", ".join(PROVIDER_SETTINGS)
            raise ValueError(
                f"Unsupported provider {value!r}. Supported values: {supported}."
            )
    return "openai"


def _parse_float(key: str) -> float | None:
    value = os.getenv(key)
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got {value!r}.") from exc


def _parse_int(key: str) -> int | None:
    value = os.getenv(key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {value!r}.") from exc


def resolve_llm_config() -> LLMConfig:
    load_project_env()

    provider = _resolve_provider()
    provider_settings = PROVIDER_SETTINGS[provider]

    model = _first_env_value(provider_settings["model"]) or provider_settings["default_model"]
    api_key = _first_env_value(provider_settings["api_key"])
    base_url = _first_env_value(provider_settings["base_url"])

    if not api_key:
        expected = ", ".join(provider_settings["api_key"])
        raise ValueError(
            f"Missing API key for provider '{provider}'. "
            f"Set one of: {expected}."
        )

    reasoning_effort = os.getenv("LLM_REASONING_EFFORT")
    if reasoning_effort:
        reasoning_effort = reasoning_effort.strip().lower()

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=_parse_float("LLM_TEMPERATURE"),
        timeout=(
            _parse_float("LLM_TIMEOUT")
            if os.getenv("LLM_TIMEOUT")
            else DEFAULT_LLM_TIMEOUT_SECONDS
        ),
        max_tokens=_parse_int("LLM_MAX_TOKENS"),
        reasoning_effort=reasoning_effort,
    )


def build_llm() -> LLM:
    config = resolve_llm_config()

    llm_kwargs = {
        "model": config.model,
        "api_key": config.api_key,
        "provider": "openai",
        "stream": True,  # Enable token-level streaming for SSE delta events
    }

    if config.base_url:
        llm_kwargs["base_url"] = config.base_url
    if config.temperature is not None:
        llm_kwargs["temperature"] = config.temperature
    if config.timeout is not None:
        llm_kwargs["timeout"] = config.timeout
    if config.max_tokens is not None:
        llm_kwargs["max_tokens"] = config.max_tokens
    if config.reasoning_effort:
        llm_kwargs["reasoning_effort"] = config.reasoning_effort

    return LLM(**llm_kwargs)
