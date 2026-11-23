"""Logging in: a username and password are exchanged for a token."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from library_api.deps import SessionDep, SettingsDep
from library_api.models import User
from library_api.schemas import Token, has_control_characters
from library_api.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Checked when the username does not exist, so that an unknown user takes as long
# as a wrong password and the answer time does not reveal which usernames exist.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/token", response_model=Token)
def log_in(
    session: SessionDep,
    settings: SettingsDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Return a token for a librarian. Send it as ``Authorization: Bearer <token>``."""
    # A control character (such as NUL) cannot be in a username, and PostgreSQL
    # would refuse to look it up, so such a name is treated as unknown.
    user = None
    if not has_control_characters(form.username):
        user = session.scalar(select(User).where(User.username == form.username))
    password_ok = verify_password(form.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_token(user.username, settings.jwt_secret, settings.token_minutes)
    return Token(access_token=token, expires_in=settings.token_minutes * 60)
