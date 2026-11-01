"""Connection and transaction setup for the local PostgreSQL database."""

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session

from app.core.config import database_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = database_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.name,
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
