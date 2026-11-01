# Deckwise Python

Single-service Python prototype for learning FastAPI, LangChain, LangGraph, and document-editing agents.

See [the phase plan](docs/phase-plan.md) for the next Web-to-Agent implementation steps.

## Code layout

- `app/api/v1/` owns HTTP contracts. `v1` is an internal package name; existing Web paths such as `/api/user/login` stay unchanged.
- `app/services/` owns use cases and external calls such as Resend.
- `app/repositories/` owns PostgreSQL and Redis access. Services control PostgreSQL transaction boundaries through `app/db/session.py`.
- `app/models/` maps the reused `backend_data` tables; `app/schemas/` defines request and response DTOs.
- `app/agent/` is the in-process Agent business package. Its graph, tools, prompts, and memory modules are structural boundaries for the next implementation slice; Agent and streaming APIs are not registered yet.
- Root `db/migration/` and `db/pom.xml` remain the Flyway database migration tooling.

## HTTP foundations

`app/core/request_logging.py` assigns or accepts a safe `X-Request-ID` and logs method, path, status, client address, and elapsed time. `logging.json` adds local ISO 8601 timestamps with a UTC offset to startup and request events. `DECKWISE_ENV=dev` additionally logs JSON request bodies up to 8 KiB, redacting fields such as `code`, `password`, `token`, and `apiKey`. Other body types, query strings, and response bodies are omitted. `DECKWISE_ENV=prod` (the default) omits all bodies. Keep `--no-access-log` on the Uvicorn command so its default access log cannot separately log query strings.

`app/core/responses.py` and `app/core/error_codes.py` keep the existing Web envelope `{code, data, message}`. FastAPI handles request parsing and OpenAPI documentation; `app/core/exceptions.py` converts business, validation, HTTP, and unexpected errors into that envelope. `app/schemas/pagination.py` provides the Java-compatible `current`, `pageSize`, `sortField`, `sortOrder` request and `records`, `total`, `hasNext` response. Each repository must still use an explicit allowlist before putting `sortField` into a SQL `ORDER BY`.

## Setup

Requires Python 3.14 or newer and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run uvicorn app.main:app --reload --no-access-log --log-config logging.json
```

Fill in `DECKWISE_DB_PASSWORD`, `APP_RESEND_API_KEY`, and `APP_RESEND_FROM` in the Git-ignored `.env` file. The database host, port, name, user, Redis URL, logging environment, and cookie setting can be changed there too. Process environment variables take precedence. An existing `.env` with the older `DB_PASSWORD` key also works. The API is available at `http://127.0.0.1:8000/` and its OpenAPI UI at `/docs`. `scripts/run_api.ps1` remains an optional wrapper around the same Uvicorn command.

## PostgreSQL and Flyway

The project uses its own local PostgreSQL database, `deckwise_python_dev`, on port `5432`. The SQL migrations V1–V12 in `db/migration/` are an unchanged snapshot of `AgentWorkbench/backend`. Redis holds login codes and Web sessions, so no login-state tables are needed. A small Maven descriptor in `db/pom.xml` runs Flyway 11.14.1 without building the Java backend.

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

For local Web integration, point `AgentWorkbench/web/.env.local` at `API_PROXY_TARGET=http://127.0.0.1:8000`, start the Python API with the Uvicorn command above, and start the Web app with `npm run dev`. The Web app forwards `/api/user/*` requests and the session cookie through its same-origin proxy. This setup is already present in the local, Git-ignored Web `.env.local` file.

Two checks are available after the database has been initialized:

- `uv run python scripts/check_login_flow.py` exercises the login API with a fake email sender.
- `uv run python scripts/check_web_login_proxy.py` checks login, cookie forwarding, and logout through a running Web proxy and Python API.

Both checks read database settings from `.env`. They create temporary users and remove them when finished. Neither sends an email.

## Workspace and Markdown documents

The first workspace slice implements owned project list/create, project session and file lists, and Markdown document list/create/read/draft update. Draft writes require the current `version` and return a conflict if the document has changed. All reads and writes check the current user's project ownership.

Run `uv run python scripts/check_workspace_flow.py` to exercise these endpoints against local PostgreSQL and Redis without sending email. Set `DECKWISE_CHECK_BASE_URL=http://127.0.0.1:8000` to test a running API server, or `http://localhost:3000` to test through the Web proxy. The script removes its temporary users and data after the check.

The Java backend's `OPENAI_*` settings are not wired into this Python API. Automatic conversation titles and document summaries will need explicit model and credential configuration when those features are implemented.

## Model picker and daily check-in

`GET /api/models/available` now returns an authenticated, Web-compatible response. Its list is empty until a model can actually handle a conversation request; this keeps the Web send button disabled while the Agent API is still being built. Adding a provider key to `.env` alone does not enable chat yet.

`GET /api/user/checkin/status` reads the user's streak from PostgreSQL. `POST /api/user/checkin` uses the user's saved time zone (or a valid time zone from the first request), records one check-in per business day, and returns zero additional points on repeated requests. The recorded reward follows the Java demo's 500-point daily / 1000-point seven-day rule; it is a check-in record, not a spendable balance.

Run `uv run python scripts/check_checkin_models_flow.py` to verify these endpoints with temporary accounts. As with the workspace check, `DECKWISE_CHECK_BASE_URL` can target a running API or the Web proxy.
