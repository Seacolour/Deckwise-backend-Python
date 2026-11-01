"""Create the configured development database and apply Flyway migrations."""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import database_settings  # noqa: E402
from app.db.session import schema_status  # noqa: E402


def main() -> None:
    settings = database_settings()
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname="postgres",
        user=settings.user,
        password=settings.password,
        autocommit=True,
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (settings.name,),
        ).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.name)))

    environment = os.environ.copy()
    if settings.password is not None:
        environment["PGPASSWORD"] = settings.password
    jdbc_url = f"jdbc:postgresql://{settings.host}:{settings.port}/{settings.name}"
    maven = "mvn.cmd" if os.name == "nt" else "mvn"
    subprocess.run(
        [maven, "-f", str(PROJECT_ROOT / "db" / "pom.xml"),
         f"-Ddeckwise.jdbc.url={jdbc_url}", f"-Ddeckwise.jdbc.user={settings.user}",
         "flyway:migrate", "flyway:validate"],
        env=environment,
        cwd=PROJECT_ROOT,
        check=True,
    )
    version, table_count = schema_status()
    print(f"Python database connection OK: version={version}, tables={table_count}")


if __name__ == "__main__":
    main()
