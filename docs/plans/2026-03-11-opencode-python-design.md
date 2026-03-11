# OpenCode Python 版本设计草案

## 1. 目标与范围
- 目标：实现一个可用的 `opencode` Python 版本（CLI + 基础 Agent Runtime），优先覆盖日常代码助手核心链路。
- 非目标（v1 不做）：完整 TUI 复刻、复杂多 Agent 编排、云同步、语音、多模态。

## 2. 上游项目能力拆解（用于对齐）
根据 `anomalyco/opencode` 仓库结构（`packages/opencode/src`）可抽象出这些能力域：
- `command` / `cli`：命令行入口与命令体系
- `provider` / `model`：模型提供商抽象与多模型接入
- `tool`：工具调用（shell/fs 等）
- `session` / `history` / `storage`：会话与持久化
- `permission` / `config`：权限与配置
- `agent` / `workflow`：任务执行与步骤编排

## 3. Python 版本设计
### 3.1 架构分层
- `opencode_py/cli/`：`typer` 命令定义（chat/run/config/session）
- `opencode_py/core/`：Agent loop（计划-执行-观察）
- `opencode_py/providers/`：LLM Provider 接口与实现（OpenAI/兼容 OpenAI）
- `opencode_py/tools/`：Tool 协议 + shell/fs/search 等工具
- `opencode_py/session/`：会话状态、消息历史、token usage
- `opencode_py/storage/`：SQLite 持久化（会话、事件、配置）
- `opencode_py/security/`：权限策略（allow/ask/deny）
- `opencode_py/config/`：`pyproject.toml` + `~/.opencode/config.toml`

### 3.2 关键接口
- `Provider.generate(messages, tools, config) -> ModelOutput`
- `Tool.invoke(args, context) -> ToolResult`
- `Agent.run(task, session_id, policy) -> RunSummary`
- `PermissionPolicy.check(tool_name, args) -> Decision`

### 3.3 数据流
1. CLI 接收用户输入并载入配置
2. Agent 读取会话上下文与可用工具
3. LLM 返回文本或工具调用请求
4. Runtime 执行工具并回填结果
5. 循环直到完成，落库并输出

## 4. 技术选型
- CLI：`typer` + `rich`
- 模型接入：`openai` SDK（先做 OpenAI-compatible）
- 数据模型：`pydantic`
- 存储：`sqlite3` / `sqlmodel`（二选一，建议先 sqlite3 原生）
- 测试：`pytest` + `pytest-asyncio`

## 5. 风险与应对
- 风险：工具调用失控（危险命令）
- 应对：默认 `ask` 权限 + 命令白名单 + 超时
- 风险：会话上下文膨胀
- 应对：窗口裁剪 + 摘要压缩
- 风险：Provider 差异
- 应对：统一内部 message/tool schema

## 6. 里程碑定义
- M1（1 周）：可运行 CLI + 单 Provider 文本对话
- M2（1 周）：工具调用（shell/fs）+ 权限确认
- M3（1 周）：会话持久化 + 恢复会话
- M4（1 周）：稳定性（重试/超时/日志）+ 打包发布
