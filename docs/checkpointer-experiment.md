# LangGraph PostgreSQL Checkpointer 实验

本实验复用项目的 `deckwise_python_dev` 数据库。`langgraph-checkpoint-postgres` 在默认 `public` schema 中管理 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes` 和 `checkpoint_migrations`；业务表仍由 Flyway 放在 `backend_data`。首次启用时，FastAPI 启动过程会调用 checkpointer 的 `setup()`。

## 开启与运行

在 Git 忽略的项目 `.env` 中设置 `DECKWISE_CHECKPOINT_ENABLED=true`，或只为当前 PowerShell 进程设置 `$env:DECKWISE_CHECKPOINT_ENABLED='true'`。未设置时默认关闭，保留原来的 PostgreSQL 会话历史回灌方式。

Windows 启动命令使用 Selector 事件循环，以便 psycopg 的异步连接工作：

```powershell
uv run uvicorn app.main:app --reload --no-access-log --log-config logging.json --loop app.db.checkpoint:selector_loop_factory
```

每个通过鉴权的业务会话对应一个服务端生成的 `thread_id`：`deckwise:user:{user_id}:session:{session_id}`。首轮若尚无 checkpoint，会从 `session_messages` 读取近期历史作为启动输入；后续轮次只提交新消息，让 checkpointer 恢复已有图状态。`session_messages` 仍负责前端分页和审计。图快照与业务消息属于两份不同的持久化记录，本实验未实现跨两者的原子提交。

## 验证与清理

```powershell
uv run python scripts/check_checkpoint_flow.py

$env:DECKWISE_CHECKPOINT_ENABLED='true'
$env:DECKWISE_TEST_FAKE_MODEL='1'
uv run python scripts/check_agent_flow.py
Remove-Item Env:DECKWISE_CHECKPOINT_ENABLED,Env:DECKWISE_TEST_FAKE_MODEL
```

第一个脚本用本地模拟模型验证关闭并重建数据库连接后仍能恢复同一线程，还会演示 `keep_latest` 和彻底删除；它会清理自己创建的线程。第二个脚本走真实 FastAPI、LangGraph、文档工具和消息持久化链路，验证第二轮不重复注入历史，也会清理临时用户与 checkpoint。真实 DeepSeek 联调时不设置 `DECKWISE_TEST_FAKE_MODEL` 即可。

已有会话可先查看记录数，再选择只保留最新快照或删除整个线程：

```powershell
uv run python scripts/checkpoint_admin.py --user-id 1 --session-id 2
uv run python scripts/checkpoint_admin.py --user-id 1 --session-id 2 --action keep-latest --apply
uv run python scripts/checkpoint_admin.py --user-id 1 --session-id 2 --action delete --apply
```

脚本默认不会裁剪或删除快照，但首次运行可能通过 `setup()` 初始化 checkpoint 表；上面的 ID 需替换为真实会话归属，并在没有活跃运行时执行清理。常规会话目前不会自动清理 checkpoint。若以后长期启用，应按会话保留期增加定时清理。`keep_latest` 保留跨轮记忆，但舍弃较早的时间旅行记录；`delete` 删除该线程的 checkpoint 和待写入记录。

Checkpointer 保存图状态，不会自动压缩模型上下文。这里保留了业务表的消息历史，下一阶段仍需设计 token 预算与摘要。当前文档保存工具的读取前置校验保存在单次请求的工具实例内；若将来从中断点恢复到写入步骤，应把这项校验纳入可恢复状态，或重新读取文档后再写入。
