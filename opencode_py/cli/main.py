"""Typer application entry point."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from opencode_py.agents import ExecutorAgent, PlannerAgent, ReviewerAgent
from opencode_py.config.settings import AppSettings
from opencode_py.core.graph import LangGraphOrchestrator, OrchestratorResult
from opencode_py.providers import OpenAIProvider
from opencode_py.retrieval import RetrievalService
from opencode_py.security.policy import PermissionPolicy
from opencode_py.session.models import SessionHistory, SessionRecord
from opencode_py.session.repository import SessionRepository
from opencode_py.storage import SQLiteStore
from opencode_py.tools import FSReadTool, FSWriteTool, SearchTool, ShellTool, ToolRuntime


app = typer.Typer(
    name="opencode",
    no_args_is_help=True,
    help="Local CLI coding assistant.",
)
session_app = typer.Typer(help="Inspect and resume stored sessions.")
app.add_typer(session_app, name="session")
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


@session_app.command("list")
def session_list(
    limit: int = typer.Option(20, min=1, max=200, help="Maximum number of sessions to show."),
    data_dir: Path | None = typer.Option(None, help="Override the application data directory."),
) -> None:
    """List stored sessions ordered by most recent update."""

    repository = _create_repository(_load_settings(data_dir=data_dir))
    _render_session_list(repository.list_sessions(limit=limit))


@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(..., help="Session id to inspect."),
    data_dir: Path | None = typer.Option(None, help="Override the application data directory."),
) -> None:
    """Show one session with events, artifacts, and checkpoint summary."""

    repository = _create_repository(_load_settings(data_dir=data_dir))
    history = repository.load_session(session_id)
    if history is None:
        console.print(f"Session `{session_id}` not found.", style="red")
        raise typer.Exit(code=1)
    _render_session_history(history)


@session_app.command("resume")
def session_resume(
    session_id: str = typer.Argument(..., help="Session id to resume."),
    model: str | None = typer.Option(None, help="Override the configured model."),
    data_dir: Path | None = typer.Option(None, help="Override the application data directory."),
    workspace_root: Path = typer.Option(Path.cwd(), help="Workspace root to operate on."),
    permission_mode: str | None = typer.Option(None, help="Override tool permission mode."),
) -> None:
    """Resume a session from its latest checkpoint."""

    settings = _load_settings(
        model=model,
        data_dir=data_dir,
        permission_mode=permission_mode,
    )
    services = create_app_services(
        settings=settings,
        workspace_root=workspace_root,
        console=console,
    )
    try:
        result = services.orchestrator.resume(session_id)
    except ValueError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc
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
    settings = _load_settings(
        model=model,
        data_dir=data_dir,
        permission_mode=permission_mode,
    )
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


def _load_settings(
    *,
    model: str | None = None,
    data_dir: Path | None = None,
    permission_mode: str | None = None,
) -> AppSettings:
    return AppSettings.from_sources(
        cli_overrides=_build_cli_overrides(
            model=model,
            data_dir=data_dir,
            permission_mode=permission_mode,
        )
    )


def _build_cli_overrides(
    *,
    model: str | None = None,
    data_dir: Path | None = None,
    permission_mode: str | None = None,
) -> dict[str, object]:
    overrides: dict[str, object] = {}
    if data_dir is not None:
        overrides["data_dir"] = data_dir
    if model is not None:
        overrides["provider"] = {"model": model}
    if permission_mode is not None:
        overrides["security"] = {"mode": permission_mode}
    return overrides


def _create_repository(settings: AppSettings) -> SessionRepository:
    return SessionRepository(SQLiteStore(settings.data_dir / "state.db"))


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


def _render_session_list(sessions: list[SessionRecord]) -> None:
    if not sessions:
        console.print("No sessions found.")
        return

    table = Table(title="Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Title")
    table.add_column("Updated At", style="green")
    table.add_column("Created At")

    for session in sessions:
        table.add_row(
            session.id,
            session.title or "-",
            _format_timestamp(session.updated_at),
            _format_timestamp(session.created_at),
        )
    console.print(table)


def _render_session_history(history: SessionHistory) -> None:
    checkpoint_step = "-"
    if history.latest_checkpoint is not None:
        checkpoint_step = str(history.latest_checkpoint.step)

    summary = Table.grid(padding=(0, 2))
    summary.add_row("Session", history.session.id)
    summary.add_row("Title", history.session.title or "-")
    summary.add_row("Created", _format_timestamp(history.session.created_at))
    summary.add_row("Updated", _format_timestamp(history.session.updated_at))
    summary.add_row("Messages", str(len(history.messages)))
    summary.add_row("Events", str(len(history.events)))
    summary.add_row("Artifacts", str(len(history.artifacts)))
    summary.add_row("Latest Checkpoint", checkpoint_step)
    console.print(Panel.fit(summary, title="Session Summary"))

    events_table = Table(title="Recent Events")
    events_table.add_column("Time", style="green")
    events_table.add_column("Type", style="cyan")
    events_table.add_column("Payload")
    for event in history.events[-10:]:
        events_table.add_row(
            _format_timestamp(event.created_at),
            event.type,
            str(event.payload),
        )
    console.print(events_table)

    artifacts_table = Table(title="Artifacts")
    artifacts_table.add_column("Time", style="green")
    artifacts_table.add_column("Kind", style="cyan")
    artifacts_table.add_column("Path")
    artifacts_table.add_column("Metadata")
    if history.artifacts:
        for artifact in history.artifacts:
            artifacts_table.add_row(
                _format_timestamp(artifact.created_at),
                artifact.kind,
                artifact.path or "-",
                str(artifact.metadata),
            )
    else:
        artifacts_table.add_row("-", "-", "-", "No artifacts recorded.")
    console.print(artifacts_table)


def _format_timestamp(value) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
