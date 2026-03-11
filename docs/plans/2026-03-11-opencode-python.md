# OpenCode Python MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python-first OpenCode MVP with CLI chat, tool-calling, permission gating, and session persistence.

**Architecture:** Use a layered design: CLI -> Agent Runtime -> Provider/Tools -> Storage. Keep the runtime provider-agnostic with a normalized message + tool schema. Persist sessions/events in SQLite and enforce tool permission checks before execution.

**Tech Stack:** Python 3.12, typer, rich, pydantic, openai SDK, pytest, pytest-asyncio, sqlite3

---

### Task 1: Scaffold Project Structure

**Files:**
- Create: `pyproject.toml`
- Create: `opencode_py/__init__.py`
- Create: `opencode_py/cli/main.py`
- Create: `opencode_py/core/runtime.py`
- Create: `opencode_py/providers/base.py`
- Create: `opencode_py/tools/base.py`
- Create: `opencode_py/session/models.py`
- Create: `opencode_py/storage/sqlite_store.py`
- Create: `tests/test_smoke_cli.py`

**Step 1: Write the failing test**

```python
from typer.testing import CliRunner
from opencode_py.cli.main import app


def test_cli_help_shows_commands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "chat" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke_cli.py -v`
Expected: FAIL with import/module errors

**Step 3: Write minimal implementation**

```python
import typer

app = typer.Typer()

@app.command()
def chat() -> None:
    print("chat")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml opencode_py tests
git commit -m "chore: scaffold opencode python project"
```

### Task 2: Define Core Message/Tool Schemas

**Files:**
- Create: `opencode_py/core/schemas.py`
- Modify: `opencode_py/providers/base.py`
- Modify: `opencode_py/tools/base.py`
- Test: `tests/test_schemas.py`

**Step 1: Write the failing test**

```python
from opencode_py.core.schemas import Message, ToolCall


def test_tool_call_schema_roundtrip():
    call = ToolCall(name="shell", arguments={"cmd": "pwd"}, call_id="1")
    msg = Message(role="assistant", content="", tool_calls=[call])
    assert msg.tool_calls[0].name == "shell"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL with missing schema symbols

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel

class ToolCall(BaseModel):
    name: str
    arguments: dict
    call_id: str

class Message(BaseModel):
    role: str
    content: str
    tool_calls: list[ToolCall] = []
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add opencode_py/core/schemas.py opencode_py/providers/base.py opencode_py/tools/base.py tests/test_schemas.py
git commit -m "feat: add normalized message and tool schemas"
```

### Task 3: Implement OpenAI-Compatible Provider

**Files:**
- Create: `opencode_py/providers/openai_provider.py`
- Modify: `opencode_py/providers/base.py`
- Create: `tests/providers/test_openai_provider.py`

**Step 1: Write the failing test**

```python
from opencode_py.providers.openai_provider import OpenAIProvider


def test_provider_builds_request_payload():
    p = OpenAIProvider(model="gpt-4o-mini", api_key="x")
    payload = p._build_payload([])
    assert payload["model"] == "gpt-4o-mini"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/providers/test_openai_provider.py -v`
Expected: FAIL with missing provider implementation

**Step 3: Write minimal implementation**
- Implement request normalization
- Add response parsing for text + tool calls
- Add timeout/retry defaults

**Step 4: Run test to verify it passes**

Run: `pytest tests/providers/test_openai_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add opencode_py/providers tests/providers
git commit -m "feat: add openai compatible provider"
```

### Task 4: Build Tool Runtime + Permission Policy

**Files:**
- Create: `opencode_py/tools/shell_tool.py`
- Create: `opencode_py/tools/fs_tool.py`
- Create: `opencode_py/security/policy.py`
- Create: `tests/tools/test_shell_tool.py`
- Create: `tests/security/test_policy.py`

**Step 1: Write the failing test**

```python
from opencode_py.security.policy import PermissionPolicy


def test_policy_denies_blacklisted_command():
    policy = PermissionPolicy(mode="ask", deny_commands=["rm -rf /"])
    d = policy.check("shell", {"cmd": "rm -rf /"})
    assert d.allowed is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/security/test_policy.py -v`
Expected: FAIL with missing policy class

**Step 3: Write minimal implementation**
- Implement allow/ask/deny decision object
- Enforce policy before shell execution
- Add subprocess timeout and stdout/stderr capture

**Step 4: Run test to verify it passes**

Run: `pytest tests/security/test_policy.py tests/tools/test_shell_tool.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add opencode_py/tools opencode_py/security tests/tools tests/security
git commit -m "feat: add tools runtime and permission gating"
```

### Task 5: Implement Agent Loop (Tool-Calling)

**Files:**
- Modify: `opencode_py/core/runtime.py`
- Create: `tests/core/test_runtime_loop.py`

**Step 1: Write the failing test**

```python
def test_runtime_executes_tool_call_then_returns_answer():
    # mock provider returns tool_call then final response
    # assert runtime invokes tool and appends tool result
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_runtime_loop.py -v`
Expected: FAIL with unimplemented runtime behavior

**Step 3: Write minimal implementation**
- Implement loop with max iterations
- Resolve tool calls through registry
- Append assistant/tool messages and stop on final text

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_runtime_loop.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add opencode_py/core/runtime.py tests/core/test_runtime_loop.py
git commit -m "feat: implement agent runtime tool-calling loop"
```

### Task 6: Add Session Persistence (SQLite)

**Files:**
- Modify: `opencode_py/storage/sqlite_store.py`
- Create: `opencode_py/session/repository.py`
- Create: `tests/storage/test_sqlite_store.py`

**Step 1: Write the failing test**

```python
def test_save_and_reload_session_messages(tmp_path):
    # create store, persist events, reload by session_id
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_sqlite_store.py -v`
Expected: FAIL with missing table/query behavior

**Step 3: Write minimal implementation**
- Create sessions/events tables
- Add insert/load APIs
- Add schema init and migrations v1

**Step 4: Run test to verify it passes**

Run: `pytest tests/storage/test_sqlite_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add opencode_py/storage opencode_py/session tests/storage
git commit -m "feat: add sqlite-backed session persistence"
```

### Task 7: Complete CLI Commands and Config

**Files:**
- Modify: `opencode_py/cli/main.py`
- Create: `opencode_py/config/settings.py`
- Create: `tests/cli/test_chat_command.py`

**Step 1: Write the failing test**

```python
def test_chat_command_loads_config_and_runs_runtime():
    # invoke `opencode chat --model ...` and assert output
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_chat_command.py -v`
Expected: FAIL with missing command options/flow

**Step 3: Write minimal implementation**
- Add config resolution: env -> user config -> CLI args
- Add `chat`, `run`, `session list`, `session show`
- Wire runtime + provider + store

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_chat_command.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add opencode_py/cli opencode_py/config tests/cli
git commit -m "feat: wire cli commands and configuration"
```

### Task 8: End-to-End Verification and Packaging

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Modify: `pyproject.toml`
- Create: `tests/e2e/test_chat_e2e.py`

**Step 1: Write the failing test**

```python
def test_e2e_chat_with_mock_provider(tmp_path):
    # run CLI end-to-end with mock provider
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/e2e/test_chat_e2e.py -v`
Expected: FAIL before wiring e2e fixtures

**Step 3: Write minimal implementation**
- Add console script entrypoint `opencode`
- Document install/config/usage
- Add Makefile or task aliases (`test`, `lint`, `format`)

**Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add README.md .env.example pyproject.toml tests/e2e
git commit -m "chore: package project and add e2e coverage"
```
