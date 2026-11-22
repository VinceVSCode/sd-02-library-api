"""Create the books, members, loans and users tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

OPEN_LOAN = sa.text("returned_on IS NULL")


def upgrade() -> None:
    """Create the four tables, their constraints and indexes."""
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("isbn", sa.String(length=13), nullable=False, unique=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("published_year", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "published_year IS NULL OR published_year BETWEEN 1450 AND 2100",
            name="ck_books_published_year",
        ),
    )
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False, unique=True),
        sa.Column("joined_on", sa.Date(), server_default=sa.func.current_date(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("loaned_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.CheckConstraint("due_on >= loaned_on", name="ck_loans_due_after_loan"),
        sa.CheckConstraint(
            "returned_on IS NULL OR returned_on >= loaned_on", name="ck_loans_return_after_loan"
        ),
    )
    op.create_index("ix_loans_member_id", "loans", ["member_id"])
    # A book can have only one loan that is not returned.
    op.create_index(
        "uq_loans_open_book",
        "loans",
        ["book_id"],
        unique=True,
        postgresql_where=OPEN_LOAN,
        sqlite_where=OPEN_LOAN,
    )


def downgrade() -> None:
    """Remove everything that upgrade() created."""
    op.drop_index("uq_loans_open_book", table_name="loans")
    op.drop_index("ix_loans_member_id", table_name="loans")
    op.drop_table("loans")
    op.drop_table("users")
    op.drop_table("members")
    op.drop_table("books")
