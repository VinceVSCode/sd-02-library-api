"""Books: anyone can read the catalogue; only a logged-in librarian can change it."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import or_, select

from library_api.deps import (
    LoggedIn,
    PagingDep,
    SessionDep,
    commit,
    conflict,
    not_found,
)
from library_api.models import Book, Loan
from library_api.schemas import BookCreate, BookOut, BookUpdate, Page

router = APIRouter(prefix="/books", tags=["books"])

ISBN_TAKEN = "A book with this ISBN already exists"


def _get(session: SessionDep, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise not_found("Book", book_id)
    return book


def _isbn_taken(session: SessionDep, isbn: str, other_than: int | None = None) -> bool:
    query = select(Book.id).where(Book.isbn == isbn)
    if other_than is not None:
        query = query.where(Book.id != other_than)
    return session.scalar(query) is not None


@router.get("", response_model=Page[BookOut])
def list_books(
    session: SessionDep,
    paging: PagingDep,
    q: str | None = None,
    available: bool | None = None,
) -> dict[str, Any]:
    """List books, oldest first. ``q`` searches title and author; ``available`` filters."""
    query = select(Book).order_by(Book.id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Book.title.ilike(pattern), Book.author.ilike(pattern)))
    if available is not None:
        query = query.where(Book.available == available)  # type: ignore[attr-defined]
    return paging.page(session, query)


@router.get("/{book_id}", response_model=BookOut)
def get_book(session: SessionDep, book_id: int) -> Book:
    """Return one book."""
    return _get(session, book_id)


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(session: SessionDep, _user: LoggedIn, data: BookCreate) -> Book:
    """Add a book. The ISBN is stored as 13 digits, and must be new."""
    if _isbn_taken(session, data.isbn):
        raise conflict(ISBN_TAKEN)
    book = Book(**data.model_dump())
    session.add(book)
    commit(session, ISBN_TAKEN)
    session.refresh(book)
    return book


@router.patch("/{book_id}", response_model=BookOut)
def update_book(session: SessionDep, _user: LoggedIn, book_id: int, data: BookUpdate) -> Book:
    """Change the fields that are sent."""
    book = _get(session, book_id)
    changes = data.model_dump(exclude_unset=True)
    if "isbn" in changes and _isbn_taken(session, changes["isbn"], other_than=book_id):
        raise conflict(ISBN_TAKEN)
    for name, value in changes.items():
        setattr(book, name, value)
    commit(session, ISBN_TAKEN)
    session.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(session: SessionDep, _user: LoggedIn, book_id: int) -> Response:
    """Delete a book that has never been lent. Its loan history is kept otherwise."""
    book = _get(session, book_id)
    has_loans = "This book has loans, so it cannot be deleted"
    if session.scalar(select(Loan.id).where(Loan.book_id == book_id).limit(1)) is not None:
        raise conflict(has_loans)
    session.delete(book)
    commit(session, has_loans)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
