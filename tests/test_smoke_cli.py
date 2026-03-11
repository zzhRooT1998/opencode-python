from typer.testing import CliRunner

from opencode_py.cli.main import app


def test_cli_help_shows_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "chat" in result.stdout

