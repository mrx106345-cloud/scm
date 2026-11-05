"""FastAPI application factory. Routers stay thin; logic lives in services/agents."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from app.api.actions import router as actions_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.connectors import router as connectors_router
from app.api.items import router as items_router
from app.api.notes import router as notes_router
from app.api.outbox import router as outbox_router
from app.api.recommendations import router as recommendations_router
from app.api.routes import router
from app.api.suppliers import router as suppliers_router
from app.config import settings
from app.core.dependencies import verify_csrf
from app.logging_setup import configure_logging

configure_logging()

# CSRF header required on every state-changing request (GET/HEAD/OPTIONS skip
# inside the dependency itself). Cross-site requests cannot attach custom
# headers without a preflight, and the session cookie is SameSite=Strict.
_CSRF = [Depends(verify_csrf)]


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(auth_router, dependencies=_CSRF)
    app.include_router(router, dependencies=_CSRF)
    app.include_router(catalog_router, dependencies=_CSRF)
    app.include_router(chat_router, dependencies=_CSRF)
    app.include_router(notes_router, dependencies=_CSRF)
    app.include_router(recommendations_router, dependencies=_CSRF)
    app.include_router(outbox_router, dependencies=_CSRF)
    app.include_router(suppliers_router, dependencies=_CSRF)
    app.include_router(items_router, dependencies=_CSRF)
    app.include_router(connectors_router, dependencies=_CSRF)
    app.include_router(actions_router, dependencies=_CSRF)
    app.include_router(admin_router, dependencies=_CSRF)

    @app.get("/health")
    def health() -> dict[str, str]:
        # Public minimal endpoint per api-spec A13. No auth, no details.
        return {"status": "ok"}

    return app


app = create_app()
