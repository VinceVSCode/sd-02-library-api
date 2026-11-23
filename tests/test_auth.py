"""Logging in, and that protected endpoints refuse requests without a valid token."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import PASSWORD, SECRET, add_book
from library_api.models import User
from library_api.security import create_token

# Every endpoint that needs a login: (method, path, body).
PROTECTED = [
    ("POST", "/books", {"isbn": "9780306406157", "title": "T", "author": "A"}),
    ("PATCH", "/books/1", {"title": "T"}),
    ("DELETE", "/books/1", None),
    ("GET", "/members", None),
    ("GET", "/members/1", None),
    ("POST", "/members", {"name": "M", "email": "m@example.com"}),
    ("PATCH", "/members/1", {"name": "M"}),
    ("DELETE", "/members/1", None),
    ("GET", "/loans", None),
    ("GET", "/loans/1", None),
    ("POST", "/loans", {"book_id": 1, "member_id": 1}),
    ("POST", "/loans/1/return", None),
]


def test_login_returns_a_bearer_token(client: TestClient, librarian: User) -> None:
    answer = client.post("/auth/token", data={"username": "librarian", "password": PASSWORD})
    assert answer.status_code == 200
    body = answer.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60


@pytest.mark.parametrize(
    ("username", "password"), [("librarian", "wrong"), ("nobody", PASSWORD), ("", "")]
)
def test_login_with_wrong_details_is_refused_with_the_same_message(
    client: TestClient, librarian: User, username: str, password: str
) -> None:
    answer = client.post("/auth/token", data={"username": username, "password": password})
    assert answer.status_code in (401, 422)
    if answer.status_code == 401:
        assert answer.json()["detail"] == "Wrong username or password"
        assert answer.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
def test_protected_endpoints_refuse_a_request_without_a_token(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    answer = client.request(method, path, json=body)
    assert answer.status_code == 401
    assert answer.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
def test_protected_endpoints_refuse_an_invalid_token(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    forged = create_token("librarian", "a-different-secret-of-the-same-length!!", 30)
    answer = client.request(method, path, json=body, headers={"Authorization": f"Bearer {forged}"})
    assert answer.status_code == 401
    assert answer.json()["detail"] == "The token is invalid or has expired"


def test_an_expired_token_is_refused(client: TestClient, librarian: User) -> None:
    old = create_token("librarian", SECRET, 30, now=datetime.now(UTC) - timedelta(hours=1))
    answer = client.get("/members", headers={"Authorization": f"Bearer {old}"})
    assert answer.status_code == 401


def test_a_token_for_a_deleted_user_is_refused(
    client: TestClient, session: Session, librarian: User, auth: dict[str, str]
) -> None:
    assert client.get("/members", headers=auth).status_code == 200
    session.delete(librarian)
    session.commit()
    answer = client.get("/members", headers=auth)
    assert answer.status_code == 401
    assert "no longer exists" in answer.json()["detail"]


def test_a_malformed_authorization_header_is_refused(client: TestClient) -> None:
    for header in ("Bearer", "Basic abc", "Bearer not.a.token"):
        assert client.get("/members", headers={"Authorization": header}).status_code == 401


def test_books_can_be_read_without_logging_in(client: TestClient, auth: dict[str, str]) -> None:
    book = add_book(client, auth)
    assert client.get("/books").status_code == 200
    assert client.get(f"/books/{book['id']}").status_code == 200
