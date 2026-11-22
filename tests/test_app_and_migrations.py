"""The health endpoint, the OpenAPI page, the settings, and the migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from pydantic import ValidationError

from library_api.app import create_app
from library_api.config import Settings
from library_api.db import alembic_config, make_engine, migrate
from library_api.models import Base


def test_health_reports_ok(client: TestClient) -> None:
    answer = client.get("/health")
    assert answer.status_code == 200
    assert answer.json() == {"status": "ok", "database": "ok"}


def test_health_reports_503_when_the_database_is_unreachable(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-folder" / "library.db"
    app = create_app(Settings(database_url=f"sqlite:///{missing}", jwt_secret="x" * 32))
    with TestClient(app) as client:
        answer = client.get("/health")
    assert answer.status_code == 503
    assert answer.json() == {"status": "error", "database": "unreachable"}


def test_the_openapi_page_is_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/", follow_redirects=False).headers["location"] == "/docs"
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/books", "/members", "/loans", "/auth/token", "/health"} <= set(paths)


def test_a_short_jwt_secret_is_refused_at_start_up() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(database_url="sqlite://", jwt_secret="short")


def test_the_database_url_is_built_from_the_postgres_settings() -> None:
    settings = Settings(
        jwt_secret="x" * 32,
        postgres_user="u",
        postgres_password="p",
        postgres_host="db",
        postgres_db="library",
    )
    assert settings.sqlalchemy_url() == "postgresql+psycopg://u:p@db:5432/library"


def test_the_migrations_match_the_models_and_can_be_undone(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    migrate(url)
    engine = make_engine(url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []
    command.downgrade(alembic_config(url), "base")
    command.upgrade(alembic_config(url), "head")
    engine.dispose()
