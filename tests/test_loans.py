"""Loans: the business rules, and the database rules behind them."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conftest import add_book, add_member, lend
from library_api import models
from library_api.models import Loan

TODAY = date(2026, 11, 22)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "today", lambda: TODAY)


def test_lending_a_book_makes_it_unavailable(client: TestClient, auth: dict[str, str]) -> None:
    book, member = add_book(client, auth), add_member(client, auth)
    answer = lend(client, auth, book, member, days=7)
    assert answer.status_code == 201
    loan = answer.json()
    assert loan["loaned_on"] == "2026-11-22"
    assert loan["due_on"] == "2026-11-29"
    assert loan["returned_on"] is None
    assert loan["overdue"] is False
    assert client.get(f"/books/{book['id']}").json()["available"] is False


def test_a_loan_is_due_in_14_days_unless_said_otherwise(
    client: TestClient, auth: dict[str, str]
) -> None:
    loan = lend(client, auth, add_book(client, auth), add_member(client, auth)).json()
    assert loan["due_on"] == "2026-12-06"


def test_a_book_cannot_be_lent_twice(client: TestClient, auth: dict[str, str]) -> None:
    book = add_book(client, auth)
    lend(client, auth, book, add_member(client, auth))
    other = add_member(client, auth, name="Nikos", email="nikos@example.com")
    answer = lend(client, auth, book, other)
    assert answer.status_code == 409
    assert answer.json()["detail"] == "This book is already lent"


def test_the_database_itself_refuses_a_second_open_loan(
    client: TestClient, auth: dict[str, str], session: Session
) -> None:
    """The rule holds even if two requests pass the API's check at the same moment."""
    book, member = add_book(client, auth), add_member(client, auth)
    lend(client, auth, book, member)
    session.add(
        Loan(book_id=book["id"], member_id=member["id"], loaned_on=TODAY, due_on=TODAY)
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_returned_book_can_be_lent_again(client: TestClient, auth: dict[str, str]) -> None:
    book, member = add_book(client, auth), add_member(client, auth)
    loan = lend(client, auth, book, member).json()
    returned = client.post(f"/loans/{loan['id']}/return", headers=auth)
    assert returned.status_code == 200
    assert returned.json()["returned_on"] == "2026-11-22"
    assert client.get(f"/books/{book['id']}").json()["available"] is True
    assert lend(client, auth, book, member).status_code == 201


def test_a_loan_cannot_be_returned_twice(client: TestClient, auth: dict[str, str]) -> None:
    loan = lend(client, auth, add_book(client, auth), add_member(client, auth)).json()
    client.post(f"/loans/{loan['id']}/return", headers=auth)
    again = client.post(f"/loans/{loan['id']}/return", headers=auth)
    assert again.status_code == 409
    assert again.json()["detail"] == "This loan was already returned on 2026-11-22"


def test_a_loan_is_overdue_after_its_due_date(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    loan = lend(client, auth, add_book(client, auth), add_member(client, auth), days=3).json()
    monkeypatch.setattr(models, "today", lambda: TODAY + timedelta(days=3))
    assert client.get(f"/loans/{loan['id']}", headers=auth).json()["overdue"] is False
    monkeypatch.setattr(models, "today", lambda: TODAY + timedelta(days=4))
    assert client.get(f"/loans/{loan['id']}", headers=auth).json()["overdue"] is True
    returned = client.post(f"/loans/{loan['id']}/return", headers=auth).json()
    assert returned["overdue"] is False


def test_lending_a_missing_book_or_to_a_missing_member_gives_404(
    client: TestClient, auth: dict[str, str]
) -> None:
    book, member = add_book(client, auth), add_member(client, auth)
    assert lend(client, auth, {"id": 999}, member).json()["detail"] == "Book 999 does not exist"
    assert lend(client, auth, book, {"id": 999}).json()["detail"] == "Member 999 does not exist"
    assert client.post("/loans/999/return", headers=auth).status_code == 404


@pytest.mark.parametrize("days", [0, 61, -1])
def test_the_loan_length_must_be_1_to_60_days(
    client: TestClient, auth: dict[str, str], days: int
) -> None:
    answer = lend(client, auth, add_book(client, auth), add_member(client, auth), days=days)
    assert answer.status_code == 422


def test_loans_can_be_filtered(client: TestClient, auth: dict[str, str]) -> None:
    first = add_book(client, auth, isbn="9780306406157")
    second = add_book(client, auth, isbn="9780804429573")
    maria = add_member(client, auth)
    nikos = add_member(client, auth, name="Nikos", email="nikos@example.com")
    old = lend(client, auth, first, maria).json()
    client.post(f"/loans/{old['id']}/return", headers=auth)
    lend(client, auth, first, nikos)
    lend(client, auth, second, maria)

    def count(**params: object) -> int:
        return client.get("/loans", params=params, headers=auth).json()["total"]

    assert count() == 3
    assert count(open=True) == 2
    assert count(open=False) == 1
    assert count(member_id=maria["id"]) == 2
    assert count(book_id=first["id"], open=True) == 1
    newest = client.get("/loans", headers=auth).json()["items"][0]
    assert newest["book_id"] == second["id"]
