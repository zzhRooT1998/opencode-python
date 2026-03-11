"""Repository text search tool built on ripgrep when available."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from opencode_py.core.schemas import ToolResult
from opencode_py.tools.base import Tool, ToolContext


class SearchTool(Tool):
    """Search repository text using ripgrep with a Python fallback."""

    name = "search"
    description = "Search files in the workspace."

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        query = str(arguments.get("query", "")).strip()
        call_id = str(arguments.get("call_id", self.name))
        if not query:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                status="error",
                stderr="Search query cannot be empty.",
            )

        if shutil.which("rg"):
            return self._run_ripgrep(query, call_id, context.workspace_root)
        return self._run_python_search(query, call_id, context.workspace_root)

    def _run_ripgrep(self, query: str, call_id: str, workspace_root: Path) -> ToolResult:
        completed = subprocess.run(
            ["rg", "--line-number", "--no-heading", query, str(workspace_root)],
            capture_output=True,
            text=True,
            check=False,
        )
        status = "success" if completed.returncode in {0, 1} else "error"
        return ToolResult(
            call_id=call_id,
            tool_name=self.name,
            status=status,
            stdout=completed.stdout,
            stderr=completed.stderr,
            metadata={"engine": "rg", "query": query, "returncode": completed.returncode},
        )

    def _run_python_search(self, query: str, call_id: str, workspace_root: Path) -> ToolResult:
        matches: list[str] = []
        lower_query = query.lower()
        for file_path in workspace_root.rglob("*"):
            if not file_path.is_file():
                continue
            if ".git" in file_path.parts or "__pycache__" in file_path.parts:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if lower_query in line.lower():
                    matches.append(f"{file_path}:{line_number}:{line}")
        return ToolResult(
            call_id=call_id,
            tool_name=self.name,
            status="success",
            stdout="\n".join(matches),
            metadata={"engine": "python", "query": query, "matches": len(matches)},
        )

