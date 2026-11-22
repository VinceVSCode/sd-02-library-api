"""Fill an empty database with demo data: a librarian, books, members and loans.

Usage: python scripts/seed.py
With Docker: docker compose exec api python scripts/seed.py

The librarian's username and password come from DEMO_USERNAME and DEMO_PASSWORD
(see .env.example). Everything else is made up: the ISBNs are demo numbers with
valid check digits, not those of real editions, and the members do not exist.
Running it again changes nothing.
"""

from __future__ import annotations

import sys
from datetime import timedelta

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from library_api.config import get_settings
from library_api.db import make_engine
from library_api.models import Book, Loan, Member, User, today
from library_api.schemas import isbn13_check_digit
from library_api.security import hash_password

BOOKS = [
    ("Pride and Prejudice", "Jane Austen", 1813),
    ("Frankenstein", "Mary Shelley", 1818),
    ("Moby-Dick", "Herman Melville", 1851),
    ("Great Expectations", "Charles Dickens", 1861),
    ("Crime and Punishment", "Fyodor Dostoevsky", 1866),
    ("Twenty Thousand Leagues Under the Seas", "Jules Verne", 1870),
    ("The Adventures of Tom Sawyer", "Mark Twain", 1876),
    ("Anna Karenina", "Leo Tolstoy", 1878),
    ("Treasure Island", "Robert Louis Stevenson", 1883),
    ("The Picture of Dorian Gray", "Oscar Wilde", 1890),
    ("Dracula", "Bram Stoker", 1897),
    ("The Time Machine", "H. G. Wells", 1895),
]
MEMBERS = [
    ("Eleni Demo", "eleni@example.com"),
    ("Giorgos Demo", "giorgos@example.com"),
    ("Sofia Demo", "sofia@example.com"),
    ("Alex Demo", "alex@example.com"),
]
# (book number, member number, lent this many days ago, loan length in days, returned)
LOANS = [
    (0, 0, 3, 14, False),
    (2, 1, 10, 14, False),
    (4, 2, 20, 14, False),  # overdue
    (6, 3, 30, 14, True),
]


class DemoLogin(BaseSettings):
    """The demo librarian, from DEMO_USERNAME and DEMO_PASSWORD (environment or .env)."""

    model_config = SettingsConfigDict(env_prefix="demo_", env_file=".env", extra="ignore")

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8)


def demo_isbn(number: int) -> str:
    """Return a made-up ISBN-13 with a valid check digit."""
    first_twelve = f"978000000{number:03d}"
    return first_twelve + isbn13_check_digit(first_twelve)


def seed(session: Session, username: str, password: str) -> list[str]:
    """Add whatever demo data is missing. Return a line for each thing added."""
    done = []
    if session.scalar(select(User).where(User.username == username)) is None:
        session.add(User(username=username, password_hash=hash_password(password)))
        done.append(f"librarian '{username}'")
    if session.scalar(select(Book.id).limit(1)) is None:
        books = [
            Book(isbn=demo_isbn(n), title=title, author=author, published_year=year)
            for n, (title, author, year) in enumerate(BOOKS)
        ]
        members = [Member(name=name, email=email) for name, email in MEMBERS]
        session.add_all(books + members)
        session.flush()
        for book, member, days_ago, length, returned in LOANS:
            lent = today() - timedelta(days=days_ago)
            session.add(
                Loan(
                    book_id=books[book].id,
                    member_id=members[member].id,
                    loaned_on=lent,
                    due_on=lent + timedelta(days=length),
                    returned_on=lent + timedelta(days=7) if returned else None,
                )
            )
        done.append(f"{len(books)} books, {len(members)} members, {len(LOANS)} loans")
    session.commit()
    return done


def main() -> int:
    try:
        login = DemoLogin()  # type: ignore[call-arg]  # values come from the environment
    except ValidationError:
        print(
            "Error: set DEMO_USERNAME and DEMO_PASSWORD (8 characters or more), "
            "for example by copying .env.example to .env",
            file=sys.stderr,
        )
        return 1
    engine = make_engine(get_settings().sqlalchemy_url())
    with Session(engine) as session:
        done = seed(session, login.username, login.password)
    engine.dispose()
    print(
        "Added: " + "; ".join(done) if done else "Nothing to add: the demo data is already there."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
