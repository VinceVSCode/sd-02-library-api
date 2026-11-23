"""Tests for the problems found in the quality review (version 1.0.1).

Each of these gave a 500 error, or a wrong answer, before the fix.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import add_book, add_member, lend
from library_api.app import EXAMPLE_SECRET_WARNING, create_app
from library_api.config import EXAMPLE_JWT_SECRET, Settings
from library_api.schemas import MAX_ID, normalise_isbn

TOO_BIG = MAX_ID + 1  # 2147483648: more than PostgreSQL's integer holds

# --- 1. numbers too large for the database ---------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", f"/books/{TOO_BIG}", None),
        ("GET", "/books/99999999999999999999", None),
        ("PATCH", f"/books/{TOO_BIG}", {"title": "T"}),
        ("DELETE", f"/books/{TOO_BIG}", None),
        ("GET", f"/members/{TOO_BIG}", None),
        ("DELETE", f"/members/{TOO_BIG}", None),
        ("GET", f"/loans/{TOO_BIG}", None),
        ("POST", f"/loans/{TOO_BIG}/return", None),
        ("GET", f"/loans?member_id={TOO_BIG}", None),
        ("GET", f"/loans?book_id={TOO_BIG}", None),
        ("GET", f"/books?offset={TOO_BIG}", None),
        ("GET", "/books?offset=10000000000000000000", None),
        ("POST", "/loans", {"book_id": TOO_BIG, "member_id": 1}),
        ("POST", "/loans", {"book_id": 1, "member_id": TOO_BIG}),
    ],
)
def test_numbers_too_large_for_the_database_are_refused_with_422(
    client: TestClient, auth: dict[str, str], method: str, path: str, body: dict | None
) -> None:
    answer = client.request(method, path, json=body, headers=auth)
    assert answer.status_code == 422, answer.text


@pytest.mark.parametrize("path", ["/books/0", "/books/-1", "/loans?member_id=0"])
def test_ids_below_1_are_refused_with_422(
    client: TestClient, auth: dict[str, str], path: str
) -> None:
    assert client.get(path, headers=auth).status_code == 422


def test_the_largest_id_is_still_accepted(client: TestClient, auth: dict[str, str]) -> None:
    answer = client.get(f"/books/{MAX_ID}")
    assert answer.status_code == 404
    assert client.get(f"/books?offset={MAX_ID}").json()["items"] == []


# --- 2. control characters such as NUL -------------------------------------------


# Each control character sits inside the text: at the ends it is trimmed like a space.
@pytest.mark.parametrize(
    "bad", ["a\u0000b", "tab\there", "line\nbreak", "bell\u0007ring", "c1\u0085x"]
)
def test_text_with_a_control_character_is_refused_with_422(
    client: TestClient, auth: dict[str, str], bad: str
) -> None:
    book = {"isbn": "9780306406157", "title": bad, "author": "A"}
    assert client.post("/books", json=book, headers=auth).status_code == 422
    member = {"name": bad, "email": "m@example.com"}
    assert client.post("/members", json=member, headers=auth).status_code == 422
    email = {"name": "M", "email": f"m{bad}@example.com"}
    assert client.post("/members", json=email, headers=auth).status_code == 422
    assert client.get("/books", params={"q": bad}).status_code == 422
    assert client.get("/members", params={"q": bad}, headers=auth).status_code == 422


def test_a_search_longer_than_200_characters_is_refused(client: TestClient) -> None:
    assert client.get("/books", params={"q": "a" * 201}).status_code == 422


def test_a_username_with_a_nul_is_refused_like_a_wrong_password(client: TestClient) -> None:
    answer = client.post("/auth/token", data={"username": "libr\u0000arian", "password": "x"})
    assert answer.status_code == 401
    assert answer.json()["detail"] == "Wrong username or password"


def test_greek_and_other_letters_are_still_accepted(
    client: TestClient, auth: dict[str, str]
) -> None:
    book = add_book(client, auth, title="Οδύσσεια", author="Όμηρος")
    assert book["title"] == "Οδύσσεια"
    # Same letter case: SQLite (the default test database) ignores case only for
    # English letters. PostgreSQL ignores it for Greek too.
    found = client.get("/books", params={"q": "δύσσ"}).json()["items"]
    assert [item["id"] for item in found] == [book["id"]]


@pytest.mark.parametrize("digits", ["٩٧٨٠٣٠٦٤٠٦١٥٧", "٠٣٠٦٤٠٦١٥٢", "９７８０３０６４０６１５７"])
def test_an_isbn_must_use_the_digits_0_to_9(digits: str) -> None:
    with pytest.raises(ValueError, match="10 or 13 digits"):
        normalise_isbn(digits)


# --- 3. search is plain text: % and _ are not wildcards ---------------------------


def test_percent_and_underscore_are_searched_as_plain_text(
    client: TestClient, auth: dict[str, str]
) -> None:
    add_book(client, auth, isbn="9780306406157", title="Dune", author="Frank Herbert")
    add_book(client, auth, isbn="9780804429573", title="100% Python", author="A")
    add_book(client, auth, isbn="9780131103627", title="snake_case", author="B")

    def titles(q: str) -> list[str]:
        return [book["title"] for book in client.get("/books", params={"q": q}).json()["items"]]

    assert titles("%") == ["100% Python"]
    assert titles("_") == ["snake_case"]
    assert titles("0%") == ["100% Python"]
    assert titles("e_c") == ["snake_case"]
    assert titles("D_ne") == []
    assert titles("\\") == []


def test_member_search_is_plain_text_too(client: TestClient, auth: dict[str, str]) -> None:
    add_member(client, auth, name="Maria", email="maria@example.com")
    found = client.get("/members", params={"q": "%"}, headers=auth).json()
    assert found["total"] == 0


def test_loans_still_work_with_the_new_id_rules(client: TestClient, auth: dict[str, str]) -> None:
    answer = lend(client, auth, add_book(client, auth), add_member(client, auth))
    assert answer.status_code == 201


# --- 4. a warning when the example JWT secret is used -----------------------------


def test_the_example_secret_matches_env_example() -> None:
    env_example = Path(__file__).resolve().parent.parent / ".env.example"
    assert f"JWT_SECRET={EXAMPLE_JWT_SECRET}\n" in env_example.read_text(encoding="utf-8")


def test_a_warning_is_logged_when_the_example_secret_is_used(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="library_api"):
        create_app(Settings(database_url="sqlite://", jwt_secret=EXAMPLE_JWT_SECRET))
    assert caplog.messages == [EXAMPLE_SECRET_WARNING]


def test_no_warning_with_a_secret_of_your_own(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="library_api"):
        create_app(
            Settings(database_url="sqlite://", jwt_secret="my-own-long-random-secret-1234567890")
        )
    assert caplog.messages == []
