"""The FastAPI application.

Run it with: uvicorn library_api.app:create_app --factory
The OpenAPI page, where every endpoint can be tried, is at /docs.
"""

from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from library_api import __version__
from library_api.config import Settings, get_settings
from library_api.db import make_engine
from library_api.deps import SessionDep
from library_api.routers import auth, books, loans, members

DESCRIPTION = """
A REST API for a small library. Anyone can read the books; changing data, and
everything about members and loans, needs a librarian's login.

**To try it here:** press **Authorize**, log in with the demo librarian from
`.env` (`DEMO_USERNAME` and `DEMO_PASSWORD`), then call any endpoint.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. The tests pass their own settings (a test database)."""
    settings = settings or get_settings()
    app = FastAPI(title="Library API", version=__version__, description=DESCRIPTION)
    engine = make_engine(settings.sqlalchemy_url())
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker(engine, expire_on_commit=False)

    for module in (auth, books, members, loans):
        app.include_router(module.router)

    @app.get("/", include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/health", tags=["health"])
    def health(session: SessionDep) -> JSONResponse:
        """Report whether the API and its database answer. Used by container probes."""
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                {"status": "error", "database": "unreachable"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return JSONResponse({"status": "ok", "database": "ok"})

    return app

