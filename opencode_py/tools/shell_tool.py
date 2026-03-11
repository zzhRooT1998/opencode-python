"""Shell command tool."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from opencode_py.core.schemas import ToolResult
from opencode_py.tools.base import Tool, ToolContext


class ShellTool(Tool):
    """Execute a shell command in the workspace."""

    name = "shell"
    description = "Run a shell command in the workspace."

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        command = str(arguments.get("cmd", "")).strip()
        timeout_seconds = float(arguments.get("timeout_seconds", 30))
        call_id = str(arguments.get("call_id", self.name))

        if not command:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                status="error",
                stderr="Shell command cannot be empty.",
            )

        env = os.environ.copy()
        env.update(context.env)

        try:
            completed = subprocess.run(
                command,
                cwd=context.workspace_root,
                env=env,
                capture_output=True,
                text=True,
                shell=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                status="error",
                stdout=_truncate(error.stdout or ""),
                stderr=f"Command timed out after {timeout_seconds} seconds.",
                metadata={"timeout_seconds": timeout_seconds},
            )

        status = "success" if completed.returncode == 0 else "error"
        return ToolResult(
            call_id=call_id,
            tool_name=self.name,
            status=status,
            stdout=_truncate(completed.stdout),
            stderr=_truncate(completed.stderr),
            metadata={"returncode": completed.returncode, "command": command},
        )


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 14] + "\n...[truncated]"

