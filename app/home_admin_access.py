from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request

from app.admin_console import db, execute, rows, session_user

ADMIN_ROLES = {"superadmin", "course_admin", "user_admin", "support", "auditor"}


def _active_admin_for_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    if not normalized:
        return None
    with db() as conn:
        found = rows(
            execute(
                conn,
                "SELECT id,email,full_name,role,active FROM nexus_admin_users WHERE email=? AND active=1",
                (normalized,),
            )
        )
    if not found or str(found[0].get("role") or "") not in ADMIN_ROLES:
        return None
    return found[0]


def register_home_admin_access(app: FastAPI) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if str(getattr(route, "path", "")) != "/api/admin/access"
    ]

    @app.get("/api/admin/access", response_model=None)
    async def home_admin_access(request: Request) -> dict[str, Any]:
        admin = session_user(request)
        if admin and str(admin.get("role") or "") in ADMIN_ROLES:
            return {
                "allowed": True,
                "authenticatedAdmin": True,
                "requiresAdminLogin": False,
                "role": admin.get("role"),
                "name": admin.get("full_name"),
                "href": "/admin",
            }

        google_user = request.session.get("user") or {}
        google_email = str(google_user.get("email") or "").strip().lower()
        matched = _active_admin_for_email(google_email) if google_email else None
        if matched:
            return {
                "allowed": True,
                "authenticatedAdmin": False,
                "requiresAdminLogin": True,
                "role": matched.get("role"),
                "name": matched.get("full_name"),
                "href": "/admin/login",
            }

        return {
            "allowed": False,
            "authenticatedAdmin": False,
            "requiresAdminLogin": False,
            "role": None,
            "name": None,
            "href": None,
        }

    print("Acceso administrativo condicional de la página principal registrado.", flush=True)
