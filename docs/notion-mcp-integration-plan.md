# Notion MCP：用户授权与 Agent 文档来源

## 目标

在现有 FastAPI + LangGraph 文档 Agent 中预设官方 Notion MCP。用户在 Web「插件 → MCP 插件」完成自己的 Notion 授权后，Agent 才能按需搜索和读取该用户可访问的 Notion 内容，并与项目内的 RAG、文档工具协同回答。首个闭环只开放读取能力。

旧 Java 项目采用「用户 OAuth → Notion REST 读取 Markdown → 导入项目文件」的快照流程。本阶段新增 Agent 直接访问外部文档的路径；确定性的项目文件写入仍由 FastAPI 业务服务承担。

## 当前基线与设计约束

- 官方托管服务使用 Streamable HTTP：`https://mcp.notion.com/mcp`。不部署另一套 Notion MCP Server，也不复用旧 REST 集成的 OAuth Client ID/Secret。
- 当前 `app/services/agent_plugin_service.py` 和 Flyway V14 只保存每位用户的 `enabled` 开关，没有第三方授权凭据或连接状态。**启用开关不等于已授权**。
- 当前 `app/services/agent_service.py` 在每轮开始前同步生成工具列表；Notion 的认证连接与工具发现是异步步骤，需要调整构图时机。`app/agent/graph.py` 的 `StateGraph` 和 `ToolNode` 可以继续复用。
- `langchain.mcp.MCPAdapter` 将已认证的 MCP 工具转换为 LangChain tools；FastMCP Client 承担传输。FastMCP 默认 OAuth helper 使用本机临时回调服务器，不能直接作为多用户 Web 的授权回调。授权入口、用户绑定与回调状态由 FastAPI 管理。
- 项目内 RAG 当前按需建立索引；读取 Notion 页面不会自动复制到项目或立即生成向量。可选的导入流程另列阶段。
- Agent 读取的 Notion 片段会进入本轮模型上下文，并与其他工具结果一样保存在会话事件中；仅在用户明确导入时才成为项目文件或进入项目 RAG 索引。
- LangGraph checkpointer 默认关闭。本阶段不引入 Agent 写入 Notion 或 Human-in-the-Loop 恢复流程。

**实施进度（2026-11-04）：** 阶段 1 的数据库迁移、用户授权入口/回调、凭据加密、插件状态和 Web 连接界面已实现；用户已在本地完成真实 Notion 授权，后端用该用户的凭据经 `MCPAdapter` 发现 74 个工具。阶段 2 已将经真实发现确认的 `notion-search`、`notion-fetch` 限定为 Agent 可用的两个只读工具。真实 Web 对话已先后执行 `notion_search` 和 `notion_fetch`，读取指定页面并返回来源链接。

**2026-11-05 进度：** 阶段 2 又用真实 DeepSeek 模型、已授权的 Notion 页面和临时项目文档完成同轮比较，工具事件依次包含 `notion_fetch`、`document_read`，没有写入工具，测试项目已清理。阶段 3 已增加明确的页面链接/ID 导入入口。后端先验证项目归属，再调用当前用户的 `notion-fetch`，提取页面正文并经现有 Markdown 上传、私有 R2 与文本分片链路保存。真实 Notion 测试页已导入临时项目，验证来源、分片、重复导入复用及跨用户拒绝。浏览器中完成“导入页面”后，刷新文件列表仍能看到带 Notion 来源标记的 Markdown 文件，预览回读了页面正文；临时项目已清理。

## 授权与可见性规则

```text
Notion 工具可见
  = 当前用户 Notion 连接有效
  ∧ 该用户已启用 notion MCP 插件
  ∧ 工具在服务端维护的只读白名单中
```

插件目录预设 `notion`，默认关闭。连接状态与开关分别保存：

| 状态 | Web 操作 | Agent 工具 |
| --- | --- | --- |
| 未连接 | 连接 Notion；启用不可用 | 不注册 |
| 授权中 | 显示授权进度，可重试 | 不注册 |
| 已连接、已关闭 | 可启用或断开连接 | 不注册 |
| 已连接、已启用 | 可关闭或断开连接 | 只注册允许的读取工具 |
| 需重新连接 | 重新授权；启用不可用 | 不注册 |

授权成功后将插件设为启用；用户关闭插件时保留授权，断开连接时删除凭据并关闭插件。所有状态转换都在后端校验；直接调用 `PUT /api/user/agent-plugins/notion` 不能绕过授权检查。插件列表增加独立的 `connectionStatus` 等字段，不把 token 返回给 Web。

## 分层设计

1. **API / Service：** FastAPI 根据登录态识别用户，提供连接入口、OAuth 回调、连接状态和断开接口。授权请求的 `state`、PKCE verifier 和用户/浏览器会话关联保存在带 TTL 的 Redis 记录中，回调时一次性消费。
2. **凭据存储：** 新迁移建立按 `user_id + provider` 隔离的连接记录；加密保存 access token、refresh token、到期时间及动态客户端注册信息。加密密钥通过项目 `.env` 配置，并在 `.env.example` 只写变量名。刷新 token 轮换时按连接串行刷新并原子保存新凭据；`invalid_grant` 转为「需重新连接」。
3. **MCP 接入：** 从当前用户的有效凭据构造 FastMCP Client，交给 `MCPAdapter` 发现工具。只按经实测确认的名称白名单注册读取工具；服务端提供的 `read_only_hint` 仅作辅助信息，不作为放行依据。工具名称加 Notion 前缀并限制结果体积，避免与本地工具冲突或一次将整页塞入上下文。
4. **LangGraph：** 每轮对话在构图前取当前用户的插件状态并完成异步工具发现；模型绑定和 `ToolNode` 使用同一份工具列表。MCP Client/Adapter 生命周期覆盖该轮 SSE 图执行。连接失效时移除工具并向用户给出可重新授权的提示，不切换到其他用户的凭据。

> OAuth 库的具体选择在阶段 1 做最小验证。优先使用成熟库处理 OAuth 发现、PKCE、注册和交换；不假设 `Client(auth="oauth")` 的本机浏览器回调能自动接入我们的 Web。LangChain 的 MCP 适配器负责工具桥接，不负责应用的用户权限与授权页面。

## 分阶段推进

### 阶段 1：用户连接闭环

- 在插件页显示 Notion 的连接状态、连接/重新连接/断开操作；未授权时不能启用。
- 实现 FastAPI 授权入口与回调，安全保存按用户隔离的凭据；回调成功后验证可建立认证的 Notion MCP 连接。
- 覆盖 `state`/PKCE 校验、过期与重复回调、跨用户访问、断开后的凭据删除，以及刷新 token 轮换。

**验收：** 一个真实 Notion 账号完成授权和刷新回读；两个应用测试用户的隔离测试证明连接与凭据不会串用。关闭和断开表现不同；未授权用户通过 API 强制开启也无法获得工具。此阶段尚不把 Notion 工具交给 Agent。

### 阶段 2：只读 MCP 工具进入 Agent

- 对真实 Notion MCP 做一次工具发现，确认搜索、页面读取工具的实际名称与返回结构，再固定服务端白名单。
- 将当前用户的认证 Client 经 `MCPAdapter` 适配为工具，与 `semantic_file_search`、`file_content_read` 一起交给现有 LangGraph。
- 验证插件开关、授权失效、工具结果裁剪与跨用户隔离；在 Web 工具事件中保留来源，便于观察 Agent 的调用顺序。

**验收：** 用户授权并启用后，可用自然语言让 Agent 搜索/读取一篇测试 Notion 页面，再与当前项目文件比较；未授权、关闭或断开的用户均看不到 Notion 工具。Agent 无法调用 Notion 的创建、编辑或删除工具。

当前白名单固定为 `notion-search` 和 `notion-fetch`，对模型暴露为 `notion_search` 和 `notion_fetch`。工具返回文本分别限制为 6,000 和 12,000 字符。模拟模型的 LangGraph 测试验证 Notion 搜索/读取与本地语义搜索可在同一轮图中调度；真实 Web 对话验证搜索、按指定页面读取和来源链接。`scripts/check_notion_cross_source_flow.py` 用真实模型完成 Notion 与临时项目文档的同轮读取，并清理测试项目。

### 阶段 3：可选的项目导入

- 用户明确选择页面并点击导入时，FastAPI 可直接调用已授权的读取工具，再复用现有文件/文档 Service 保存 Markdown；不强制让 LLM 执行确定性导入。
- 导入后的文档按当前项目文件权限管理。若需要语义检索，沿用现有按需索引流程；是否改为导入时建索引另做性能与费用评估。

当前实现保存为项目 Markdown **文件**，可预览并交给 Agent 读取；未自动创建可编辑的草稿文档。来源页 ID/URL 存于文件元数据；同一页面且正文未变化时复用已存文件，页面更新后产生新快照。图片和附件仍引用 Notion 原链接，可能过期。

**验收：** 导入后页面作为项目文件可回读，跨项目/跨用户不能访问；Notion 页面后续修改不会被误称为已自动同步。

### 后续候选：Notion 写入与人工审批

只有确有写回场景时，才扩充工具权限，并设计 LangGraph `interrupt()`、持久化 checkpoint、恢复 API 与 Web 审批界面。MCP 工具注解可以辅助识别写操作，实际准入仍由应用的工具白名单和授权策略决定。

## 实施前准备

- 一个可联调的 Notion 工作区成员账号及一两篇测试页面。授权时选择测试工作区；不在聊天或仓库中传递 token。
- 本地 Web 和 FastAPI 的访问地址，用于确定本项目的 OAuth 回调地址。旧 Java 的 REST 回调 URI 不直接沿用。
- 如工作区有 MCP 客户端审批策略，确认允许当前应用连接。首阶段使用交互式用户 OAuth；无需先准备旧 Notion REST 集成的 Client ID/Secret。

## 参考资料

- [LangChain Python：MCP 鉴权](https://docs.langchain.com/oss/python/langchain/mcp/auth)
- [LangChain Python：MCP 工具](https://docs.langchain.com/oss/python/langchain/mcp/tools)
- [FastMCP Client OAuth](https://gofastmcp.com/clients/auth/oauth)
- [Notion：构建 MCP Client](https://developers.notion.com/guides/mcp/build-mcp-client)
