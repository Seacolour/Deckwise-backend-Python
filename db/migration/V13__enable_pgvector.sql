-- pgvector is installed on the PostgreSQL server before this migration runs.
-- Keep its type and functions in public; application tables remain in backend_data.
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
