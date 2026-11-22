"""Members: personal data, so every route needs a logged-in librarian."""

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
from library_api.models import Loan, Member
from library_api.schemas import MemberCreate, MemberOut, MemberUpdate, Page

router = APIRouter(prefix="/members", tags=["members"])

EMAIL_TAKEN = "A member with this email already exists"


def _get(session: SessionDep, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("Member", member_id)
    return member


def _email_taken(session: SessionDep, email: str, other_than: int | None = None) -> bool:
    query = select(Member.id).where(Member.email == email)
    if other_than is not None:
        query = query.where(Member.id != other_than)
    return session.scalar(query) is not None


@router.get("", response_model=Page[MemberOut])
def list_members(
    session: SessionDep, _user: LoggedIn, paging: PagingDep, q: str | None = None
) -> dict[str, Any]:
    """List members, oldest first. ``q`` searches name and email."""
    query = select(Member).order_by(Member.id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Member.name.ilike(pattern), Member.email.ilike(pattern)))
    return paging.page(session, query)


@router.get("/{member_id}", response_model=MemberOut)
def get_member(session: SessionDep, _user: LoggedIn, member_id: int) -> Member:
    """Return one member."""
    return _get(session, member_id)


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def create_member(session: SessionDep, _user: LoggedIn, data: MemberCreate) -> Member:
    """Add a member. The email is stored in lower case, and must be new."""
    if _email_taken(session, data.email):
        raise conflict(EMAIL_TAKEN)
    member = Member(**data.model_dump())
    session.add(member)
    commit(session, EMAIL_TAKEN)
    session.refresh(member)
    return member


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(
    session: SessionDep, _user: LoggedIn, member_id: int, data: MemberUpdate
) -> Member:
    """Change the fields that are sent."""
    member = _get(session, member_id)
    changes = data.model_dump(exclude_unset=True)
    if "email" in changes and _email_taken(session, changes["email"], other_than=member_id):
        raise conflict(EMAIL_TAKEN)
    for name, value in changes.items():
        setattr(member, name, value)
    commit(session, EMAIL_TAKEN)
    session.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(session: SessionDep, _user: LoggedIn, member_id: int) -> Response:
    """Delete a member who has never borrowed a book."""
    member = _get(session, member_id)
    has_loans = "This member has loans, so they cannot be deleted"
    if session.scalar(select(Loan.id).where(Loan.member_id == member_id).limit(1)) is not None:
        raise conflict(has_loans)
    session.delete(member)
    commit(session, has_loans)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
