"""Password hashing and login tokens.

Passwords are hashed with scrypt from the standard library, each with its own
random salt. Login tokens are JSON Web Tokens signed with HS256 that expire.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

# scrypt cost settings. N=2^14 uses 16 MB and about 0.05 s per login on a laptop.
# OWASP recommends N=2^17 (128 MB) for production; the README lists this as a limitation.
_N, _R, _P = 2**14, 8, 1
_ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a login token is missing, damaged, forged or expired."""


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    """Return a salted scrypt hash, stored as ``scrypt$N$r$p$salt$hash``."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Return True if the password matches the stored hash. Never raises."""
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except ValueError:  # a damaged hash: wrong number of parts, bad base64 or numbers
        return False
    return hmac.compare_digest(actual, expected)


def create_token(username: str, secret: str, minutes: int, now: datetime | None = None) -> str:
    """Return a signed token for this user that expires after ``minutes``."""
    issued = now or datetime.now(UTC)
    claims = {"sub": username, "iat": issued, "exp": issued + timedelta(minutes=minutes)}
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def read_token(token: str, secret: str) -> str:
    """Return the username in a valid token, or raise ``InvalidTokenError``."""
    try:
        claims = jwt.decode(
            token, secret, algorithms=[_ALGORITHM], options={"require": ["sub", "exp"]}
        )
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error
    username = claims["sub"]
    if not isinstance(username, str) or not username:
        raise InvalidTokenError("the token names no user")
    return username
