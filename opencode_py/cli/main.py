"""Typer application entry point."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="opencode",
    no_args_is_help=True,
    help="Local CLI coding assistant.",
)


@app.callback()
def cli() -> None:
    """OpenCode Python command group."""


@app.command()
def chat() -> None:
    """Placeholder chat command for the MVP scaffold."""
    typer.echo("chat")


def main() -> None:
    """Run the Typer application."""
    app()
