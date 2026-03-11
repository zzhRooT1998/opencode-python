from pathlib import Path

from opencode_py.security.policy import PermissionPolicy


def test_policy_denies_blacklisted_command() -> None:
    policy = PermissionPolicy(mode="ask", deny_commands=["rm -rf /"])

    decision = policy.check("shell", {"cmd": "rm -rf /"})

    assert decision.allowed is False
    assert decision.requires_confirmation is False


def test_policy_requires_confirmation_for_workspace_writes(tmp_path: Path) -> None:
    policy = PermissionPolicy(mode="ask", workspace_root=tmp_path)

    decision = policy.check("fs_write", {"path": str(tmp_path / "app.py")})

    assert decision.allowed is False
    assert decision.requires_confirmation is True


def test_policy_denies_write_outside_workspace(tmp_path: Path) -> None:
    policy = PermissionPolicy(mode="allow", workspace_root=tmp_path)

    decision = policy.check("fs_write", {"path": str(tmp_path.parent / "outside.py")})

    assert decision.allowed is False
    assert "outside" in decision.reason.lower()

