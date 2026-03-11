"""Filesystem tools for reading and writing repository files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode_py.core.schemas import ToolResult
from opencode_py.tools.base import Tool, ToolContext


class FSReadTool(Tool):
    """Read text from a file path."""

    name = "fs_read"
    description = "Read file contents from the workspace."

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        call_id = str(arguments.get("call_id", self.name))
        target = _resolve_path(arguments, context)
        if target is None:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                status="error",
                stderr="A valid file path is required.",
            )

        if not target.exists():
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                status="error",
                stderr=f"File not found: {target}",
            )

        content = target.read_text(encoding="utf-8")
        return ToolResult(
            call_id=call_id,
            tool_name=self.name,
            status="success",
            stdout=content,
            metadata={"path": str(target)},
        )


class FSWriteTool(Tool):
    """Write text to a file path."""

    name = "fs_write"
    description = "Write file contents within the workspace."

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        call_id = str(arguments.get("call_id", self.name))
        target = _resolve_path(arguments, context)
        if target is None:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                status="error",
                stderr="A valid file path is required.",
            )

        content = str(arguments.get("content", ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            call_id=call_id,
            tool_name=self.name,
            status="success",
            stdout=f"Wrote {len(content)} bytes.",
            metadata={"path": str(target)},
            artifacts=[str(target)],
        )


def _resolve_path(arguments: dict[str, Any], context: ToolContext) -> Path | None:
    path_value = arguments.get("path")
    if not path_value:
        return None
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = context.workspace_root / candidate
    return candidate.resolve()

