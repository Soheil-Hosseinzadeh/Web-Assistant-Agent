"""Configuration loading and process-environment setup.

All settings live in ``conf.yml`` (see ``conf.example.yml``). They are loaded
once, validated, and exposed as an immutable :class:`Settings` object.

This module must stay free of heavy imports (smolagents / litellm) so the
environment can be prepared *before* those libraries are imported.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "conf.yml"

REQUIRED_KEYS = (
    "MODEL",
    "BASE_URL",
    "API_KEY",
    "CONTEXT_LENGTH",
    "MAX_STEP",
    "INSTRUCTIONS",
)


class ConfigError(Exception):
    """Raised when conf.yml is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    # Required
    model: str
    base_url: str
    api_key: str
    context_length: int
    max_steps: int
    instructions: str
    # Optional (defaults match the original main.py)
    context_threshold: float = 0.85
    keep_ratio: float = 0.75
    temperature: float = 0.1
    executor_timeout: int = 120
    host: str = "127.0.0.1"
    port: int = 8080
    proxy: str = ""
    enable_vision_tools: bool = False

    @property
    def context_trigger(self) -> float:
        """Input-token count at which older memory is trimmed."""
        return self.context_length * self.context_threshold


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    if not path.is_file():
        raise ConfigError(
            f"Configuration file not found: {path}\n"
            "Create it with:  cp conf.example.yml conf.yml"
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a YAML mapping of settings.")

    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise ConfigError(f"{path} is missing required keys: {', '.join(missing)}")

    return Settings(
        model=raw["MODEL"],
        base_url=raw["BASE_URL"],
        api_key=raw["API_KEY"],
        context_length=int(raw["CONTEXT_LENGTH"]),
        max_steps=int(raw["MAX_STEP"]),
        instructions=raw["INSTRUCTIONS"],
        context_threshold=float(raw.get("CONTEXT_THRESHOLD", 0.80)),
        keep_ratio=float(raw.get("KEEP_RATIO", 0.50)),
        temperature=float(raw.get("TEMPERATURE", 0.1)),
        executor_timeout=int(raw.get("EXECUTOR_TIMEOUT", 120)),
        host=str(raw.get("HOST", "127.0.0.1")),
        port=int(raw.get("PORT", 8080)),
        proxy=str(raw.get("PROXY", "") or ""),
        enable_vision_tools=bool(raw.get("ENABLE_VISION_TOOLS", False)),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load (once) and return the application settings."""
    return load_settings()


def apply_environment(settings: Settings) -> None:
    """Prepare environment variables. Call BEFORE importing smolagents/litellm."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    # Proxy configuration is intentionally controlled only by conf.yml. Clear
    # inherited proxy settings when PROXY is empty so clients connect directly.
    proxy_keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )
    if settings.proxy:
        os.environ["HTTP_PROXY"] = settings.proxy
        os.environ["HTTPS_PROXY"] = settings.proxy
        os.environ["http_proxy"] = settings.proxy
        os.environ["https_proxy"] = settings.proxy
        os.environ.pop("ALL_PROXY", None)
        os.environ.pop("all_proxy", None)
    else:
        for key in proxy_keys:
            os.environ.pop(key, None)
