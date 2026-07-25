from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request

from app.admin_console import db, execute, rows, session_user

ADMIN_ROLES = {"superadmin", "course_admin", "user_admin", "support", "auditor"}
EMAIL_KEYS = {
    "email",
    "mail",
    "preferred_username",
    "userprincipalname",
    "username",
    "login",
}


def _active_admin_for_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        return None
    with db() as conn:
        found = rows(
            execute(
                conn,
                "SELECT id,email,full_name,role,active FROM nexus_admin_users "
                "WHERE LOWER(email)=? AND active=1",
                (normalized,),
            )
        )
    if not found or str(found[0].get("role") or "") not in ADMIN_ROLES:
        return None
    return found[0]


def _session_emails(value: Any, *, depth: int = 0) -> set[str]:
    if depth > 4:
        return set()
    emails: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in EMAIL_KEYS and isinstance(nested, str):
                candidate = nested.strip().lower()
                if "@" in candidate:
                    emails.add(candidate)
            elif isinstance(nested, (Mapping, list, tuple)):
                emails.update(_session_emails(nested, depth=depth + 1))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            emails.update(_session_emails(nested, depth=depth + 1))
    return emails


def _matched_platform_admin(request: Request) -> dict[str, Any] | None:
    try:
        session = dict(request.session)
    except Exception:
        return None
    for email in sorted(_session_emails(session)):
        matched = _active_admin_for_email(email)
        if matched:
            return matched
    return None


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
                "source": "admin_session",
            }

        matched = _matched_platform_admin(request)
        if matched:
            return {
                "allowed": True,
                "authenticatedAdmin": False,
                "requiresAdminLogin": True,
                "role": matched.get("role"),
                "name": matched.get("full_name"),
                "href": "/admin/login",
                "source": "platform_session",
            }

        return {
            "allowed": False,
            "authenticatedAdmin": False,
            "requiresAdminLogin": False,
            "role": None,
            "name": None,
            "href": None,
            "source": None,
        }

    print("Acceso Administrador seguro registrado en la portada.", flush=True)
