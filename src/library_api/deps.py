"""Shared pieces of the routes: the database session, login, paging and errors."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Path, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from library_api.config import Settings
from library_api.models import User
from library_api.schemas import MAX_ID, SearchText
from library_api.security import InvalidTokenError, read_token

_bearer = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    """Give each request its own database session, closed when the request ends."""
    with request.app.state.sessionmaker() as session:
        yield session


def get_settings(request: Request) -> Settings:
    """Return the settings the app was created with."""
    return request.app.state.settings


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def current_user(
    session: SessionDep, settings: SettingsDep, token: str | None = Depends(_bearer)
) -> User:
    """Return the logged-in librarian, or answer 401 if the token is missing or invalid."""
    if token is None:
        raise _unauthorized("Log in first: send 'Authorization: Bearer <token>'")
    try:
        username = read_token(token, settings.jwt_secret)
    except InvalidTokenError as error:
        raise _unauthorized("The token is invalid or has expired") from error
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        raise _unauthorized("The token's user no longer exists")
    return user


LoggedIn = Annotated[User, Depends(current_user)]


class Paging:
    """``limit`` and ``offset`` query parameters, shared by every list."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
        offset: Annotated[int, Query(ge=0, le=MAX_ID, description="Items to skip.")] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset

    def page(self, session: Session, query: Select[Any]) -> dict[str, Any]:
        """Run the query for one page, and count every match."""
        total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        items = session.scalars(query.limit(self.limit).offset(self.offset)).all()
        return {"items": items, "total": total, "limit": self.limit, "offset": self.offset}


PagingDep = Annotated[Paging, Depends()]

# An id in the address (for example /books/{book_id}) or in a filter. Ids out of
# range are refused with 422 before they reach the database.
PathId = Annotated[int, Path(ge=1, le=MAX_ID)]
FilterId = Annotated[int | None, Query(ge=1, le=MAX_ID)]
# Search text: at most 200 characters, no control characters. It is matched as
# plain text: % and _ have no special meaning.
Search = Annotated[SearchText | None, Query(description="Text to look for (plain text).")]


def not_found(kind: str, item_id: int) -> HTTPException:
    """Return a 404 answer that names what was not found."""
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{kind} {item_id} does not exist")


def conflict(detail: str) -> HTTPException:
    """Return a 409 answer: the request is valid, but clashes with the data."""
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def commit(session: Session, clash: str) -> None:
    """Commit, or answer 409 with ``clash`` if a database rule refuses the change.

    The routes check the rules first to give precise messages. This catches the
    case where another request changed the data in between.
    """
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise conflict(clash) from error
