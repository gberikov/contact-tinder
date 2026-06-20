"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import accounts, snapshots, working_copies
from src.core.errors import register_error_handlers
from src.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Contact Tinder — Snapshots & Working Copies API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(accounts.router)
    app.include_router(snapshots.router)
    app.include_router(working_copies.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
