"""Apply the database migrations. The Docker container runs this before the API starts.

Usage: python -m library_api.migrate
"""

from __future__ import annotations

from library_api.config import get_settings
from library_api.db import migrate

if __name__ == "__main__":
    migrate(get_settings().sqlalchemy_url())
    print("Database is up to date.")
