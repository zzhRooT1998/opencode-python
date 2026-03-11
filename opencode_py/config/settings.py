"""Application configuration loading."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


PermissionMode = Literal["allow", "ask", "deny"]


class ProviderSettings(BaseModel):
    """Provider connection settings."""

    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0


class SecuritySettings(BaseModel):
    """Tool permission settings."""

    mode: PermissionMode = "ask"


class AppSettings(BaseModel):
    """Top-level application settings."""

    data_dir: Path = Field(default_factory=lambda: Path.home() / ".opencode")
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @classmethod
    def from_sources(
        cls,
        cli_overrides: Mapping[str, Any] | None = None,
        config_path: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "AppSettings":
        """Load settings with precedence env -> config file -> CLI overrides."""

        merged: dict[str, Any] = {}
        _deep_update(merged, _env_config(environ or os.environ))

        file_config = _load_config_file(config_path)
        _deep_update(merged, file_config)

        _deep_update(merged, dict(cli_overrides or {}))
        return cls.model_validate(merged)


def _load_config_file(config_path: Path | None) -> dict[str, Any]:
    path = config_path or (Path.home() / ".opencode" / "config.toml")
    if not path.exists():
        return {}

    with path.open("rb") as file:
        raw = tomllib.load(file)

    return {
        "data_dir": raw.get("app", {}).get("data_dir"),
        "provider": raw.get("provider", {}),
        "security": raw.get("security", {}),
    }


def _env_config(environ: Mapping[str, str]) -> dict[str, Any]:
    provider: dict[str, Any] = {}
    security: dict[str, Any] = {}
    root: dict[str, Any] = {}

    if model := environ.get("OPENCODE_MODEL"):
        provider["model"] = model
    if api_key := environ.get("OPENCODE_API_KEY"):
        provider["api_key"] = api_key
    if base_url := environ.get("OPENCODE_BASE_URL"):
        provider["base_url"] = base_url
    if timeout_seconds := environ.get("OPENCODE_TIMEOUT_SECONDS"):
        provider["timeout_seconds"] = float(timeout_seconds)
    if permission_mode := environ.get("OPENCODE_PERMISSION_MODE"):
        security["mode"] = permission_mode
    if data_dir := environ.get("OPENCODE_DATA_DIR"):
        root["data_dir"] = data_dir

    if provider:
        root["provider"] = provider
    if security:
        root["security"] = security

    return root


def _deep_update(target: dict[str, Any], override: Mapping[str, Any]) -> None:
    for key, value in override.items():
        if value is None:
            continue
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, Mapping)
        ):
            _deep_update(target[key], value)
            continue
        target[key] = dict(value) if isinstance(value, Mapping) else value

