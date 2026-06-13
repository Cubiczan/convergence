"""Convergence FastAPI application."""
from __future__ import annotations

import os

from cubiczan_resilience.fastapi_helpers import cors_allowlist
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from convergence.api.routes.workstreams import router as workstreams_router


def _allowed_origins() -> list[str]:
    """Explicit CORS origin allowlist sourced from the ALLOWED_ORIGINS env var.

    Comma-separated; defaults to localhost dev origins when unset.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Convergence",
        description="Post-Merger Integration Intelligence Platform - CHP-governed multi-agent Convergence",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        **cors_allowlist(_allowed_origins()),
    )
    app.include_router(workstreams_router)
    return app


app = create_app()


def main():
    import uvicorn
    uvicorn.run("convergence.api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
