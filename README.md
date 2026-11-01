# Deckwise Python

Single-service Python prototype for learning FastAPI, LangChain, LangGraph, and document-editing agents.

## Code layout

- `app/api/v1/` owns HTTP contracts. `v1` is an internal package name; existing Web paths such as `/api/user/login` stay unchanged.
- `app/services/` owns use cases and external calls such as Resend.
- `app/repositories/` owns SQL queries. Services control transaction boundaries through `app/db/session.py`.
- `app/models/` maps the reused `backend_data` tables; `app/schemas/` defines request and response DTOs.
- `app/agent/` is the in-process Agent business package. Its graph, tools, prompts, and memory modules are structural boundaries for the next implementation slice; no Agent or document API is registered yet.
- Root `db/migration/` and `db/pom.xml` remain the Flyway database migration tooling.

## HTTP foundations

`app/core/request_logging.py` assigns or accepts a safe `X-Request-ID` and logs method, path, status, client address, and elapsed time. `DECKWISE_ENV=dev` additionally logs JSON request bodies up to 8 KiB, redacting fields such as `code`, `password`, `token`, and `apiKey`. Other body types, query strings, and response bodies are omitted. `DECKWISE_ENV=prod` (the default) omits all bodies. The local runner selects `dev` unless an environment is already set, and disables Uvicorn's default access log so it cannot separately log query strings.

`app/core/responses.py` and `app/core/error_codes.py` keep the existing Web envelope `{code, data, message}`. FastAPI handles request parsing and OpenAPI documentation; `app/core/exceptions.py` converts business, validation, HTTP, and unexpected errors into that envelope. `app/schemas/pagination.py` provides the Java-compatible `current`, `pageSize`, `sortField`, `sortOrder` request and `records`, `total`, `hasNext` response. Each repository must still use an explicit allowlist before putting `sortField` into a SQL `ORDER BY`.

## Setup

Requires Python 3.14 or newer and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked
.\scripts\run_api.ps1
```

The runner prompts for the local PostgreSQL password. Resend reads `APP_RESEND_API_KEY` and `APP_RESEND_FROM` from process environment variables or this project's Git-ignored `.env` file; process variables take precedence. Only those two `.env` keys are read by the login feature. The API is available at `http://127.0.0.1:8000/` and its OpenAPI UI at `/docs`.

## PostgreSQL and Flyway

The project uses its own local PostgreSQL database, `deckwise_python_dev`, on port `5432`. The SQL migrations V1–V12 in `db/migration/` are an unchanged snapshot of `AgentWorkbench/backend`; V13 adds Python email login state. A small Maven descriptor in `db/pom.xml` runs Flyway 11.14.1 without building the Java backend.

Start PostgreSQL, then run the setup script from this directory:

```powershell
.\scripts\setup_db.ps1
```

The script prompts for the local `postgres` password, creates the database if needed, runs Flyway migrate and validate, and verifies the schema through the Python SQLAlchemy connection. It keeps the password in the process only. Re-running the script validates the existing database. Keep V1–V12 unchanged after applying them; add a new migration for schema changes.

## Email login

FastAPI implements the Web app's cookie-based email login contract:

- `POST /api/user/login/email-code` accepts `{ "email": "..." }` and sends a six-digit code through Resend.
- `POST /api/user/login` accepts `email`, `code`, and optional locale fields, then sets the HttpOnly `deckwise_session` cookie.
- `GET /api/user/get/login` checks the session; `POST /api/user/logout` revokes it.

Login codes expire after five minutes and can be attempted at most five times. Resending is limited to once per minute per address. The Python backend stores code hashes and opaque session token hashes in PostgreSQL; it does not require Redis. Set `APP_WEB_SESSION_COOKIE_SECURE=true` when serving the Web app over HTTPS.

For local Web integration, point `AgentWorkbench/web/.env.local` at `API_PROXY_TARGET=http://127.0.0.1:8000`, start the Python API with `scripts/run_api.ps1`, and start the Web app with `npm run dev`. The Web app forwards `/api/user/*` requests and the session cookie through its same-origin proxy. This setup is already present in the local, Git-ignored Web `.env.local` file.

Two checks are available after the database has been initialized:

- `uv run python scripts/check_login_flow.py` exercises the login API with a fake email sender.
- `uv run python scripts/check_web_login_proxy.py` checks login, cookie forwarding, and logout through a running Web proxy and Python API.

Both checks need the local database password in the process-only `PGPASSWORD` environment variable. They create temporary users and remove them when finished. Neither sends an email.

The Java backend's `OPENAI_*` settings are not wired into this Python API. Automatic conversation titles and document summaries will need explicit model and credential configuration when those features are implemented.
