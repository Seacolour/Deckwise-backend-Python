# Database migration source

`migration/V1__foundation.sql` through `V12__openrouter_model_credentials.sql` are snapshots of the earlier Java Backend migrations. They create the `backend_data` schema in a separate local database. `V13__enable_pgvector.sql` is the first Python-specific migration and enables the server-installed pgvector extension in `public`. The Python service uses only the tables required by its Web-compatible API and Agent paths.

Login codes and Web sessions live in Redis. User accounts and login records remain in PostgreSQL. Install pgvector for the server's PostgreSQL major version before running `scripts/setup_db.py`; the database user must be allowed to create extensions. The local development database's Flyway history advances through V15 after setup.

The optional LangGraph PostgreSQL checkpointer uses tables in the database's `public` schema. `AsyncPostgresSaver.setup()` manages those tables independently of Flyway when the experiment is enabled.

The project-file RAG tool uses LangGraph `AsyncPostgresStore`. Its first semantic search calls `setup()` to manage `public.store`, `public.store_vectors`, and migration metadata. Flyway V13 enables the pgvector extension itself; Store tables remain owned by the LangGraph package. The embedding column uses 1024 dimensions for OpenRouter BGE-M3.

Flyway V14 creates `user_agent_plugin_settings`, which stores per-user switches for the approved MCP and Skill catalog. It does not store arbitrary MCP URLs or uploaded skill files.

Flyway V15 creates `user_mcp_connections` for encrypted, per-user Notion MCP OAuth credentials and connection status. It is separate from the V14 plugin switch. The existing project encryption key is domain-separated for MCP credentials; Notion callback state and PKCE verifiers have a short Redis TTL.

The file-upload learning path reuses the existing `object_storage_files`, `project_file_links`, and `file_text_fragments` tables from V3. It requires no new migration.
An explicit Notion MCP page import reuses these same tables and stores the page ID/URL as source metadata. It creates a project Markdown file snapshot, not a new database table.

User long-term memories reuse the V2 `user_memories` and `user_rules` tables. Their semantic index uses the existing LangGraph Store tables in `public` under a separate per-user namespace; it introduces no new Flyway migration.

Do not edit applied Flyway migrations. Once the Python feature set is stable, remove unused tables with forward migrations and build a separate clean baseline for fresh installations if needed.
