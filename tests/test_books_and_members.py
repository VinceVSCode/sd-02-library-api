"""Books and members: create, read, update, delete, paging, search and validation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import add_book, add_member, lend

ISBNS = ["9780306406157", "9780804429573", "9780131103627", "9780201633610", "9780262033848"]

# --- books ---------------------------------------------------------------------


def test_a_new_book_is_stored_and_available(client: TestClient, auth: dict[str, str]) -> None:
    book = add_book(client, auth, isbn="0-306-40615-2", title="  Signals  ", published_year=1999)
    assert book["isbn"] == "9780306406157"
    assert book["title"] == "Signals"
    assert book["available"] is True
    assert client.get(f"/books/{book['id']}").json() == book


def test_the_same_isbn_cannot_be_added_twice_even_written_differently(
    client: TestClient, auth: dict[str, str]
) -> None:
    add_book(client, auth, isbn="9780306406157")
    answer = client.post(
        "/books", json={"isbn": "0306406152", "title": "Copy", "author": "B"}, headers=auth
    )
    assert answer.status_code == 409
    assert answer.json()["detail"] == "A book with this ISBN already exists"


@pytest.mark.parametrize(
    "body",
    [
        {"isbn": "9780306406158", "title": "T", "author": "A"},  # wrong check digit
        {"isbn": "9780306406157", "title": "   ", "author": "A"},  # blank title
        {"isbn": "9780306406157", "title": "T" * 201, "author": "A"},
        {"isbn": "9780306406157", "title": "T"},  # no author
        {"isbn": "9780306406157", "title": "T", "author": "A", "published_year": 1200},
        {"isbn": "9780306406157", "title": "T", "author": "A", "pages": 300},  # unknown field
    ],
)
def test_an_invalid_book_is_refused_with_422(
    client: TestClient, auth: dict[str, str], body: dict
) -> None:
    answer = client.post("/books", json=body, headers=auth)
    assert answer.status_code == 422
    assert client.get("/books").json()["total"] == 0


def test_a_book_is_updated_only_where_fields_are_sent(
    client: TestClient, auth: dict[str, str]
) -> None:
    book = add_book(client, auth, published_year=1999)
    answer = client.patch(f"/books/{book['id']}", json={"title": "New"}, headers=auth)
    assert answer.status_code == 200
    assert answer.json() | {"title": "Signals"} == book
    cleared = client.patch(f"/books/{book['id']}", json={"published_year": None}, headers=auth)
    assert cleared.json()["published_year"] is None


def test_a_required_field_cannot_be_set_to_null(
    client: TestClient, auth: dict[str, str]
) -> None:
    book = add_book(client, auth)
    answer = client.patch(f"/books/{book['id']}", json={"title": None}, headers=auth)
    assert answer.status_code == 422
    assert "title cannot be null" in answer.text


def test_an_update_cannot_take_another_books_isbn(
    client: TestClient, auth: dict[str, str]
) -> None:
    add_book(client, auth, isbn=ISBNS[0])
    second = add_book(client, auth, isbn=ISBNS[1])
    answer = client.patch(f"/books/{second['id']}", json={"isbn": ISBNS[0]}, headers=auth)
    assert answer.status_code == 409
    same = client.patch(f"/books/{second['id']}", json={"isbn": ISBNS[1]}, headers=auth)
    assert same.status_code == 200


def test_missing_books_give_404(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/books/999").json() == {"detail": "Book 999 does not exist"}
    assert client.patch("/books/999", json={"title": "T"}, headers=auth).status_code == 404
    assert client.delete("/books/999", headers=auth).status_code == 404


def test_a_book_without_loans_can_be_deleted(client: TestClient, auth: dict[str, str]) -> None:
    book = add_book(client, auth)
    assert client.delete(f"/books/{book['id']}", headers=auth).status_code == 204
    assert client.get(f"/books/{book['id']}").status_code == 404


def test_a_book_with_loans_cannot_be_deleted(client: TestClient, auth: dict[str, str]) -> None:
    book = add_book(client, auth)
    member = add_member(client, auth)
    loan = lend(client, auth, book, member).json()
    client.post(f"/loans/{loan['id']}/return", headers=auth)  # even after it is returned
    answer = client.delete(f"/books/{book['id']}", headers=auth)
    assert answer.status_code == 409
    assert "has loans" in answer.json()["detail"]


def test_books_are_paged_and_counted(client: TestClient, auth: dict[str, str]) -> None:
    for number, isbn in enumerate(ISBNS):
        add_book(client, auth, isbn=isbn, title=f"Book {number}")
    page = client.get("/books", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 5
    assert (page["limit"], page["offset"]) == (2, 2)
    assert [book["title"] for book in page["items"]] == ["Book 2", "Book 3"]
    assert client.get("/books", params={"offset": 10}).json()["items"] == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}])
def test_invalid_paging_is_refused(client: TestClient, params: dict) -> None:
    assert client.get("/books", params=params).status_code == 422


def test_books_can_be_searched_and_filtered_by_availability(
    client: TestClient, auth: dict[str, str]
) -> None:
    dune = add_book(client, auth, isbn=ISBNS[0], title="Dune", author="Frank Herbert")
    add_book(client, auth, isbn=ISBNS[1], title="Emma", author="Jane Austen")
    member = add_member(client, auth)
    lend(client, auth, dune, member)

    def titles(**params: object) -> list[str]:
        return [book["title"] for book in client.get("/books", params=params).json()["items"]]

    assert titles(q="austen") == ["Emma"]
    assert titles(q="DUNE") == ["Dune"]
    assert titles(available=True) == ["Emma"]
    assert titles(available=False) == ["Dune"]
    assert titles(q="emma", available=False) == []


# --- members -------------------------------------------------------------------


def test_a_member_is_stored_with_a_lower_case_email(
    client: TestClient, auth: dict[str, str]
) -> None:
    member = add_member(client, auth, email=" Maria@Example.com ")
    assert member["email"] == "maria@example.com"
    assert member["joined_on"]
    assert client.get(f"/members/{member['id']}", headers=auth).json() == member


def test_the_same_email_cannot_be_used_twice(client: TestClient, auth: dict[str, str]) -> None:
    add_member(client, auth, email="maria@example.com")
    answer = client.post(
        "/members", json={"name": "Other", "email": "MARIA@example.com"}, headers=auth
    )
    assert answer.status_code == 409


def test_an_invalid_member_is_refused(client: TestClient, auth: dict[str, str]) -> None:
    for body in ({"name": "M", "email": "not-an-email"}, {"name": "", "email": "m@example.com"}):
        assert client.post("/members", json=body, headers=auth).status_code == 422


def test_members_can_be_updated_searched_and_deleted(
    client: TestClient, auth: dict[str, str]
) -> None:
    maria = add_member(client, auth)
    add_member(client, auth, name="Nikos", email="nikos@example.com")
    renamed = client.patch(f"/members/{maria['id']}", json={"name": "Maria P."}, headers=auth)
    assert renamed.json()["name"] == "Maria P."
    found = client.get("/members", params={"q": "nikos"}, headers=auth).json()
    assert [member["name"] for member in found["items"]] == ["Nikos"]
    assert client.delete(f"/members/{maria['id']}", headers=auth).status_code == 204
    assert client.get(f"/members/{maria['id']}", headers=auth).status_code == 404


def test_a_member_with_loans_cannot_be_deleted(client: TestClient, auth: dict[str, str]) -> None:
    member = add_member(client, auth)
    lend(client, auth, add_book(client, auth), member)
    assert client.delete(f"/members/{member['id']}", headers=auth).status_code == 409
