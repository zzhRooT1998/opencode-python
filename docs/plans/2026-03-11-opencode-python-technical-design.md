# OpenCode Python 技术方案（多 Agent + RAG + Symbol Graph）

## 1. 文档信息
- 日期：2026-03-11
- 状态：Draft v1
- 适用范围：`opencode-python` 项目 MVP 到 v1.0

## 2. 目标与非目标
### 2.1 目标
- 构建一个 Python 版 OpenCode CLI Agent，支持多 Agent 协作完成代码任务。
- 以 `LangGraph` 作为运行时主干，保证可观测、可恢复、可扩展。
- 集成代码检索能力：先上轻量 RAG，再引入 Symbol Graph 增强跨文件理解。
- 兼容 OpenAI-compatible 模型接口，后续可扩展其他 Provider。

### 2.2 非目标（MVP 阶段）
- 不追求完整复刻上游 TUI 或所有交互能力。
- 不做复杂云端同步与团队协作权限系统。
- 不做全语言通用语义图（先聚焦 Python/TS 两类主流代码结构）。

## 3. 总体架构

```text
CLI (Typer)
  -> Orchestrator Graph (LangGraph)
      -> Planner Agent
      -> Executor Agent
      -> Reviewer Agent
      -> Retrieval Subsystem (RAG + Symbol Graph)
      -> Tool Runtime (shell/fs/search)
      -> Permission Policy
      -> Session/State Store (SQLite)
  -> Output Renderer (Rich)
```

### 3.1 关键设计决策
- 运行时：`LangGraph`（状态机、checkpoint、恢复执行）。
- Agent 形态：固定 3 角色（Planner/Executor/Reviewer），避免角色爆炸。
- 检索路径：`关键词召回 -> rerank -> 图增强召回`。
- 存储：SQLite 单机优先，支持后续切 PostgreSQL。

## 4. Agent 设计

### 4.1 Planner Agent
- 输入：用户目标、历史上下文、检索摘要。
- 输出：结构化执行计划（step list，含每步目标与工具建议）。
- 约束：最多生成 N 步（默认 8），避免长链路失控。

### 4.2 Executor Agent
- 输入：当前步骤、工具上下文、权限策略。
- 输出：工具调用结果与步骤产物。
- 约束：工具调用前必须经过 `PermissionPolicy`。

### 4.3 Reviewer Agent
- 输入：执行产物、原目标、约束条件。
- 输出：`accept`/`revise`/`abort` 决策与理由。
- 约束：发现风险命令、结果不完整、测试失败时必须拒绝通过。

### 4.4 Agent 间协作协议
- 消息格式统一为：`role`, `content`, `tool_calls`, `artifacts`, `trace_id`。
- 所有节点仅通过共享状态读写，禁止跨节点直接副作用调用。

## 5. LangGraph 编排

### 5.1 图节点
- `load_context`
- `retrieve_context`
- `plan`
- `execute_step`
- `review_step`
- `commit_or_retry`
- `finalize`

### 5.2 状态模型（核心字段）
- `session_id`: str
- `user_goal`: str
- `plan_steps`: list[PlanStep]
- `current_step`: int
- `messages`: list[Message]
- `retrieval_hits`: list[RetrievalChunk]
- `artifacts`: dict
- `decision`: Literal[continue, retry, done, abort]

### 5.3 终止条件
- 全部步骤通过 Reviewer。
- 达到最大重试次数（默认每步 2 次）。
- 命中安全策略中止。

## 6. 检索系统设计（RAG）

### 6.1 为什么需要 RAG
- 代码任务需要大规模上下文定位，仅靠对话窗口不足。
- RAG 提供“按需取证”能力，降低幻觉与误改风险。

### 6.2 MVP 检索链路
1. 文件枚举与分块（按函数/类/段落切片）
2. 关键词/BM25 召回（高精度起步）
3. rerank（交叉编码器或 LLM rerank）
4. 注入 Agent 上下文（带来源路径与行号）

### 6.3 v1 增强
- 引入 embedding 向量召回，形成混合检索（BM25 + Vector）。
- 增加“任务类型模板”检索策略（debug/refactor/feature 文档权重不同）。

## 7. Symbol Graph 设计

### 7.1 为什么需要 Symbol Graph
- 多文件代码修改依赖符号关系（定义、引用、调用链）。
- 图结构可显著提升“影响范围分析”和“精准召回”。

### 7.2 MVP 图模型
- 节点类型：`File`, `Symbol`（function/class/method）
- 边类型：`defines`, `references`, `calls`, `imports`
- 元数据：`path`, `line_start`, `line_end`, `language`

### 7.3 构建策略
- Python：优先 AST + 静态分析。
- TypeScript：优先 Tree-sitter/tsserver 结果。
- 增量更新：基于 git diff 或文件 mtime 重建受影响子图。

### 7.4 与 RAG 融合
- 查询阶段先做文本召回，再做符号扩展（1-hop/2-hop）。
- 最终上下文按“相关性 + 距离 + 变更风险”排序。

## 8. 工具与安全

### 8.1 工具集（首批）
- `shell`: 执行命令（超时、沙箱、输出截断）
- `fs_read`: 文件读取（范围读取）
- `fs_write`: 文件写入（白名单路径）
- `search`: 代码检索（rg 优先）

### 8.2 权限策略
- 模式：`allow` / `ask` / `deny`（默认 `ask`）。
- 高危命令（如删除/网络写入/权限提升）默认拒绝。
- 每次工具调用记录审计日志（请求参数、执行人、结果摘要）。

## 9. 数据存储

### 9.1 SQLite 表结构（建议）
- `sessions(id, created_at, updated_at, title)`
- `events(id, session_id, type, payload_json, created_at)`
- `artifacts(id, session_id, kind, path, metadata_json)`
- `symbol_index(id, repo, symbol, path, line_start, line_end, lang, hash)`

### 9.2 持久化策略
- Graph checkpoint 每步落盘，支持异常恢复。
- 检索索引异步更新，不阻塞主流程。

## 10. 可观测性与质量

### 10.1 可观测性
- 统一 `trace_id` 贯穿 CLI -> Graph -> Tool。
- 输出三类日志：业务日志、工具日志、安全审计日志。

### 10.2 测试策略
- 单测：状态转换、权限决策、检索排序。
- 集成：单次任务完整图执行。
- E2E：从 CLI 输入到文件变更与测试验证。

### 10.3 验收指标（MVP）
- 任务成功率（人工评估）>= 70%
- 危险命令误放行率 = 0
- 单任务中位耗时 <= 60s（中等仓库）

## 11. 分阶段实施

### Phase 1：多 Agent 主干
- 完成 3 Agent + LangGraph 节点流。
- 接入 shell/fs/search 工具与权限策略。

### Phase 2：轻量 RAG
- 完成分块、BM25、rerank、上下文注入。
- 在 debug/定位类任务上验证收益。

### Phase 3：Symbol Graph
- 完成 symbol 抽取与关系图。
- 接入 1-hop/2-hop 扩展召回并对比基线。

### Phase 4：稳定性
- checkpoint 恢复、重试策略、日志完善。
- 打包发布与配置文档。

## 12. 风险与缓解
- 风险：多 Agent 循环导致成本和延迟上升。
- 缓解：限制步骤数与重试次数，优先短路径计划。

- 风险：Symbol Graph 构建耗时高。
- 缓解：增量索引 + 后台构建 + 按需语言支持。

- 风险：RAG 召回噪音高。
- 缓解：强制 rerank + 来源可解释（路径/行号/分数）。

## 13. 开发约束
- 默认 Python 3.12。
- CLI 输出必须可在非交互环境运行（CI 友好）。
- 所有工具调用必须可审计、可重放。

---

## 附录 A：建议目录

```text
opencode_py/
  cli/
  core/
    graph/
    runtime/
  agents/
    planner.py
    executor.py
    reviewer.py
  retrieval/
    rag/
    symbol_graph/
  tools/
  providers/
  security/
  storage/
  config/
tests/
```

## 附录 B：后续可选项
- 将 DeepAgents 作为高级编排层接入（在 LangGraph 主干稳定后）。
- 增加任务模板库（修 bug、加功能、重构、写测试）。
- 引入离线评测集，做回归评估。
