"""The demo data script."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import seed
from conftest import PASSWORD
from library_api.models import Book, Loan, Member, User
from library_api.schemas import normalise_isbn


def test_seed_fills_an_empty_database_once(session: Session, client: TestClient) -> None:
    first = seed.seed(session, "demo", PASSWORD)
    assert first == ["librarian 'demo'", "12 books, 4 members, 4 loans"]
    assert seed.seed(session, "demo", PASSWORD) == []
    count = {
        table.__name__: session.scalar(select(func.count()).select_from(table))
        for table in (User, Book, Member, Loan)
    }
    assert count == {"User": 1, "Book": 12, "Member": 4, "Loan": 4}

    login = client.post("/auth/token", data={"username": "demo", "password": PASSWORD})
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    loans = client.get("/loans", headers=auth).json()["items"]
    assert sum(loan["overdue"] for loan in loans) == 1
    assert client.get("/books", params={"available": False}).json()["total"] == 3


def test_the_demo_isbns_are_valid_and_distinct() -> None:
    isbns = [seed.demo_isbn(n) for n in range(len(seed.BOOKS))]
    assert [normalise_isbn(isbn) for isbn in isbns] == isbns
    assert len(set(isbns)) == len(isbns)


def test_seed_refuses_to_run_without_a_demo_login(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("DEMO_USERNAME", raising=False)
    monkeypatch.setenv("DEMO_PASSWORD", "short")
    assert seed.main() == 1
    assert "DEMO_USERNAME and DEMO_PASSWORD" in capsys.readouterr().err
