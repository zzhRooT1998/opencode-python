from pathlib import Path

from opencode_py.security.policy import PermissionPolicy
from opencode_py.tools import FSReadTool, FSWriteTool, SearchTool, ShellTool, ToolRuntime


def test_shell_tool_captures_stdout(tmp_path: Path) -> None:
    runtime = ToolRuntime(
        tools=[ShellTool()],
        policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
        workspace_root=tmp_path,
    )

    result = runtime.invoke("shell", {"cmd": 'python -c "print(123)"', "call_id": "1"})

    assert result.status == "success"
    assert "123" in result.stdout


def test_fs_tools_roundtrip(tmp_path: Path) -> None:
    runtime = ToolRuntime(
        tools=[FSWriteTool(), FSReadTool()],
        policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
        workspace_root=tmp_path,
    )

    write_result = runtime.invoke(
        "fs_write",
        {"path": str(tmp_path / "notes.txt"), "content": "hello", "call_id": "write-1"},
        approved=True,
    )
    read_result = runtime.invoke(
        "fs_read",
        {"path": str(tmp_path / "notes.txt"), "call_id": "read-1"},
    )

    assert write_result.status == "success"
    assert read_result.stdout == "hello"


def test_search_tool_finds_matches(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run_task():\n    return 'ok'\n", encoding="utf-8")
    runtime = ToolRuntime(
        tools=[SearchTool()],
        policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
        workspace_root=tmp_path,
    )

    result = runtime.invoke("search", {"query": "run_task", "call_id": "search-1"})

    assert result.status == "success"
    assert "app.py" in result.stdout


def test_runtime_requires_confirmation_in_ask_mode(tmp_path: Path) -> None:
    runtime = ToolRuntime(
        tools=[FSWriteTool()],
        policy=PermissionPolicy(mode="ask", workspace_root=tmp_path),
        workspace_root=tmp_path,
    )

    result = runtime.invoke(
        "fs_write",
        {"path": str(tmp_path / "draft.txt"), "content": "hello", "call_id": "write-1"},
    )

    assert result.status == "error"
    assert result.metadata["permission"] == "ask"

