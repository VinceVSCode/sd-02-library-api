"""Loans: lending a book to a member and taking it back. Needs a logged-in librarian."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from library_api import models
from library_api.deps import (
    LoggedIn,
    PagingDep,
    SessionDep,
    commit,
    conflict,
    not_found,
)
from library_api.models import Book, Loan, Member
from library_api.schemas import LoanCreate, LoanOut, Page

router = APIRouter(prefix="/loans", tags=["loans"])

ALREADY_LENT = "This book is already lent"


def _get(session: SessionDep, loan_id: int) -> Loan:
    loan = session.get(Loan, loan_id)
    if loan is None:
        raise not_found("Loan", loan_id)
    return loan


@router.get("", response_model=Page[LoanOut])
def list_loans(
    session: SessionDep,
    _user: LoggedIn,
    paging: PagingDep,
    book_id: int | None = None,
    member_id: int | None = None,
    open: bool | None = None,
) -> dict[str, Any]:
    """List loans, newest first. Filter by book, by member, or by open (not returned)."""
    query = select(Loan).order_by(Loan.id.desc())
    if book_id is not None:
        query = query.where(Loan.book_id == book_id)
    if member_id is not None:
        query = query.where(Loan.member_id == member_id)
    if open is not None:
        query = query.where(Loan.returned_on.is_(None) if open else Loan.returned_on.is_not(None))
    return paging.page(session, query)


@router.get("/{loan_id}", response_model=LoanOut)
def get_loan(session: SessionDep, _user: LoggedIn, loan_id: int) -> Loan:
    """Return one loan."""
    return _get(session, loan_id)


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def lend(session: SessionDep, _user: LoggedIn, data: LoanCreate) -> Loan:
    """Lend a book to a member from today, due after ``days`` days."""
    if session.get(Book, data.book_id) is None:
        raise not_found("Book", data.book_id)
    if session.get(Member, data.member_id) is None:
        raise not_found("Member", data.member_id)
    open_loan = select(Loan.id).where(Loan.book_id == data.book_id, Loan.returned_on.is_(None))
    if session.scalar(open_loan) is not None:
        raise conflict(ALREADY_LENT)
    today = models.today()
    loan = Loan(
        book_id=data.book_id,
        member_id=data.member_id,
        loaned_on=today,
        due_on=today + timedelta(days=data.days),
    )
    session.add(loan)
    # The partial unique index refuses a second open loan, even from a parallel request.
    commit(session, ALREADY_LENT)
    session.refresh(loan)
    return loan


@router.post("/{loan_id}/return", response_model=LoanOut)
def return_book(session: SessionDep, _user: LoggedIn, loan_id: int) -> Loan:
    """Mark the book as returned today. A loan can be returned only once."""
    loan = _get(session, loan_id)
    if loan.returned_on is not None:
        raise conflict(f"This loan was already returned on {loan.returned_on.isoformat()}")
    loan.returned_on = models.today()
    commit(session, "The loan could not be returned")
    session.refresh(loan)
    return loan
