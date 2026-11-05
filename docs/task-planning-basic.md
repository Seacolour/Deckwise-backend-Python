# Agent 基础任务规划：Todo 列表

## 目标与现状

在现有 FastAPI + LangGraph 文档 Agent 中，为多步骤 `AGENT` 请求增加一份可更新、可回看的待办列表。当前图是 `context → model ↔ tools → response`；`AgentState` 只有消息、文档引用和工具轮数，没有显式计划。项目仍使用自定义 `StateGraph`，不切换到 Deep Agents harness。

LangChain 的 `TodoListMiddleware` 为 `create_agent` / Deep Agents 提供 `write_todos`；本项目保留原图，借鉴其“结构化待办 + 执行中更新”的交互。基础版不增加独立的规划模型调用。

## 基础版范围

- 仅向 `AGENT` 模式提供 `write_todos`；简单请求可以直接执行，复杂请求先列 2–6 个短步骤。
- 每项包含 `content` 与 `status`：`pending`、`in_progress`、`completed`。一次最多一个执行中步骤。
- 待办作为 `AgentState.todos` 的整表更新；工具调用通过 LangGraph `Command` 返回状态更新及匹配的 `ToolMessage`。工具节点必须保留该更新，不能只取 `messages`。
- 模型每次调用都能看到当前待办。创建和状态变化经现有 SSE 工具事件送到 Web，保存到 `session_messages`，刷新后仍可展示待办快照。
- 模型应在实际工具结果确认后标记步骤完成。基础版记录的是 Agent 报告的进度，尚不由后端逐项验证业务结果。
- 计划只覆盖当前这一轮运行。默认关闭的 checkpointer 不因本功能开启；下一轮不自动续用前一轮的待办。

## 当前实施结果

- `AgentState.todos` 保存本轮待办；`write_todos` 通过 `Command` 更新状态并返回配对的 `ToolMessage`。工具节点合并计划更新和普通工具结果。
- Web 将 `write_todos` 工具事件显示为待办卡片；工具事件原样存入会话历史，刷新后可重建卡片。
- `scripts/check_task_planning_flow.py` 用临时项目和真实 DeepSeek 模型完成读取、定位、修改、保存任务：首个工具是 `write_todos`，共更新四次待办，最终四项完成、文档版本变为 2。脚本清理测试项目。

## 验收

1. 简单 `ASK` 请求没有 `write_todos`；多步骤 `AGENT` 请求可创建、推进并完成待办，图状态中的 `todos` 与工具事件一致。
2. 非法待办（过多、空内容、多个执行中、更新时改写原有步骤）被拒绝且不污染图状态。
3. Web 在流式回复和刷新后的历史中都能显示状态与步骤内容；工具结果仍与调用配对。
4. 现有文档编辑、版本冲突、Notion 和 RAG 工具链不因计划工具失效；工具轮数与递归限制足够覆盖基础计划更新。

## 后续增强

基础版验证后再考虑：对复杂任务自动触发独立规划节点；用业务结果校验步骤完成；工具失败时标记阻塞并有限次重规划；跨轮计划持久化、恢复和人工调整。那时再决定使用业务计划表还是启用 LangGraph checkpointer，避免把本轮 Todo 快照误称为完整的任务恢复系统。

参考：[LangChain TodoListMiddleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#to-do-list-3)、[LangGraph 工具更新状态](https://docs.langchain.com/oss/python/langchain/tools#return-a-command)、[Deep Agents 任务规划](https://docs.langchain.com/oss/python/deepagents/overview#task-planning)。
