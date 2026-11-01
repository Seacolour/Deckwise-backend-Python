# Deckwise Python 阶段推进计划

## 目标与边界

用 FastAPI 承担简化后的 Backend 与进程内 Agent 职责，复用当前 Web 的 API 契约和 PostgreSQL 表结构。先完成一条可从前端操作、可持久化、可验证的文档编辑链路，再让 Agent 使用同一套业务服务读写文档。

以 `登录 → 项目 → 文档 → Agent 编辑文档` 为主线推进。每阶段都以真实前端联调和数据回读为验收依据；暂不追求覆盖原 Java Backend 的全部功能。

## 当前基线

- 邮箱验证码登录、HttpOnly Cookie 鉴权和退出登录已与 Web 联通。
- 用户及登录记录保存在 PostgreSQL；验证码和登录会话保存在 Redis。
- FastAPI 的 API、Service、Repository、Schema、Model 和 Agent 包结构已建立。
- 阶段 1 的项目、会话列表、文件列表和 Markdown 草稿接口已实现；Agent 模块仍是结构外壳。模型列表和每日签到接口已补齐，模型列表在对话能力接入前如实返回空数组。

## 阶段 1：工作区与文档闭环（已完成）

### 1.1 项目入口

- 对照 Web 的请求与响应实现 `POST /api/projects/list`、`POST /api/projects/create`。
- 实现项目归属校验；列表只返回当前用户可访问的项目，排序字段使用显式白名单。
- 补齐工作台进入项目后所需的 `POST /api/projects/{projectId}/list` 会话列表读取，使无会话的新项目也能正常显示空列表。
- 工作台选中项目后还会自动读取 `GET /api/projects/{projectId}/files`；本阶段提供真实的只读列表（无文件时返回空数组），上传与预览留待后续。

### 1.2 文档编辑

- 实现 `GET /api/documents/list`、`POST /api/documents/create`、`GET /api/documents/{documentId}`、`PUT /api/documents/{documentId}/draft`。
- 按现有分层组织：API 处理 HTTP 契约，Service 处理项目权限与编辑规则，Repository 负责 SQL，Schema 负责请求和响应。
- 草稿更新使用 `version` 乐观锁；版本过期返回明确的冲突错误，不能覆盖较新的内容。
- 文档读取与写入都验证所属项目及当前用户权限。返回值保持 Web 使用的 `{code, data, message}` 外层格式和文档 DTO 字段。

### 阶段 1 验收

1. 在 Web 登录后创建项目、创建 Markdown 文档、修改草稿并刷新页面，内容和版本仍正确；新项目的会话与文件列表能正常显示为空。
2. 两个账号无法读取或修改对方的项目和文档；旧版本写入得到冲突响应。
3. API 测试覆盖项目归属、草稿版本冲突及成功写入，并通过真实 PostgreSQL 的联调检查。

已验证：`scripts/check_workspace_flow.py` 通过 FastAPI、运行中的 API 服务和 Web 代理，覆盖项目、会话/文件列表、文档写入、版本冲突与跨账号权限；Playwright 页面操作完成创建、保存和刷新回读。测试账号及数据已清理。

## 阶段 1.5：登录后附属接口（已完成）

- `GET /api/models/available` 已从 404 改为认证后的成功响应；现阶段无可调用的对话模型，因此返回空列表，不会让 Web 误启用发送按钮。
- `GET /api/user/checkin/status` 与 `POST /api/user/checkin` 使用 PostgreSQL 签到状态和日志表，按用户时区计算日期，并保证同日重复签到不重复记奖励。
- `scripts/check_checkin_models_flow.py` 通过 FastAPI、实际 HTTP 服务和 Web 代理；浏览器登录后确认三个请求均为 200，页面控制台无错误。

## 阶段 2：最小 Agent 文档编辑链路（下一阶段）

- 在对话执行能力接入后填充 `GET /api/models/available`，只展示当前实际配置且可调用的模型。
- 完成会话创建、消息读取和流式回复所需的最小 API；先核对现有 Web 的 SSE 事件格式。
- 将文档读取、保存封装为 LangChain tools，调用阶段 1 的业务服务和权限检查，避免另写一套文档写入逻辑。
- 用一个明确的 LangGraph 流程串起上下文读取、模型/工具调用、写入结果和会话消息保存；需要写入恢复或冲突分支时再扩展节点。

### 阶段 2 验收

从 Web 选择模型，向 Agent 发出一个文档修改请求；界面能看到流式结果，文档实际更新，刷新后对话及文档状态仍可回读。Agent 遇到无权限或版本冲突时不能静默覆盖数据。

## 后续按需求补齐

- 项目重命名与删除、文档删除及版本历史。
- 文件上传、预览与对象存储；随后再决定是否需要 RAG。
- 更多模型凭据管理和其他原 Backend 功能。
- 如需对比框架体验，再以同一文档任务试用 Deep Agents，比较实现复杂度和行为。

每进入下一阶段前，先确认前一阶段的前端操作、持久化回读和权限边界均已通过。
