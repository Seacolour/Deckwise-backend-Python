# RAG、MCP 与 Skill 学习链路

本阶段在现有 FastAPI + LangGraph 文档 Agent 中各实现一条可验证的最小能力。业务文件继续存于 PostgreSQL/R2；工具沿用当前用户与项目权限，不引入第二套业务写入逻辑。

MCP 与 Skill 统一出现在 Web 的“插件”入口，页面内部再按“MCP 插件”和“技能”分组。Flyway V14 保存每位用户的启用状态；Agent 只注册该用户启用的对应工具。

## 1. 项目文件 RAG（已接入）

- 数据源：现有 `backend_data.file_text_fragments`，只读取当前用户仍关联到当前项目的文本分片。
- 索引：`AsyncPostgresStore` 的语义搜索；pgvector 扩展由 Flyway V13 启用，Store 自己管理 `public.store` 与 `public.store_vectors` 表。Store 与可选的 LangGraph checkpointer 属于不同数据。
- Embedding：OpenRouter BYOK 的 `baai/bge-m3`，1024 维，适合项目里的中文资料。原计划的 `openai/text-embedding-3-small` 在本地 OpenRouter 路由返回地区限制 403；BGE-M3 已真实调用成功。更换模型或维度需要重建既有向量索引。
- Agent 工具：`semantic_file_search(query, limit, cache_key)` 返回文件名、分片编号、相似度和短摘录；需要精确引用时再用 `file_content_read` 读取原文。
- 边界：首次检索按需建索引，后续调用复用持久化向量；每次最多处理 120 个分片、返回 5 个结果。项目过大时按文件 `cache_key` 缩小范围。查询前后校验项目归属，文件解除关联后清理旧索引条目。

验收：`uv run python scripts/check_rag_flow.py` 使用临时项目和确定性向量验证跨连接持久化、范围过滤、重复查询不重新嵌入、移除文件后不返回旧片段及跨用户拒绝。真实 OpenRouter BGE-M3 已为已有项目 DOCX 建立 2 个分片索引并命中该文件；GPT-6 Luna 的真实图调用依次执行 `semantic_file_search` 和 `file_content_read`，完成回答。首次建索引会消耗当前用户的 OpenRouter embedding 额度。

## 2. 文档 MCP（已接入，可选）

- 使用 LangChain `MCPAdapter` 接入公开的 `https://docs.langchain.com/mcp`，封装为 `langchain_docs_search`。
- 只选择服务器的 `search_docs_by_lang_chain` 工具；反馈写入工具不暴露给 Agent。最多返回 3 条、每条 1,800 字符，并保留官方文档 URL。
- 对每位用户默认关闭；可在 Web“插件 → MCP 插件”中启用。用于 LangChain/LangGraph 框架问题，不向公共 MCP 发送项目私有文档内容。

验收：与官方 MCP 服务器建立连接、发现工具并返回 Python 文档链接；`scripts/check_plugin_flow.py` 验证用户启用后工具注册、关闭时不注册。`langchain.mcp` 当前为 beta API，后续升级要复查接口。

## 3. 项目内 Skill（已接入）

- `app/agent/skills/` 下存放带 `name`、`description` 前置元数据的 `SKILL.md`。当前示例为 `document-review` 与 `source-grounded-answer`。
- `skill_list` 只返回技能名称和用途；`skill_read` 按允许的确切名称加载步骤，不接受任意文件路径。Agent 可在文档审阅或跨文件问答任务中按需调用。
- 两项内置 Skill 默认开启；用户可在 Web“插件 → 技能”中分别停用或重新启用。停用的 Skill 不会出现在工具返回的目录中，也不能被 `skill_read` 打开。
- 这是一套接入当前 LangGraph 工具循环的轻量 Skill 读取机制，与旧 Java Toolbook 的按需说明加载思路对应；它没有改用 Deep Agents harness。

验收：测试覆盖技能发现、按名称读取和路径遍历拒绝；`scripts/check_plugin_flow.py` 验证跨用户开关隔离和停用后的工具访问。后续可用同一任务比较读取 Skill 前后的工具调用与结果质量。

参考：[LangGraph Store 语义搜索](https://docs.langchain.com/oss/python/langgraph/stores#semantic-search)、[LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp/index)、[Deep Agents Skills 格式](https://docs.langchain.com/oss/python/deepagents/skills)。
