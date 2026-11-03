# 模型目录与 BYOK

## 两类数据

- [`app/resources/model-catalog.json`](../app/resources/model-catalog.json) 是应用级定义：模型 ID、提供商、上游模型 ID、展示名称、问答/Agent/图片能力以及是否启用。修改后重启 API 生效。
- Flyway V11/V12 已创建的 `backend_data.user_model_credentials` 是用户级数据：每位用户对每个提供商保存一条加密 API Key。模型目录不包含密钥。

`GET /api/models/available` 取两者交集：只返回 catalog 中已启用且当前用户已配置相应提供商 Key 的模型。发送消息时再次核对模型和模式，再解密当前用户的 Key 创建 LangChain 模型；图片上传和图片消息还检查 catalog 的 `imageSupported`。不存在服务端共享 Key 回退。

## 与旧 Java 后端的对应关系

Python 复用相同的 V11/V12 表、`GET/PUT/DELETE /api/user/model-credentials` 契约，以及 AES-256-GCM 的 12 字节 nonce、版本 1 和 `model-credential:v1:{userId}:{providerId}` AAD。Key 只在服务端解密；状态接口只返回 `configured` 与末尾四位掩码。Python catalog 独立于 Java catalog，因为当前 Python 使用 LangChain 的 ChatDeepSeek / ChatOpenAI Chat Completions 调用路径，不能直接把 Java Responses API 模型清单当作已支持模型。

## 本地配置与使用

1. 在忽略提交的 `.env` 中配置 `APP_MODEL_CREDENTIAL_ENCRYPTION_KEY`，值为随机 32 字节的 Base64 编码。可用 `uv run python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"` 生成；请将结果写入本地 `.env`，不要提交。
2. 登录现有 Web，在“管理密钥”页分别设置 DeepSeek 或 OpenRouter 的个人 Key。填写后可先点“测试 Key”，不会保存候选 Key；已保存的 Key 可点“测试连接”重测。测试会调用 catalog 中该提供商的第一个问答模型，消耗少量 token；返回可用、鉴权失败或服务暂不可用，不显示上游错误原文。页面只显示掩码；删除后该提供商的模型立即从当前用户列表中消失。
3. 当前 catalog 只列实际接入的 `deepseek-chat` 与 `openai/gpt-6-luna`。DeepSeek 保持纯文本；OpenRouter GPT 支持图片。更改模型时同时核对上游接口格式与能力，不要只添加一个展示名称。

旧 `.env` 中的 `DEEPSEEK_API_KEY`、`OPENROUTER_API_KEY` 和模型 ID 配置不再用于运行中的用户请求。`DECKWISE_TEST_DEEPSEEK_API_KEY` 可选地供联调脚本为临时测试用户通过 BYOK 接口写入 Key；脚本结束后删除测试用户和凭据。

当前信封版本为 1，尚未实现加密主密钥轮换。已保存用户 Key 后请保管好 `APP_MODEL_CREDENTIAL_ENCRYPTION_KEY`；直接更换它会使旧密文无法解密，需要用户重新保存个人 Key。

## 验证

`uv run python scripts/check_model_byok_flow.py` 创建两个临时用户，检查候选/已保存 Key 的测试接口、加密存储、用户隔离、模型列表过滤、无效提供商和删除行为。设置 `DECKWISE_REAL_KEY_PROBE=1` 与 `DECKWISE_TEST_DEEPSEEK_API_KEY` 后，还会对 DeepSeek 发送一次真实短请求。`uv run python scripts/check_agent_flow.py` 在提供测试 Key 时通过 BYOK 接口为临时用户配置 DeepSeek，然后运行真实模型文档编辑。脚本均清理测试用户。

2026-11-04 联调：使用已保存的个人 OpenRouter Key 测试 `openai/gpt-6-luna` 返回 `valid`；同一模型按要求生成 `echo_probe` 工具调用，并正确识别一张合成红色 PNG。测试输入没有使用私人文档或图片。Web 页面中的测试按钮和完整多工具任务仍以实际交互验收。
