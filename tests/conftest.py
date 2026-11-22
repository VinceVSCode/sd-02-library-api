"""Shared test setup: a test database built by the real migrations, and a logged-in client.

By default the tests use a SQLite file in a temporary folder, so they run
without Docker. Set TEST_DATABASE_URL to run them against PostgreSQL instead
(CI does both). Every table is emptied before each test.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from library_api.app import create_app
from library_api.config import Settings
from library_api.db import make_engine, migrate
from library_api.models import Book, Loan, Member, User
from library_api.security import hash_password

SECRET = "test-secret-that-is-long-enough-for-hs256"
PASSWORD = "correct horse battery staple"


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        # The tests delete every row, so refuse a database that is not clearly a test one.
        assert "test" in url.rsplit("/", 1)[-1], "TEST_DATABASE_URL must name a test database"
    else:
        url = f"sqlite:///{Path(tmp_path_factory.mktemp('db')) / 'library.db'}"
    migrate(url)
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = make_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on an empty database."""
    with Session(engine) as session:
        for table in (Loan, Book, Member, User):
            session.execute(delete(table))
        session.commit()
        yield session


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(database_url=database_url, jwt_secret=SECRET, token_minutes=30)


@pytest.fixture
def client(settings: Settings, session: Session) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as client:
        yield client
    app.state.engine.dispose()


@pytest.fixture
def librarian(session: Session) -> User:
    user = User(username="librarian", password_hash=hash_password(PASSWORD))
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def auth(client: TestClient, librarian: User) -> dict[str, str]:
    """Headers with a valid token, from the real login endpoint."""
    answer = client.post("/auth/token", data={"username": "librarian", "password": PASSWORD})
    assert answer.status_code == 200, answer.text
    return {"Authorization": f"Bearer {answer.json()['access_token']}"}


def add_book(client: TestClient, auth: dict[str, str], **fields: object) -> dict:
    data = {"isbn": "9780306406157", "title": "Signals", "author": "A. Writer", **fields}
    answer = client.post("/books", json=data, headers=auth)
    assert answer.status_code == 201, answer.text
    return answer.json()


def add_member(client: TestClient, auth: dict[str, str], **fields: object) -> dict:
    data = {"name": "Maria", "email": "maria@example.com", **fields}
    answer = client.post("/members", json=data, headers=auth)
    assert answer.status_code == 201, answer.text
    return answer.json()


def lend(client: TestClient, auth: dict[str, str], book: dict, member: dict, **fields: object):
    data = {"book_id": book["id"], "member_id": member["id"], **fields}
    return client.post("/loans", json=data, headers=auth)
