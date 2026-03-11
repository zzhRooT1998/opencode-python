from pathlib import Path

from opencode_py.config.settings import AppSettings


def test_settings_precedence_cli_overrides_config_and_env(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[app]",
                'data_dir = "C:/config-data"',
                "",
                "[provider]",
                'model = "config-model"',
                "",
                "[security]",
                'mode = "deny"',
            ]
        ),
        encoding="utf-8",
    )

    settings = AppSettings.from_sources(
        cli_overrides={"provider": {"model": "cli-model"}},
        config_path=config_path,
        environ={
            "OPENCODE_MODEL": "env-model",
            "OPENCODE_PERMISSION_MODE": "ask",
            "OPENCODE_DATA_DIR": "C:/env-data",
        },
    )

    assert settings.provider.model == "cli-model"
    assert settings.security.mode == "deny"
    assert settings.data_dir == Path("C:/config-data")


def test_settings_use_env_when_config_missing() -> None:
    settings = AppSettings.from_sources(
        environ={
            "OPENCODE_MODEL": "env-model",
            "OPENCODE_API_KEY": "secret",
            "OPENCODE_PERMISSION_MODE": "allow",
        }
    )

    assert settings.provider.model == "env-model"
    assert settings.provider.api_key == "secret"
    assert settings.security.mode == "allow"

