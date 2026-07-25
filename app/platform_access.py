from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request

from app.admin_console import db, execute, rows, session_user
from app.home_admin_access import ADMIN_ROLES, _session_emails

ACADEMIC_ROLES = {"instructor", "student"}
ROLE_LABELS = {
    "superadmin": "Superadministrador",
    "course_admin": "Administrador académico",
    "user_admin": "Administrador de usuarios",
    "support": "Soporte técnico",
    "auditor": "Auditor",
    "instructor": "Instructor",
    "student": "Estudiante",
}


def _remove_route(app: FastAPI, path: str) -> None:
    app.router.routes = [
        route for route in app.router.routes if str(getattr(route, "path", "")) != path
    ]


def _account_for_request(request: Request) -> dict[str, Any] | None:
    admin = session_user(request)
    if admin:
        return admin

    emails = sorted(_session_emails(dict(request.session)))
    if not emails:
        return None
    placeholders = ",".join("?" for _ in emails)
    with db() as conn:
        found = rows(
            execute(
                conn,
                f"SELECT id,email,full_name,role,active,must_change_password FROM nexus_admin_users "
                f"WHERE active=1 AND LOWER(email) IN ({placeholders}) ORDER BY id LIMIT 1",
                tuple(emails),
            )
        )
    return found[0] if found else None


def _course_roles(email: str) -> list[dict[str, Any]]:
    if not email:
        return []
    with db() as conn:
        return rows(
            execute(
                conn,
                """SELECT e.course_id,e.course_role,e.status,c.course_code,c.title
                FROM nexus_admin_enrollments e
                JOIN nexus_admin_courses c ON c.id=e.course_id
                WHERE LOWER(e.user_email)=? AND e.status='active'
                ORDER BY c.title,c.course_code""",
                (email.strip().lower(),),
            )
        )


def _payload(request: Request) -> dict[str, Any]:
    session_profile = request.session.get("user") or {}
    account = _account_for_request(request)
    email = str((account or {}).get("email") or session_profile.get("email") or "").strip().lower()
    role = str((account or {}).get("role") or "") or None
    memberships = _course_roles(email)
    course_role_names = {str(item.get("course_role") or "") for item in memberships}

    user_profile = dict(session_profile) if isinstance(session_profile, dict) else {}
    if account:
        user_profile.setdefault("email", account.get("email"))
        user_profile.setdefault("name", account.get("full_name"))
        user_profile.setdefault("full_name", account.get("full_name"))

    authenticated = bool(session_profile or session_user(request))
    return {
        "authenticated": authenticated,
        "user": user_profile or None,
        "platformRole": role,
        "platformRoleLabel": ROLE_LABELS.get(role or "", role),
        "isAdmin": role in ADMIN_ROLES,
        "isInstructor": role == "instructor" or bool(
            course_role_names & {"instructor", "teaching_assistant", "course_builder", "facilitator"}
        ),
        "isStudent": role == "student" or "student" in course_role_names,
        "courseRoles": memberships,
    }


def register_platform_access(app: FastAPI) -> None:
    _remove_route(app, "/api/me")
    _remove_route(app, "/api/platform/access")

    @app.get("/api/me", response_model=None)
    async def platform_me(request: Request) -> dict[str, Any]:
        return _payload(request)

    @app.get("/api/platform/access", response_model=None)
    async def platform_access(request: Request) -> dict[str, Any]:
        return _payload(request)

    print("Identidad de Instructor, Estudiante y administradores registrada.", flush=True)
