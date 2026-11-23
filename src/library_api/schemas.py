"""The shapes of requests and responses, with their validation rules.

A request that breaks a rule gets a 422 answer that names the field.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, ClassVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# The largest id PostgreSQL's "integer" column holds. Larger ids, and offsets
# beyond it, are refused with 422 instead of reaching the database.
MAX_ID = 2_147_483_647

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def has_control_characters(value: str) -> bool:
    """Return True if the text holds an invisible control character (such as NUL or a tab)."""
    return any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value)


def refuse_control_characters(value: str) -> str:
    """Return the text, or raise ``ValueError`` if it holds a control character.

    PostgreSQL refuses the NUL character outright, and the others have no place
    in a title, a name or a search.
    """
    if has_control_characters(value):
        raise ValueError("control characters (such as NUL or a tab) are not allowed")
    return value


Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(refuse_control_characters),
]
SearchText = Annotated[
    str, StringConstraints(max_length=200), AfterValidator(refuse_control_characters)
]
Id = Annotated[int, Field(ge=1, le=MAX_ID)]


def isbn13_check_digit(first_twelve: str) -> str:
    """Return the check digit for the first 12 digits of an ISBN-13."""
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(first_twelve))
    return str((10 - total % 10) % 10)


def normalise_isbn(value: str) -> str:
    """Return the ISBN as 13 digits. Accepts ISBN-10 or ISBN-13, with or without hyphens.

    Raises ``ValueError`` if the length or the check digit is wrong.
    """
    digits = value.replace("-", "").replace(" ", "").upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", digits):
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(digits))
        if total % 11:
            raise ValueError("the ISBN-10 check digit is wrong")
        first_twelve = "978" + digits[:9]
        return first_twelve + isbn13_check_digit(first_twelve)
    if re.fullmatch(r"[0-9]{13}", digits):
        if isbn13_check_digit(digits[:12]) != digits[12]:
            raise ValueError("the ISBN-13 check digit is wrong")
        return digits
    raise ValueError("an ISBN has 10 or 13 digits (the last digit of an ISBN-10 may be X)")


def normalise_email(value: str) -> str:
    """Return the email address trimmed and in lower case, after a basic shape check."""
    value = value.strip().lower()
    if len(value) > 254 or has_control_characters(value) or not _EMAIL.fullmatch(value):
        raise ValueError("not a valid email address")
    return value


Isbn = Annotated[str, AfterValidator(normalise_isbn)]
Email = Annotated[str, AfterValidator(normalise_email)]
Year = Annotated[int, Field(ge=1450, le=2100)]


class Strict(BaseModel):
    """Refuses fields it does not know, so a typo is reported instead of ignored."""

    model_config = ConfigDict(extra="forbid")


class Patch(Strict):
    """A partial update: fields that are left out stay as they are.

    ``REQUIRED`` lists the fields that may be left out but not set to null.
    """

    REQUIRED: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _no_null_for_required(self) -> Patch:
        for name in self.REQUIRED:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


# --- books ---------------------------------------------------------------------


class BookCreate(Strict):
    isbn: Isbn = Field(examples=["978-0-13-468599-1"])
    title: Text = Field(examples=["The Pragmatic Programmer"])
    author: Text = Field(examples=["David Thomas, Andrew Hunt"])
    published_year: Year | None = Field(default=None, examples=[2019])


class BookUpdate(Patch):
    """Only the fields that are sent are changed."""

    REQUIRED = ("isbn", "title", "author")

    isbn: Isbn | None = None
    title: Text | None = None
    author: Text | None = None
    published_year: Year | None = None


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    isbn: str
    title: str
    author: str
    published_year: int | None
    available: bool


# --- members -------------------------------------------------------------------


class MemberCreate(Strict):
    name: Text = Field(examples=["Maria Papadopoulou"])
    email: Email = Field(examples=["maria@example.com"])


class MemberUpdate(Patch):
    REQUIRED = ("name", "email")

    name: Text | None = None
    email: Email | None = None


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    joined_on: date


# --- loans ---------------------------------------------------------------------


class LoanCreate(Strict):
    book_id: Id
    member_id: Id
    days: int = Field(default=14, ge=1, le=60, description="Days until the book is due.")


class LoanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    member_id: int
    loaned_on: date
    due_on: date
    returned_on: date | None
    overdue: bool


# --- shared --------------------------------------------------------------------


class Page[T](BaseModel):
    """One page of a list. ``total`` counts every match, not just this page."""

    items: list[T]
    total: int
    limit: int
    offset: int


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires.")
