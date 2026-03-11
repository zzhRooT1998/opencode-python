# OpenCode Python MVP Task Breakdown

## 1. 文档信息
- 日期：2026-03-11
- 状态：Draft v1
- 适用范围：`opencode-python` 项目 MVP 实施拆解
- 关联文档：
  - `docs/plans/2026-03-11-opencode-python-prd.md`
  - `docs/plans/2026-03-11-opencode-python-architecture.md`

## 2. 执行约定
- 任务按依赖顺序推进，除非明确标注可并行。
- 每个任务完成后必须更新本文件中的 `状态`、`完成日期`、`备注`。
- 当前执行约定：每个任务完成后必须执行一次 `git commit`。
- 说明：原计划要求每个任务都 `git push`，但当前环境下 GitHub HTTPS 推送持续超时，因此后续任务先以本地 commit 为准。
- 任务完成的最低标准：代码落地、相关测试通过、文档/配置同步更新。

## 3. 状态说明
- `todo`：未开始
- `doing`：进行中
- `blocked`：被依赖、设计或环境问题阻塞
- `done`：已完成并达到当前验收标准

## 4. 阶段划分
### Phase 0：项目骨架与基础约束
- T01 项目脚手架与打包入口
- T02 核心 schema、配置模型与目录结构

### Phase 1：基础运行时能力
- T03 存储层、会话模型与 checkpoint
- T04 Provider 抽象与 OpenAI-compatible 接入
- T05 Tool Runtime 与权限策略

### Phase 2：检索与 Agent 主链路
- T06 轻量 RAG 索引与检索服务
- T07 Planner Agent
- T08 Executor Agent（ReAct-style）
- T09 Reviewer Agent
- T10 LangGraph Orchestrator

### Phase 3：CLI 闭环与质量
- T11 CLI 命令与渲染输出
- T12 会话查询、恢复与审计呈现
- T13 测试、样例文档与发布准备

## 5. 任务明细

### T01 项目脚手架与打包入口
- 状态：`done`
- 完成日期：2026-03-11
- 依赖：无
- 目标：建立可运行的 Python 项目基础结构，确保 CLI 可以启动。
- 交付物：
  - `pyproject.toml`
  - `opencode_py/` 基础包结构
  - `opencode` console script 入口
  - 最小可运行的 `chat` 命令占位
- 验收标准：
  - `python -m opencode_py` 或等效入口可运行
  - `opencode --help` 可展示命令帮助
  - 基础 smoke test 通过
- 备注：
  - 已新增 `pyproject.toml`、`opencode_py` 包骨架、CLI 入口和 smoke test
  - 已新增 `.gitignore`，忽略 `.idea/` 和常见 Python 产物
  - 验证命令：`python -m pytest tests/test_smoke_cli.py -v`、`python -m opencode_py --help`

### T02 核心 schema、配置模型与目录结构
- 状态：`done`
- 完成日期：2026-03-11
- 依赖：T01
- 目标：统一运行时对象和配置加载方式，避免后续模块各自定义协议。
- 交付物：
  - 标准化消息 schema
  - tool call / tool result schema
  - agent state schema
  - app settings / provider settings / security settings
  - 与架构文档一致的目录骨架
- 验收标准：
  - Provider、Tool、Graph 共享同一套 schema
  - 配置支持 CLI 参数、用户配置、环境变量三层来源
  - 关键 schema 有单测覆盖
- 备注：
  - 已新增 `opencode_py/core/schemas.py`，统一消息、工具结果、计划步骤和 agent state
  - 已新增 `opencode_py/config/settings.py`，实现 env -> config file -> CLI override 的加载优先级
  - 已补齐 `agents`、`retrieval`、`security`、`core/graph`、`core/runtime` 目录骨架
  - 验证命令：`python -m pytest tests/core/test_schemas.py tests/config/test_settings.py -v`

### T03 存储层、会话模型与 checkpoint
- 状态：`done`
- 完成日期：2026-03-11
- 依赖：T02
- 目标：实现会话持久化、事件记录、产物保存和 graph checkpoint。
- 交付物：
  - SQLite store
  - `sessions` / `events` / `artifacts` / `checkpoints` 表初始化
  - session repository
  - checkpoint 读写接口
- 验收标准：
  - 能保存并读取 session 历史
  - 能按 step 落盘 checkpoint
  - 表初始化和基本 CRUD 有测试覆盖
- 备注：
  - 已新增 `opencode_py/storage/sqlite_store.py`，实现 SQLite 表初始化、session/event/artifact/checkpoint CRUD
  - 已新增 `opencode_py/session/models.py` 和 `opencode_py/session/repository.py`
  - checkpoint 直接持久化 `AgentState` JSON，便于后续 graph 恢复
  - 验证命令：`python -m pytest tests/storage/test_sqlite_store.py tests/session/test_repository.py -v`
  - 全量验证：`python -m pytest -v`

### T04 Provider 抽象与 OpenAI-compatible 接入
- 状态：`done`
- 完成日期：2026-03-11
- 依赖：T02
- 目标：实现与模型服务的统一交互层，支持文本与工具调用。
- 交付物：
  - provider base interface
  - OpenAI-compatible provider 实现
  - 请求/响应标准化转换
  - 超时、重试和错误归一化
- 验收标准：
  - 能构造符合目标 provider 的请求
  - 能解析文本响应和 tool call 响应
  - provider 单测覆盖成功与失败路径
- 备注：
  - 已新增 `opencode_py/providers/base.py` 和 `opencode_py/providers/openai_provider.py`
  - 已补齐统一 tool definition 和 provider output 抽象
  - OpenAI-compatible provider 已实现消息序列化、tool schema 序列化和响应解析
  - 验证命令：`python -m pytest tests/providers/test_openai_provider.py -v`
  - 全量验证：`python -m pytest -v`

### T05 Tool Runtime 与权限策略
- 状态：`done`
- 完成日期：2026-03-11
- 依赖：T02
- 目标：实现统一工具调用入口与安全控制。
- 交付物：
  - tool base interface
  - `shell`、`fs_read`、`fs_write`、`search` 工具
  - permission policy
  - 审计记录模型
- 验收标准：
  - 工具调用统一返回标准结果
  - 高风险命令可被 `ask` 或 `deny`
  - shell 工具支持超时、输出截断、stderr 捕获
  - 工具与权限策略有单测覆盖
- 备注：
  - 已新增 `PermissionPolicy`、`ToolRuntime` 和 `shell/fs_read/fs_write/search` 工具
  - ask/allow/deny 三类权限决策已经打通
  - 工具结果统一落到 `ToolResult`，支持 stdout/stderr/metadata/artifacts
  - 验证命令：`python -m pytest tests/security/test_policy.py tests/tools/test_tools_runtime.py -v`
  - 全量验证：`python -m pytest -v`

### T06 轻量 RAG 索引与检索服务
- 状态：`done`
- 完成日期：2026-03-11
- 依赖：T02、T05
- 目标：实现 MVP 级别的代码检索链路，向 Agent 提供 evidence pack。
- 交付物：
  - 文件发现与过滤
  - 代码切片器
  - 关键词/BM25 检索
  - rerank 接口
  - evidence pack 组装服务
- 验收标准：
  - 给定任务描述能返回带路径和行号的候选代码片段
  - 检索结果能按相关度重排
  - 检索无结果时返回可识别的空结果状态
- 备注：
  - 已新增 repository indexer、keyword ranker、heuristic reranker 和 retrieval service
  - Python 文件优先按函数/类切片，其他文本文件按固定行数切片
  - evidence pack 已包含 path、line_start、line_end、snippet、score、reason
  - 验证命令：`python -m pytest tests/retrieval/test_service.py -v`
  - 全量验证：`python -m pytest -v`

### T07 Planner Agent
- 状态：`todo`
- 完成日期：
- 依赖：T04、T06
- 目标：把用户目标和检索摘要转成结构化计划。
- 交付物：
  - planner prompt/template
  - 结构化 step list 输出模型
  - 最大步骤数与计划约束控制
- 验收标准：
  - 给定输入可产出可执行 step list
  - step 至少包含目标、建议工具和完成判定依据
  - planner 单测覆盖结构化输出解析
- 备注：

### T08 Executor Agent（ReAct-style）
- 状态：`todo`
- 完成日期：
- 依赖：T04、T05、T06、T07
- 目标：实现 `reason -> act -> observe -> continue` 的执行循环。
- 交付物：
  - executor prompt/template
  - tool call dispatch 逻辑
  - tool result 回填逻辑
  - 单步最大循环次数限制
- 验收标准：
  - 能处理“直接回答”和“先调工具再继续推理”两类路径
  - 工具结果会写回消息历史并触发下一轮推理
  - executor 单测覆盖 ReAct 主循环
- 备注：

### T09 Reviewer Agent
- 状态：`todo`
- 完成日期：
- 依赖：T04、T08
- 目标：实现结果验收、重试建议和中止决策。
- 交付物：
  - reviewer prompt/template
  - `accept / revise / abort` 输出模型
  - 审查理由与重试建议结构
- 验收标准：
  - 能对步骤结果给出结构化审查结论
  - 遇到工具失败、结果不完整或高风险结果时可拒绝通过
  - reviewer 单测覆盖三种决策分支
- 备注：

### T10 LangGraph Orchestrator
- 状态：`todo`
- 完成日期：
- 依赖：T03、T06、T07、T08、T09
- 目标：把 Planner、Retriever、Executor、Reviewer 串成主执行链路。
- 交付物：
  - graph state
  - graph nodes：`load_context`、`retrieve_context`、`plan`、`execute_step`、`review_step`、`commit_or_retry`、`finalize`
  - 重试策略与终止条件
  - checkpoint 恢复逻辑
- 验收标准：
  - graph 能完整跑通单任务闭环
  - Reviewer `revise` 时可回到当前 step 重试
  - 中断后可从 checkpoint 恢复
- 备注：

### T11 CLI 命令与渲染输出
- 状态：`todo`
- 完成日期：
- 依赖：T03、T04、T10
- 目标：把运行时能力接入 CLI，形成可用的用户入口。
- 交付物：
  - `chat` 命令
  - `run` 命令
  - Rich 输出渲染器
  - 权限确认交互
- 验收标准：
  - 用户可以发起真实任务并获得结构化输出
  - 权限确认可通过 CLI 完成
  - CLI 在非交互模式下也能输出可读结果
- 备注：

### T12 会话查询、恢复与审计呈现
- 状态：`todo`
- 完成日期：
- 依赖：T03、T10、T11
- 目标：补齐 session 查询、任务追踪与恢复体验。
- 交付物：
  - `session list`
  - `session show`
  - 会话恢复入口
  - 审计摘要展示
- 验收标准：
  - 可查看历史 session 列表
  - 可查看单个 session 的关键事件和产物
  - 中断任务可基于 checkpoint 恢复
- 备注：

### T13 测试、样例文档与发布准备
- 状态：`todo`
- 完成日期：
- 依赖：T11、T12
- 目标：补齐交付闭环，确保 MVP 可验证、可安装、可复现。
- 交付物：
  - 单测、集成测试、E2E 测试
  - `.env.example`
  - README 使用说明
  - 基础任务脚本或命令说明
- 验收标准：
  - 核心测试集通过
  - 本地安装和最小使用流程可按文档复现
  - 文档覆盖配置、命令、权限模式和已知限制
- 备注：

## 6. 推荐执行顺序
1. T01 -> T02
2. T03 / T04 / T05
3. T06 -> T07 -> T08 -> T09
4. T10
5. T11 -> T12
6. T13

## 7. 可并行任务建议
- T03 与 T04 可并行，但都依赖 T02 完成。
- T05 可与 T03、T04 并行推进。
- T07 与 T06 后半段可以交错推进，但正式联调前需要 evidence pack 输出稳定。
- T11 前可以先由 T10 提供 mock 输出做 CLI 对接。

## 8. 状态更新模板

```md
### Txx 任务名
- 状态：`doing`
- 完成日期：2026-03-11
- 依赖：Tyy
- 备注：
  - commit: `abc1234`
  - push: `origin/main`
  - 说明：完成 xxx，待补 xxx
```
