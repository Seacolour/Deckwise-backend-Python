# 用户长期记忆：画像、Agent 写入与 Store 语义召回

## 目标与来源

复用旧 Java 项目的两条写入路径：用户在 Web 个性化页维护自己的画像与记忆，Agent 在对话中调用 `manage_user_memory` 保存稳定、可复用的事实或偏好。后续会话自动读取相关记忆。用户规则继续单独管理，作为明确指令；普通记忆只提供背景事实。

旧项目用 `user_memories` 保存 `title`、`content`、`source=user|ai`，用户可增改删，Agent 工具支持 create/update/delete/list，并将全部记忆拼入后续对话。Python Flyway V2 已有 `user_memories` 和 `user_rules`；当前 Web 个性化页也已调用对应 API。本阶段补齐 Python API，用 LangGraph `AsyncPostgresStore` 对记忆建立独立的语义索引，按问题召回少量相关条目。

## 数据边界

- `backend_data.user_memories` 是可编辑、可删除的权威记录；Store 只是可重建的向量索引。写入成功不依赖 embedding 服务是否可用。
- 记忆 Store 使用与项目文件 RAG 分开的用户命名空间，例如 `("deckwise", "users", user_id, "memories", "bge-m3-v1")`；沿用现有 PostgreSQL、pgvector 和 OpenRouter BGE-M3。
- 每次语义检索前按当前 SQL 记忆列表增量同步 Store，删除已失效条目；用户更新、删除及跨用户隔离均以 SQL 权限检查为准。
- 用户画像专用记忆沿用 Web 的 `Deckwise personalization profile` 标题，作为有限长度的稳定背景。其他记忆优先返回语义相关的少数几条；未配置 OpenRouter embedding Key 时回退为有限条最近记忆。
- `user_rules` 只注入启用规则，不做向量索引。普通记忆不能覆盖当前用户请求、项目权限或工具规则。
- 保留旧项目的来源字段：用户 API 创建为 `user`，Agent 创建为 `ai`。Agent 只保存稳定习惯、工作背景或用户明确要求记住的内容；不把一次性任务输出或密钥自动写入长期记忆。

## 接口与 Agent

- 复用 Web 已有的 `/api/user/memories`、`/api/user/rules` 和 `/api/user/update/my` 契约；用户可以查看、创建、更新和删除记忆，维护画像与规则。
- `AGENT` 模式注册 `manage_user_memory`，支持创建、更新、删除、列表，并复用同一 Service 和用户归属校验。`ASK` 模式仍只读。
- 每轮运行前按当前提问载入相关记忆与启用规则，作为有长度上限的模型背景；跨会话的事实来自 SQL/Store，Checkpointer 继续默认关闭。
- Web 个性化页不需要重做布局，只验证其现有表单与 Python API 联通。

## 验收

1. 用户在 Web 保存画像、创建/删除记忆和规则后刷新可回读；另一个用户无法读取或修改。
2. Agent 创建一条 `source=ai` 的记忆；用户在个性化页能看到、修改或删除。新会话可以按语义召回这条记忆。
3. 修改记忆后检索到新内容，删除后不再召回旧内容；无 OpenRouter Key 时保留有限的普通记忆回退路径。
4. 记忆与项目文件 RAG 命名空间隔离；普通问答仍可使用，默认关闭的 checkpointer 不因本功能开启。

## 当前实现与验证

- Python API 已补齐 Web 个性化页的记忆、规则与昵称接口；用户和 Agent 通过同一记忆 Service 写入，分别记录 `source=user`、`source=ai`。
- Agent 每轮从 SQL 画像和启用规则加载有界背景。其余记忆在用户配置 OpenRouter Key 时经独立 `AsyncPostgresStore` 命名空间做 BGE-M3 语义召回；无 Key 或语义服务暂不可用时使用有限条最近记忆。
- `scripts/check_user_memory_flow.py` 用临时账号验证 CRUD、Web 同源代理、跨用户权限、语义索引更新与删除。`scripts/check_agent_memory_flow.py` 用真实 DeepSeek 在第一会话调用工具写入，第二会话召回，再清理测试记忆与项目。
- 现有 Web 个性化页已在浏览器用临时账号完成手动新增、刷新回读与删除。开发日志保留记忆标题，但隐藏请求体中的记忆/规则正文。

## 后续增强

在基础链路通过后，再评估自动抽取候选记忆、重复事实合并、过期与置信度、用户审核和写入频率限制。用户规则、用户记忆和项目知识保持独立；不将整段对话原样长期保存。

参考：[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)、[LangChain 长期记忆](https://docs.langchain.com/oss/python/langchain/long-term-memory)、[LangGraph 语义记忆](https://docs.langchain.com/oss/python/langgraph/add-memory#long-term-memory-with-semantic-search)。
