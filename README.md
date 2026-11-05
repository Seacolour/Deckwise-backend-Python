# Deckwise Python

Single-service Python prototype for learning FastAPI, LangChain, LangGraph, and document-editing agents.

See [the phase plan](docs/phase-plan.md) for the next Web-to-Agent implementation steps.

This repository contains the API and in-process Agent. The compatible Web client is maintained separately; the FastAPI OpenAPI UI at `/docs` and the included flow scripts can exercise the backend without that client. The PostgreSQL schema is a snapshot from the earlier Java project, while the Python service uses only the tables needed by this demo.

## Code layout

- `app/api/v1/` owns HTTP contracts. `v1` is an internal package name; existing Web paths such as `/api/user/login` stay unchanged.
- `app/services/` owns use cases and external calls such as Resend.
- `app/repositories/` owns PostgreSQL and Redis access. Services control PostgreSQL transaction boundaries through `app/db/session.py`.
- `app/models/` maps the reused `backend_data` tables; `app/schemas/` defines request and response DTOs.
- `app/agent/` runs a LangGraph model/tool loop in process. Project-scoped LangChain tools call the existing document services, and conversation messages are persisted in PostgreSQL.
- Root `db/migration/` and `db/pom.xml` remain the Flyway database migration tooling.

## HTTP foundations

`app/core/request_logging.py` assigns or accepts a safe `X-Request-ID` and logs method, path, status, client address, and elapsed time. `logging.json` adds local ISO 8601 timestamps with a UTC offset to startup and request events. `DECKWISE_ENV=dev` additionally logs JSON request bodies up to 8 KiB, redacting fields such as `code`, `password`, `token`, and `apiKey`. Other body types, query strings, and response bodies are omitted. `DECKWISE_ENV=prod` (the default) omits all bodies. Keep `--no-access-log` on the Uvicorn command so its default access log cannot separately log query strings.

`app/core/responses.py` and `app/core/error_codes.py` keep the existing Web envelope `{code, data, message}`. FastAPI handles request parsing and OpenAPI documentation; `app/core/exceptions.py` converts business, validation, HTTP, and unexpected errors into that envelope. `app/schemas/pagination.py` provides the Java-compatible `current`, `pageSize`, `sortField`, `sortOrder` request and `records`, `total`, `hasNext` response. Each repository must still use an explicit allowlist before putting `sortField` into a SQL `ORDER BY`.

## Try the code

Requires Python 3.14 or newer and [uv](https://docs.astral.sh/uv/). The unit suite runs without PostgreSQL, Redis, R2, Resend, or a personal model Key. Pandoc enables the DOCX conversion test; without it, that one test is skipped.

```powershell
uv sync --locked
uv run pytest -q
```

## Run the API locally

Start PostgreSQL and Redis first. PostgreSQL 18 also needs the [pgvector extension](https://github.com/pgvector/pgvector#installation) installed on the server; Flyway V13 enables it in this database. Database initialization needs Java and Maven on `PATH`; DOCX uploads need Pandoc on `PATH`. Copy the configuration template, then set `DECKWISE_DB_PASSWORD` and `APP_MODEL_CREDENTIAL_ENCRYPTION_KEY`. The PostgreSQL user needs permission to create the development database and enable extensions. The encryption key is a Base64-encoded random 32-byte value; see [the BYOK guide](docs/model-byok-catalog.md).

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run python scripts/setup_db.py
uv run uvicorn app.main:app --reload --no-access-log --log-config logging.json --loop app.db.checkpoint:selector_loop_factory
```

The API is available at `http://127.0.0.1:8000/` and its OpenAPI UI at `/docs`. Email login requires Resend (`APP_RESEND_API_KEY`, `APP_RESEND_FROM`), and private uploads require Cloudflare R2 credentials. The database host, port, name, user, Redis URL, logging environment, and cookie setting can be changed in the Git-ignored `.env` file; process environment variables take precedence. An existing `.env` with the older `DB_PASSWORD` key also works. `scripts/run_api.ps1` remains an optional wrapper around the same Uvicorn command.

## PostgreSQL and Flyway

The project uses its own local PostgreSQL database, `deckwise_python_dev`, on port `5432`. SQL migrations V1–V12 in `db/migration/` are an unchanged snapshot of `AgentWorkbench/backend`; V13 enables pgvector for the Python RAG path. Redis holds login codes and Web sessions, so no login-state tables are needed. A small Maven descriptor in `db/pom.xml` runs Flyway 11.14.1 without building the Java backend.

Start PostgreSQL, then run the setup command from this directory:

```powershell
uv run python scripts/setup_db.py
```

The script reads the database settings from `.env`, creates the database if needed, runs Flyway migrate and validate, and verifies the schema through SQLAlchemy. It passes the password to Flyway only through the child process environment. Re-running the script validates the existing database. `scripts/setup_db.ps1` remains an optional wrapper. Keep V1–V12 unchanged after applying them; add a new migration for schema changes.

## Email login

FastAPI implements the Web app's cookie-based email login contract:

- `POST /api/user/login/email-code` accepts `{ "email": "..." }` and sends a six-digit code through Resend.
- `POST /api/user/login` accepts `email`, `code`, and optional locale fields, then sets the HttpOnly `deckwise_session` cookie.
- `GET /api/user/get/login` checks the session; `POST /api/user/logout` revokes it.

Login codes expire after five minutes and can be attempted at most five times. Resending is limited to once per minute per address. Redis stores salted code hashes and a user ID under each hashed opaque session token, with a 30-day TTL. Keys use a `deckwise-python:` prefix so they do not overlap the Java backend's keys. PostgreSQL keeps users and login records. Existing PostgreSQL-backed login cookies become invalid after this change. Set `APP_WEB_SESSION_COOKIE_SECURE=true` when serving the Web app over HTTPS.

For local Web integration with a compatible client checkout, set its `API_PROXY_TARGET=http://127.0.0.1:8000` and start that client separately. Its same-origin proxy forwards `/api/*` requests and the session cookie to this API.

Two checks are available after the database has been initialized:

- `uv run python scripts/check_login_flow.py` exercises the login API with a fake email sender.
- `uv run python scripts/check_web_login_proxy.py` checks login, cookie forwarding, and logout through a running Web proxy and Python API.

Both checks read database settings from `.env`. They create temporary users and remove them when finished. Neither sends an email.

## Workspace and Markdown documents

The first workspace slice implements owned project list/create, project session and file lists, and Markdown document list/create/read/draft update. Draft writes require the current `version` and return a conflict if the document has changed. All reads and writes check the current user's project ownership.

Run `uv run python scripts/check_workspace_flow.py` to exercise these endpoints against local PostgreSQL and Redis without sending email. Set `DECKWISE_CHECK_BASE_URL=http://127.0.0.1:8000` to test a running API server, or `http://localhost:3000` to test through the Web proxy. The script removes its temporary users and data after the check.

The Java backend's `OPENAI_*` settings are not wired into this Python API. Automatic conversation titles and document summaries will need explicit model and credential configuration when those features are implemented.

## Model picker and daily check-in

`GET /api/models/available` intersects the enabled definitions in [`app/resources/model-catalog.json`](app/resources/model-catalog.json) with the current user's configured BYOK providers. The Web's model settings use `GET/PUT/DELETE /api/user/model-credentials`; API keys are AES-256-GCM encrypted in the existing `backend_data.user_model_credentials` table and only masked status is returned. `POST /api/user/model-credentials/{providerId}/test` probes a newly entered or saved Key with one short model request without saving the candidate; the Web settings page has a test button for each case. Current entries are `deepseek-chat` and `openai/gpt-6-luna` through OpenRouter. DeepSeek remains text-only; image upload and `imageCacheKeys` are accepted only for a catalog model with `imageSupported=true` and the user's matching provider Key. Existing `.env` provider keys are ignored by normal requests. See [the BYOK guide](docs/model-byok-catalog.md).

`GET /api/user/checkin/status` reads the user's streak from PostgreSQL. `POST /api/user/checkin` uses the user's saved time zone (or a valid time zone from the first request), records one check-in per business day, and returns zero additional points on repeated requests. The recorded reward follows the Java demo's 500-point daily / 1000-point seven-day rule; it is a check-in record, not a spendable balance.

Run `uv run python scripts/check_checkin_models_flow.py` to verify these endpoints with temporary accounts. As with the workspace check, `DECKWISE_CHECK_BASE_URL` can target a running API or the Web proxy.

## Document-editing Agent

The Web can create a conversation with `POST /api/projects/{projectId}/create`, read its messages through `GET /api/sessions/{sessionId}/messages/after-seq`, and stream a turn through `POST /api/sessions/{sessionId}/sendRPC` (proxied by the Web as `/sse/sessions/{sessionId}/sendRPC`). `POST /api/sessions/{sessionId}/abort` stops an active local run. Validated file, image, and explicitly referenced document names are stored in the user message's existing JSONB metadata so the Web can show attachment chips during the turn and after refresh; signed R2 URLs are never stored there.

In `AGENT` mode, a LangGraph context → model ↔ tools flow offers project-scoped file reads, `document_create`, `document_read`, `document_locate`, `document_diff`, and `document_save`. Both `ASK` and `AGENT` modes can inspect JSON uploads with `json_structure_read` and `json_subtree_read`; JSON originals are read from private R2 after a project ownership check, with a 1 MB input cap and bounded tool output. `ASK` mode exposes only read tools. Local diffs change a per-turn working copy and require `document_save` to persist; full-draft saves require `document_read`. Both save paths use the current document `version`; a concurrent edit returns `40903` without overwriting it. PostgreSQL session messages remain the Web-facing history. An optional PostgreSQL checkpointer can also retain graph state across turns; see [the checkpoint experiment](docs/checkpointer-experiment.md). The local in-memory abort registry does not coordinate across multiple API workers. The next capabilities are tracked in [the Agent roadmap](docs/agent-capabilities-roadmap.md).

The Agent also includes a small [RAG, MCP, and Skill learning path](docs/rag-mcp-skills-plan.md): project file semantic search via LangGraph `AsyncPostgresStore` and pgvector, optional read-only LangChain docs MCP search, and repository-owned `SKILL.md` packages loaded on demand. Semantic search uses the current user's OpenRouter Key for BGE-M3 embeddings and lazily indexes at most 120 current-project fragments. MCP and Skills share a Web “Plugins” entry with per-user switches (`GET/PUT /api/user/agent-plugins`); the docs MCP defaults off and the built-in Skills default on. `uv run python scripts/check_rag_flow.py` verifies the persistent, project-scoped Store, and `uv run python scripts/check_plugin_flow.py` verifies plugin switches with temporary users.

The [Notion MCP plan](docs/notion-mcp-integration-plan.md) starts with per-user OAuth connection management and read-only Agent tools. Flyway V15 stores encrypted credentials separately from plugin switches. The Web client starts Notion authorization from Plugins and completes it at `/oauth/notion-mcp/callback`; set `NOTION_MCP_REDIRECT_URI` to that Web origin. The existing `APP_MODEL_CREDENTIAL_ENCRYPTION_KEY` is reused through a domain-separated derived key. Only an authorized and enabled user's `notion-search` and `notion-fetch` tools are exposed to the Agent as bounded `notion_search` and `notion_fetch` tools. `uv run python scripts/check_notion_mcp_connection_flow.py` verifies OAuth state, isolation, refresh, and disconnect with simulated Notion responses. Set `DECKWISE_CHECK_BASE_URL=http://localhost:3000` to check the live Web proxy as well. Real Notion authorization, Web Agent search, specified-page fetch, and source links have been exercised locally; a same-turn comparison with project content remains to verify.

To save a user-selected Notion page as a project Markdown file, call `POST /api/notion/pages/import` with `projectId` and `pageIdOrUrl`, or use the Web file panel's Notion import form. This is a snapshot: it uses the existing private R2 upload and text-fragment pipeline, while RAG vectors remain lazily built on search. The page ID and URL are retained as source metadata; the import does not create an editable draft document or mirror Notion attachments. Set `DECKWISE_TEST_NOTION_PAGE_ID` locally and run `uv run python scripts/check_notion_import_flow.py` to exercise a real Notion/R2 import with temporary project cleanup.

With the same test page ID set, `uv run python scripts/check_notion_cross_source_flow.py` checks that a real DeepSeek Agent turn reads both that Notion page and a temporary project document, then removes the project. It uses the connected user's BYOK DeepSeek credential.

The [basic task-planning path](docs/task-planning-basic.md) adds a per-turn `write_todos` tool to `AGENT` mode. LangGraph `Command` updates structured Todo state; the Web shows plan snapshots from persisted tool events. Simple `ASK` turns do not get this tool. `uv run python scripts/check_task_planning_flow.py` verifies a real DeepSeek edit with Todo updates and cleans its temporary project. This is progress tracking within one turn, not automatic replanning or durable cross-turn task recovery.

Run `uv run python scripts/check_agent_flow.py` for a real DeepSeek edit against temporary data. Set `DECKWISE_CHECK_BASE_URL=http://127.0.0.1:8000` to use a running API; to verify the Web SSE proxy, use `DECKWISE_CHECK_BASE_URL=http://localhost:3000` with `DECKWISE_CHECK_WEB_PROXY=1`. The script removes its temporary account and data after the check. File attachment parsing is covered by the separate flow below.

## Private file uploads and parsed text

`POST /api/files/upload/batch` accepts the Web's `files` multipart field with `projectId` and `uploadSource=user_upload`. PDF, DOCX, TXT, Markdown, and JSON files up to 50 MB are accepted. PNG, JPEG, WebP, and GIF images are accepted up to 8 MB and 20 million pixels when the request also supplies `model=<configured OpenRouter GPT model>`. The Web file pickers hide image formats for DeepSeek, and the API rejects image uploads or image messages for unsupported models. DOCX text is converted to Markdown by the system Pandoc executable through `pypandoc`; PDF text layers are extracted with PyPDF. Scanned PDFs still need OCR, and embedded DOCX images are represented only by a marker in parsed text.

Original files are stored in the configured private Cloudflare R2 bucket. The project file row and 2,500-character overlapping text fragments are stored in the existing PostgreSQL tables; images have no text fragments. `GET /api/files/{fileId}/access-url?projectId=...` issues a five-minute private preview URL. The Agent's `file_content_read` tool returns at most five fragments per call, so an uploaded document is not inserted wholesale into model context. For image questions, the model receives a short-lived private R2 URL during the current call; the business conversation history and graph state store only the text request. Legacy `.doc` is not supported.

Set `R2_ACCOUNT_ID`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_PRIVATE_BUCKET`, and optionally `R2_PRIVATE_PATH_PREFIX` in the Git-ignored `.env`. `uv run python scripts/check_file_flow.py` tests synthetic TXT/PDF/DOCX/JSON/PNG uploads, R2 preview, fragment pagination, authorization, the Agent's file-read → document-create → local-diff → save flow, JSON structure/subtree reads, and image-model gating, then removes its objects and temporary users. The image model in this script is simulated; a real OpenRouter image call requires an OpenRouter Key saved through the user's Web settings. Set `DECKWISE_REAL_JSON_MODEL=1` and `DECKWISE_TEST_DEEPSEEK_API_KEY` to exercise the JSON tools with a real DeepSeek model under a temporary BYOK user. To exercise the running Web proxy, set `DECKWISE_CHECK_BASE_URL=http://localhost:3000` and `DECKWISE_CHECK_WEB_PROXY=1`. The batch endpoint processes its files sequentially, so an error after one successful file can leave earlier files uploaded.
