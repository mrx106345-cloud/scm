"""FastAPI application factory. Routers stay thin; logic lives in services/agents."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.items import router as items_router
from app.api.notes import router as notes_router
from app.api.outbox import router as outbox_router
from app.api.recommendations import router as recommendations_router
from app.api.routes import router
from app.api.suppliers import router as suppliers_router
from app.config import settings
from app.logging_setup import configure_logging

configure_logging()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(catalog_router)
    app.include_router(chat_router)
    app.include_router(notes_router)
    app.include_router(recommendations_router)
    app.include_router(outbox_router)
    app.include_router(suppliers_router)
    app.include_router(items_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        # Public minimal endpoint per api-spec A13. No auth, no details.
        return {"status": "ok"}

    return app


app = create_app()
