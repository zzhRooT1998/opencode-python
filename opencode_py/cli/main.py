"""Typer application entry point."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel

from opencode_py.agents import ExecutorAgent, PlannerAgent, ReviewerAgent
from opencode_py.config.settings import AppSettings
from opencode_py.core.graph import LangGraphOrchestrator, OrchestratorResult
from opencode_py.providers import OpenAIProvider
from opencode_py.retrieval import RetrievalService
from opencode_py.security.policy import PermissionPolicy
from opencode_py.session.repository import SessionRepository
from opencode_py.storage import SQLiteStore
from opencode_py.tools import FSReadTool, FSWriteTool, SearchTool, ShellTool, ToolRuntime


app = typer.Typer(
    name="opencode",
    no_args_is_help=True,
    help="Local CLI coding assistant.",
)
console = Console()


@dataclass(slots=True)
class AppServices:
    """Runtime services assembled from configuration."""

    orchestrator: LangGraphOrchestrator
    repository: SessionRepository


@app.callback()
def cli() -> None:
    """OpenCode Python command group."""


@app.command()
def chat(
    task: str = typer.Argument(..., help="Natural-language coding task."),
    model: str | None = typer.Option(None, help="Override the configured model."),
    session_id: str | None = typer.Option(None, help="Reuse an explicit session id."),
    data_dir: Path | None = typer.Option(None, help="Override the application data directory."),
    workspace_root: Path = typer.Option(Path.cwd(), help="Workspace root to operate on."),
    permission_mode: str | None = typer.Option(None, help="Override tool permission mode."),
) -> None:
    """Run one interactive-style task."""

    result = _run_task(
        task=task,
        model=model,
        session_id=session_id,
        data_dir=data_dir,
        workspace_root=workspace_root,
        permission_mode=permission_mode,
    )
    _render_result(result)


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural-language coding task."),
    model: str | None = typer.Option(None, help="Override the configured model."),
    session_id: str | None = typer.Option(None, help="Reuse an explicit session id."),
    data_dir: Path | None = typer.Option(None, help="Override the application data directory."),
    workspace_root: Path = typer.Option(Path.cwd(), help="Workspace root to operate on."),
    permission_mode: str | None = typer.Option(None, help="Override tool permission mode."),
) -> None:
    """Run one non-interactive task execution."""

    result = _run_task(
        task=task,
        model=model,
        session_id=session_id,
        data_dir=data_dir,
        workspace_root=workspace_root,
        permission_mode=permission_mode,
    )
    _render_result(result)


def main() -> None:
    """Run the Typer application."""
    app()


def _run_task(
    *,
    task: str,
    model: str | None,
    session_id: str | None,
    data_dir: Path | None,
    workspace_root: Path,
    permission_mode: str | None,
) -> OrchestratorResult:
    cli_overrides: dict[str, object] = {}
    if data_dir is not None:
        cli_overrides["data_dir"] = data_dir
    if model is not None:
        cli_overrides.setdefault("provider", {})
        cli_overrides["provider"] = {"model": model}
    if permission_mode is not None:
        cli_overrides["security"] = {"mode": permission_mode}

    settings = AppSettings.from_sources(cli_overrides=cli_overrides)
    services = create_app_services(
        settings=settings,
        workspace_root=workspace_root,
        console=console,
    )
    return services.orchestrator.run(
        session_id=session_id or str(uuid4()),
        user_goal=task,
    )


def create_app_services(
    *,
    settings: AppSettings,
    workspace_root: Path,
    console: Console,
) -> AppServices:
    """Construct CLI runtime services from application settings."""

    repository = SessionRepository(SQLiteStore(settings.data_dir / "state.db"))
    provider = OpenAIProvider(
        model=settings.provider.model,
        api_key=settings.provider.api_key,
        base_url=settings.provider.base_url,
        timeout_seconds=settings.provider.timeout_seconds,
    )
    policy = PermissionPolicy(mode=settings.security.mode, workspace_root=workspace_root)
    runtime = ToolRuntime(
        tools=[ShellTool(), FSReadTool(), FSWriteTool(), SearchTool()],
        policy=policy,
        workspace_root=workspace_root,
    )
    approval_handler = _build_approval_handler(console=console)

    orchestrator = LangGraphOrchestrator(
        repository=repository,
        retrieval_service=RetrievalService(workspace_root),
        planner=PlannerAgent(provider),
        executor=ExecutorAgent(provider, runtime, approval_handler=approval_handler),
        reviewer=ReviewerAgent(provider),
    )
    return AppServices(orchestrator=orchestrator, repository=repository)


def _build_approval_handler(*, console: Console):
    def approval_handler(tool_call, decision) -> bool:
        prompt = (
            f"{decision.reason}\n"
            f"Approve tool `{tool_call.name}` with args {tool_call.arguments}?"
        )
        return typer.confirm(prompt, default=False)

    return approval_handler


def _render_result(result: OrchestratorResult) -> None:
    console.print(
        Panel.fit(
            result.final_output or "No output produced.",
            title=f"Session {result.session_id}",
        )
    )
