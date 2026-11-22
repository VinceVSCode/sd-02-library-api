"""Alembic environment: runs the migrations against the configured database."""

from __future__ import annotations

from alembic import context

from library_api.config import get_settings
from library_api.db import make_engine
from library_api.models import Base

config = context.config
url = config.get_main_option("sqlalchemy.url") or get_settings().sqlalchemy_url()


def run_offline() -> None:
    """Write the SQL instead of running it (alembic upgrade --sql)."""
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    """Run the migrations on the database."""
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
