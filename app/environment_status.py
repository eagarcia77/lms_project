from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI


def _environment() -> str:
    return (os.getenv("APP_ENV") or "development").strip().lower()


def _release_channel() -> str:
    return (os.getenv("RELEASE_CHANNEL") or _environment()).strip().lower()


def _commit_sha() -> str | None:
    value = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    ).strip()
    return value or None


def release_payload() -> dict[str, Any]:
    environment = _environment()
    return {
        "application": os.getenv("APP_NAME", "EAGR Learning XR"),
        "environment": environment,
        "releaseChannel": _release_channel(),
        "commit": _commit_sha(),
        "isProduction": environment == "production",
        "isStaging": environment == "staging",
    }


def register_environment_status(app: FastAPI) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if str(getattr(route, "path", "")) != "/api/release"
    ]

    @app.get("/api/release", response_model=None)
    async def api_release() -> dict[str, Any]:
        return release_payload()

    print("Identidad de entorno y versión registrada en /api/release.", flush=True)
