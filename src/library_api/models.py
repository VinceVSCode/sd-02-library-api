"""The database tables: users (librarians), books, members and loans.

The rules that must never break are kept in the database itself, so they hold
even if two requests arrive at the same moment:

- an ISBN and a member's email are unique;
- a loan points to an existing book and member, and neither can be deleted
  while a loan refers to it;
- a book has at most one loan that is not returned (a partial unique index).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    exists,
    func,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column, relationship


def today() -> date:
    """Return today's date. The tests replace this to move the clock."""
    return date.today()


class Base(DeclarativeBase):
    """Base class of every table."""


class User(Base):
    """A librarian who can log in and change data."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Book(Base):
    """One physical copy of a book."""

    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "published_year IS NULL OR published_year BETWEEN 1450 AND 2100",
            name="ck_books_published_year",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(String(13), unique=True)  # always 13 digits
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(200))
    published_year: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    loans: Mapped[list[Loan]] = relationship(back_populates="book", passive_deletes="all")


class Member(Base):
    """A person who can borrow books."""

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored in lower case
    joined_on: Mapped[date] = mapped_column(Date, server_default=func.current_date())

    loans: Mapped[list[Loan]] = relationship(back_populates="member", passive_deletes="all")


class Loan(Base):
    """A book lent to a member. ``returned_on`` stays empty until the book comes back."""

    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("due_on >= loaned_on", name="ck_loans_due_after_loan"),
        CheckConstraint(
            "returned_on IS NULL OR returned_on >= loaned_on", name="ck_loans_return_after_loan"
        ),
        # At most one open loan per book: the rule "a book cannot be lent twice".
        Index(
            "uq_loans_open_book",
            "book_id",
            unique=True,
            postgresql_where=text("returned_on IS NULL"),
            sqlite_where=text("returned_on IS NULL"),
        ),
        Index("ix_loans_member_id", "member_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="RESTRICT"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"))
    loaned_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date] = mapped_column(Date)
    returned_on: Mapped[date | None] = mapped_column(Date)

    book: Mapped[Book] = relationship(back_populates="loans")
    member: Mapped[Member] = relationship(back_populates="loans")

    @property
    def overdue(self) -> bool:
        """True if the book is still out after its due date."""
        return self.returned_on is None and self.due_on < today()


# A book is available when it has no open loan. Defined here, after Loan exists,
# so that it can be read on every book and used in filters.
Book.available = column_property(  # type: ignore[attr-defined]
    ~exists(select(Loan.id).where(Loan.book_id == Book.id, Loan.returned_on.is_(None)))
)
