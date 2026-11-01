"""Connection and transaction setup for the local PostgreSQL database."""

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # psycopg reads PGPASSWORD from the process environment via libpq.
    url = URL.create(
        "postgresql+psycopg",
        username=os.getenv("DECKWISE_DB_USER", "postgres"),
        host=os.getenv("DECKWISE_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DECKWISE_DB_PORT", "5432")),
        database=os.getenv("DECKWISE_DB_NAME", "deckwise_python_dev"),
    )
    return create_engine(url, pool_pre_ping=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        with session.begin():
            yield session


def schema_status() -> tuple[int, int]:
    with get_engine().connect() as connection:
        version = connection.scalar(
            text(
                "SELECT max(version::integer) "
                "FROM backend_data.flyway_schema_history "
                "WHERE success AND type = 'SQL'"
            )
        )
        table_count = connection.scalar(
            text(
                "SELECT count(*) FROM pg_tables "
                "WHERE schemaname = 'backend_data' "
                "AND tablename <> 'flyway_schema_history'"
            )
        )
    return int(version or 0), int(table_count or 0)


if __name__ == "__main__":
    schema_version, domain_tables = schema_status()
    print(f"Python database connection OK: version={schema_version}, tables={domain_tables}")
