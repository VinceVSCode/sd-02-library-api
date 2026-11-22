"""Settings, read from environment variables (or a .env file) in one place."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting of the API. Missing or invalid values stop the start-up with a clear error."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # A full SQLAlchemy URL. When it is not set, it is built from the POSTGRES_* values.
    database_url: str | None = None
    postgres_user: str = "library"
    postgres_password: str = ""
    postgres_db: str = "library"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    jwt_secret: str = Field(min_length=32)
    token_minutes: int = Field(default=30, ge=1, le=24 * 60)

    def sqlalchemy_url(self) -> str:
        """Return the database URL the API connects to."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
