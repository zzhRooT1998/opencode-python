"""Permission policy for tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opencode_py.config.settings import PermissionMode


@dataclass(slots=True)
class PermissionDecision:
    """Normalized permission outcome for one tool invocation."""

    mode: PermissionMode
    allowed: bool
    requires_confirmation: bool
    reason: str


class PermissionPolicy:
    """Apply allow/ask/deny rules to tool invocations."""

    def __init__(
        self,
        mode: PermissionMode = "ask",
        deny_commands: list[str] | None = None,
        workspace_root: str | Path | None = None,
        allowed_write_roots: list[str | Path] | None = None,
    ) -> None:
        self.mode = mode
        self.deny_commands = tuple(command.lower() for command in (deny_commands or []))
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.allowed_write_roots = [
            Path(root).resolve()
            for root in (allowed_write_roots or ([workspace_root] if workspace_root else []))
        ]

    def check(self, tool_name: str, args: dict[str, Any]) -> PermissionDecision:
        """Return a permission decision for a requested tool call."""

        if tool_name == "shell":
            return self._check_shell(args)
        if tool_name == "fs_write":
            return self._check_fs_write(args)
        if tool_name in {"fs_read", "search"}:
            return PermissionDecision(
                mode=self.mode,
                allowed=True,
                requires_confirmation=False,
                reason="Read-only tool allowed.",
            )
        return PermissionDecision(
            mode="deny",
            allowed=False,
            requires_confirmation=False,
            reason=f"Unknown tool: {tool_name}",
        )

    def _check_shell(self, args: dict[str, Any]) -> PermissionDecision:
        command = str(args.get("cmd", "")).strip()
        lowered = command.lower()

        if not command:
            return PermissionDecision(
                mode="deny",
                allowed=False,
                requires_confirmation=False,
                reason="Shell command cannot be empty.",
            )

        if any(blocked in lowered for blocked in self.deny_commands):
            return PermissionDecision(
                mode="deny",
                allowed=False,
                requires_confirmation=False,
                reason="Command matched deny list.",
            )

        high_risk_tokens = (
            "rm -rf",
            "del /f",
            "format ",
            "shutdown",
            "reboot",
            "sudo ",
            "chmod 777",
            "curl ",
            "wget ",
            "Invoke-WebRequest",
        )
        if any(token.lower() in lowered for token in high_risk_tokens):
            return PermissionDecision(
                mode="ask",
                allowed=False,
                requires_confirmation=True,
                reason="High-risk shell command requires confirmation.",
            )

        if self.mode == "deny":
            return PermissionDecision(
                mode="deny",
                allowed=False,
                requires_confirmation=False,
                reason="Shell execution disabled by policy.",
            )

        if self.mode == "ask":
            return PermissionDecision(
                mode="ask",
                allowed=False,
                requires_confirmation=True,
                reason="Shell execution requires confirmation in ask mode.",
            )

        return PermissionDecision(
            mode="allow",
            allowed=True,
            requires_confirmation=False,
            reason="Shell execution allowed.",
        )

    def _check_fs_write(self, args: dict[str, Any]) -> PermissionDecision:
        path_value = args.get("path")
        if not path_value:
            return PermissionDecision(
                mode="deny",
                allowed=False,
                requires_confirmation=False,
                reason="fs_write requires a target path.",
            )

        target = Path(path_value).resolve()
        if self.allowed_write_roots and not any(
            _is_relative_to(target, root) for root in self.allowed_write_roots
        ):
            return PermissionDecision(
                mode="deny",
                allowed=False,
                requires_confirmation=False,
                reason="Target path is outside allowed write roots.",
            )

        if self.mode == "deny":
            return PermissionDecision(
                mode="deny",
                allowed=False,
                requires_confirmation=False,
                reason="File writes disabled by policy.",
            )

        if self.mode == "ask":
            return PermissionDecision(
                mode="ask",
                allowed=False,
                requires_confirmation=True,
                reason="File writes require confirmation in ask mode.",
            )

        return PermissionDecision(
            mode="allow",
            allowed=True,
            requires_confirmation=False,
            reason="File write allowed.",
        )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

