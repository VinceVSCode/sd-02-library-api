"""Unit tests: password hashing, tokens, and the ISBN and email rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from library_api.schemas import normalise_email, normalise_isbn
from library_api.security import (
    InvalidTokenError,
    create_token,
    hash_password,
    read_token,
    verify_password,
)

SECRET = "x" * 40

# --- passwords -----------------------------------------------------------------


def test_a_password_matches_its_hash_and_nothing_else() -> None:
    stored = hash_password("secret one")
    assert stored.startswith("scrypt$")
    assert verify_password("secret one", stored)
    assert not verify_password("secret two", stored)
    assert not verify_password("", stored)


def test_the_same_password_gets_a_different_salt_each_time() -> None:
    assert hash_password("same") != hash_password("same")


@pytest.mark.parametrize(
    "damaged", ["", "plain", "scrypt$1$2$3", "bcrypt$a$b$c$d$e", "scrypt$x$8$1$AA==$AA=="]
)
def test_a_damaged_hash_never_matches_and_never_raises(damaged: str) -> None:
    assert not verify_password("anything", damaged)


# --- tokens --------------------------------------------------------------------


def test_a_token_names_its_user() -> None:
    assert read_token(create_token("librarian", SECRET, 30), SECRET) == "librarian"


def test_an_expired_token_is_refused() -> None:
    old = datetime.now(UTC) - timedelta(hours=2)
    with pytest.raises(InvalidTokenError, match="expired"):
        read_token(create_token("librarian", SECRET, 30, now=old), SECRET)


def test_a_token_signed_with_another_secret_is_refused() -> None:
    with pytest.raises(InvalidTokenError):
        read_token(create_token("librarian", "y" * 40, 30), SECRET)


def test_an_unsigned_token_is_refused() -> None:
    claims = {"sub": "librarian", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    unsigned = jwt.encode(claims, None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        read_token(unsigned, SECRET)


@pytest.mark.parametrize(
    "claims",
    [{"exp": 9_999_999_999}, {"sub": "librarian"}, {"sub": "", "exp": 9_999_999_999}],
)
def test_a_token_without_a_user_or_an_expiry_is_refused(claims: dict) -> None:
    with pytest.raises(InvalidTokenError):
        read_token(jwt.encode(claims, SECRET, algorithm="HS256"), SECRET)


def test_garbage_is_refused() -> None:
    with pytest.raises(InvalidTokenError):
        read_token("not.a.token", SECRET)


# --- ISBN and email ------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("9780306406157", "9780306406157"),
        ("978-0-306-40615-7", "9780306406157"),
        ("0-306-40615-2", "9780306406157"),  # ISBN-10 is converted
        ("080442957X", "9780804429573"),  # X as the ISBN-10 check digit
        ("080442957x", "9780804429573"),
    ],
)
def test_valid_isbns_are_stored_as_13_digits(given: str, stored: str) -> None:
    assert normalise_isbn(given) == stored


@pytest.mark.parametrize(
    ("given", "reason"),
    [
        ("9780306406158", "ISBN-13 check digit"),
        ("0306406153", "ISBN-10 check digit"),
        ("12345", "10 or 13 digits"),
        ("97803064061X7", "10 or 13 digits"),
        ("", "10 or 13 digits"),
    ],
)
def test_invalid_isbns_are_refused(given: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        normalise_isbn(given)


def test_emails_are_trimmed_and_lower_case() -> None:
    assert normalise_email("  Maria@Example.COM ") == "maria@example.com"


@pytest.mark.parametrize("bad", ["maria", "maria@", "@example.com", "a b@example.com", "a@b"])
def test_invalid_emails_are_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="email"):
        normalise_email(bad)
