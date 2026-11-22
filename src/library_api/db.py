"""The database connection and the migrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def make_engine(url: str) -> Engine:
    """Create the engine. SQLite (used by the tests) is told to enforce foreign keys."""
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _foreign_keys_on(connection: Any, _record: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def alembic_config(url: str) -> Config:
    """Return an Alembic configuration for this database, without an alembic.ini file."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def migrate(url: str) -> None:
    """Bring the database up to the latest migration."""
    command.upgrade(alembic_config(url), "head")
