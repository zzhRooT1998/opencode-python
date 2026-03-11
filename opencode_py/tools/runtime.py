"""Runtime wrapper for tool lookup, permission checks, and audit capture."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opencode_py.core.schemas import ToolResult
from opencode_py.security.policy import PermissionDecision, PermissionPolicy
from opencode_py.tools.base import Tool, ToolContext


@dataclass(slots=True)
class ToolAuditEntry:
    """One audit log entry for a tool call."""

    tool_name: str
    arguments: dict[str, Any]
    decision: PermissionDecision
    result: ToolResult | None = None


class ToolRuntime:
    """Resolve and execute tools behind a unified interface."""

    def __init__(
        self,
        tools: list[Tool],
        policy: PermissionPolicy,
        workspace_root: str | Path,
        env: dict[str, str] | None = None,
    ) -> None:
        self.tools = {tool.name: tool for tool in tools}
        self.policy = policy
        self.context = ToolContext(workspace_root=Path(workspace_root).resolve(), env=env or {})
        self.audit_log: list[ToolAuditEntry] = []

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        approved: bool = False,
    ) -> ToolResult:
        """Execute one tool call if permitted."""

        tool = self.tools.get(tool_name)
        if tool is None:
            result = ToolResult(
                call_id=str(arguments.get("call_id", tool_name)),
                tool_name=tool_name,
                status="error",
                stderr=f"Unknown tool: {tool_name}",
            )
            self.audit_log.append(
                ToolAuditEntry(
                    tool_name=tool_name,
                    arguments=arguments,
                    decision=PermissionDecision(
                        mode="deny",
                        allowed=False,
                        requires_confirmation=False,
                        reason="Unknown tool.",
                    ),
                    result=result,
                )
            )
            return result

        decision = self.policy.check(tool_name, arguments)
        if decision.requires_confirmation and not approved:
            result = ToolResult(
                call_id=str(arguments.get("call_id", tool_name)),
                tool_name=tool_name,
                status="error",
                stderr=decision.reason,
                metadata={"permission": "ask"},
            )
            self.audit_log.append(
                ToolAuditEntry(tool_name=tool_name, arguments=arguments, decision=decision, result=result)
            )
            return result

        if not decision.allowed and not (decision.requires_confirmation and approved):
            result = ToolResult(
                call_id=str(arguments.get("call_id", tool_name)),
                tool_name=tool_name,
                status="error",
                stderr=decision.reason,
                metadata={"permission": "deny"},
            )
            self.audit_log.append(
                ToolAuditEntry(tool_name=tool_name, arguments=arguments, decision=decision, result=result)
            )
            return result

        result = tool.invoke(arguments, self.context)
        self.audit_log.append(
            ToolAuditEntry(tool_name=tool_name, arguments=arguments, decision=decision, result=result)
        )
        return result

