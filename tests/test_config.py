"""Environment settings stay project-local and allow process overrides."""

from app.core import config


def test_database_settings_read_project_env_and_process_override(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "DECKWISE_DB_HOST=localhost\n"
        "DECKWISE_DB_PORT=5434\n"
        "DECKWISE_DB_NAME=developer_db\n"
        "DECKWISE_DB_USER=developer\n"
        "DECKWISE_DB_PASSWORD=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for key in ("DECKWISE_DB_HOST", "DECKWISE_DB_PORT", "DECKWISE_DB_NAME",
                "DECKWISE_DB_USER", "DECKWISE_DB_PASSWORD", "DB_PASSWORD", "PGPASSWORD"):
        monkeypatch.delenv(key, raising=False)

    settings = config.database_settings()
    assert (settings.host, settings.port, settings.name, settings.user, settings.password) == (
        "localhost", 5434, "developer_db", "developer", "from-file",
    )
    assert "from-file" not in repr(settings)

    monkeypatch.setenv("DECKWISE_DB_PASSWORD", "from-process")
    assert config.database_settings().password == "from-process"


def test_legacy_db_password_still_works(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("DB_PASSWORD=legacy-value\n", encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for key in ("DECKWISE_DB_PASSWORD", "DB_PASSWORD", "PGPASSWORD"):
        monkeypatch.delenv(key, raising=False)
    assert config.database_settings().password == "legacy-value"
