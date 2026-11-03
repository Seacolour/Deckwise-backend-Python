# Agent 能力复刻路线

## 目标

沿用 FastAPI 项目内的业务服务和现有 Web 契约，选择旧 Agent 中能形成完整任务链路的能力来学习 LangChain 工具与 LangGraph 流程。上下文窗口、重复读取和 token 用量随实际任务观察，不单独安排上下文缩减实验。LangGraph checkpointer 继续默认关闭。

## 1. 从资料创建文档并局部编辑（后端已完成）

现状：Agent 能读取项目文件和 Markdown 草稿，也能提交整份新草稿；尚不能创建文档、定位原文或应用局部修改。旧 Agent 的 `document_diff` 先修改工作副本，再由 `document_save` 持久化。

实现顺序：

1. 增加项目范围内的 `document_create`，复用 `document_service.create_document`。
2. 增加 `document_locate`，返回当前版本、匹配原文和有限上下文；匹配不唯一时明确列出候选，不猜测目标。
3. 增加 `document_diff`，用精确原文匹配在本轮工作副本应用局部修改；未保存的修改不写数据库。
4. 扩展 `document_save`，支持保存工作副本，同时保留现有“读取整篇 → 提交整篇”的调用方式；最终仍使用项目权限和版本乐观锁。

验收：从已上传的 PDF/DOCX/TXT 分片读取资料，创建 Markdown 文档，定位并只修改其中一节；Web 可看到工具事件，刷新后内容和版本正确。歧义匹配、跨项目 ID、未先读取、外部并发更新均不能写入。核对 `file_list` → `file_content_read` → `document_create` 以及 `document_locate` → `document_diff` → `document_save` 所需工具轮次。

验证记录（2026-11-04）：`uv run pytest -q` 为 21 passed；`scripts/check_agent_flow.py` 在真实 DeepSeek 下选择 `document_read → document_locate → document_diff → document_save` 并完成版本递增；`scripts/check_file_flow.py` 通过真实 R2 上传和解析，使用脚本模型在同一 LangGraph 轮次走完 `file_content_read → document_create → document_locate → document_diff → document_save`，刷新 API 回读到修改后的草稿。局部修改在 `document_save` 前未写入数据库；单元测试覆盖歧义匹配、修改块原子性、项目作用域和版本冲突。Web 页面中的工具展示尚待目测。

## 2. JSON 结构与局部读取（后端已完成）

现状：JSON 文件可以上传并作为文本分片读取。旧 Agent 提供 `json_structure_read` 和 `json_subtree_read`。

实现：对项目内 JSON 建立有大小、深度和返回量限制的结构视图；以 JSON Pointer 精确读取局部节点，复用文件权限检查。读取数据时避免把整份 JSON 展开到模型上下文。先提供只读能力。

验收：嵌套 JSON 能先列出结构，再读取目标子树；无效指针、越权文件、超限结果返回明确错误；Web 能展示工具过程。

验证记录（2026-11-04）：`uv run pytest -q` 为 24 passed，覆盖 JSON Pointer 的 `~0`/`~1` 转义、无效路径、结构截断、子树大小和节点限制。`scripts/check_file_flow.py` 通过真实 R2 上传 JSON；项目内工具先读取结构再读取 `/settings/features/1`，跨账号访问、无效路径和超限子树均被拒绝。设置 `DECKWISE_REAL_JSON_MODEL=1` 后，真实 DeepSeek 经 SSE 调用 `json_structure_read` 与 `json_subtree_read` 并完成回答。Web 已有这两个工具的时间线解析，页面展示尚待目测。每次读取均重新检查项目归属，读取原件上限为 1 MB。

## 3. 图片理解（后端与真实模型已验证，Web 页面待验收）

Web 已传 `imageCacheKeys`，Python API 现在支持 PNG/JPEG/WebP/GIF 私有上传与项目权限检查。DeepSeek 保持纯文本；只有当前用户通过 BYOK 设置了 OpenRouter Key，catalog 中的 GPT 视觉模型才出现在其模型列表，并接受图片上传和图片消息。Web 的两个文件选择器会在 DeepSeek 下隐藏图片格式，后端上传与发送接口也会拒绝不支持视觉的模型。

图片原件存入私有 R2；后端限制 8 MB、2000 万像素和真实图片格式，发送时再次检查文件属于当前项目。模型调用时临时注入短时授权 URL，业务历史和图状态只保留文本。当前 catalog 的 `openai/gpt-6-luna` 在 OpenRouter 公开目录标有图片输入与工具支持；后续模型变更由 [Python model catalog](../app/resources/model-catalog.json) 管理。

验收：从 Web 附加图片并提问，模型可基于图片回答；无权限、过大或不支持的格式有明确反馈，消息回读仍正常。

验证记录（2026-11-04）：`scripts/check_file_flow.py` 实际上传 PNG 至私有 R2，验证 DeepSeek 上传和发送均拒绝、跨账号和非图片读取拒绝；脚本模型收到多模态图片消息且可获取图片，业务会话回读未含临时 R2 URL。Web 类型检查与定向测试通过。

补充验证（2026-11-04）：catalog 切换到 `openai/gpt-6-luna` 后，已保存的个人 OpenRouter Key 测试成功；模型生成了指定工具调用，并对合成红色 PNG 回答 `red`。这验证了模型接口的工具调用与视觉输入，尚不能据此断言复杂多工具任务质量。

## 后续判断

在上述链路里记录实际遇到的上下文溢出、重复读取或遗忘，再决定是否引入消息裁剪、摘要或跨轮工作记忆。旧版 `todo_list`、运行账本和工具结果缓存不直接搬运：先确认 Python 会话持久化与工具事件回读能支撑其预期语义。人工审批与中断恢复另行评估，因为它们需要持久化的恢复点。
