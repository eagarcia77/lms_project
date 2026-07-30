from __future__ import annotations

"""Entrada única y determinista de producción para NUVEDRA.

La consola administrativa, la gestión de roles, el Studio unificado, el Centro
de Innovación, la administración de la portada y el Portal Administrativo
Integral se incorporan a la misma aplicación FastAPI.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.admin_console import register_admin_console
from app.admin_portal import register_admin_portal
from app.admin_system import register_admin_system
from app.home_content import register_home_content
from app.innovation_hub import register_innovation_hub
from app.main import app
from app.role_management import register_role_management
from app.unified_authoring import register_unified_authoring

AUTHORING_PREFIXES = ("/admin/authoring", "/course-studio", "/course-builder")
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _path(route: object) -> str:
    return str(getattr(route, "path", ""))


def _methods(route: object) -> set[str]:
    return set(getattr(route, "methods", set()) or set())


def _is_authoring_route(route: object) -> bool:
    path = _path(route)
    return any(path == prefix or path.startswith(prefix + "/") for prefix in AUTHORING_PREFIXES)


def _remove_get_route(path: str) -> None:
    """Replace only the public GET route while preserving POST authentication."""
    app.router.routes = [
        route
        for route in app.router.routes
        if not (_path(route) == path and "GET" in _methods(route))
    ]


def _register_administration() -> None:
    if not any(_path(route) == "/admin/login" for route in app.router.routes):
        register_admin_console(app)
    if not any(_path(route) == "/admin/system" for route in app.router.routes):
        register_admin_system(app)
    register_role_management(app)


def _register_unified_studio() -> None:
    isolated = FastAPI(title="NUVEDRA Unified Authoring Router")
    register_unified_authoring(isolated)
    register_innovation_hub(isolated)
    routes = [route for route in isolated.router.routes if _is_authoring_route(route)]
    if not routes:
        raise RuntimeError("El Studio unificado no produjo rutas para registrar.")

    app.router.routes = [route for route in app.router.routes if not _is_authoring_route(route)]
    app.router.routes.extend(routes)
    app.openapi_schema = None


def _register_integrated_portal() -> None:
    register_admin_portal(app)
    register_home_content(app)
    app.openapi_schema = None


def _register_public_login() -> None:
    """Use the production NUVEDRA homepage for the unauthenticated login view."""
    _remove_get_route("/login")

    @app.get("/login", include_in_schema=False, response_class=FileResponse)
    async def nuvedra_login() -> FileResponse:
        page = STATIC_DIR / "index.html"
        if not page.is_file():
            raise RuntimeError("No se encontró la página principal de NUVEDRA.")
        return FileResponse(page, media_type="text/html; charset=utf-8")

    app.openapi_schema = None


def _validate() -> None:
    snapshot = [
        (_path(route), _methods(route))
        for route in app.router.routes
    ]
    required = {
        ("/healthz", "GET"),
        ("/login", "GET"),
        ("/api/home-content", "GET"),
        ("/course-studio", "GET"),
        ("/admin", "GET"),
        ("/admin/login", "GET"),
        ("/admin/home-content", "GET"),
        ("/admin/home-content/save", "POST"),
        ("/admin/home-content/{item_id}/toggle", "POST"),
        ("/admin/home-content/{item_id}/delete", "POST"),
        ("/admin/courses", "GET"),
        ("/admin/system", "GET"),
        ("/admin/system/health", "GET"),
        ("/admin/roles", "GET"),
        ("/admin/users", "GET"),
        ("/admin/users", "POST"),
        ("/admin/users/{user_id}/role", "POST"),
        ("/admin/users/{user_id}/status", "POST"),
        ("/admin/users/{user_id}/force-password-reset", "POST"),
        ("/admin/enrollments", "GET"),
        ("/admin/enrollments", "POST"),
        ("/admin/enrollments/{enrollment_id}/role", "POST"),
        ("/admin/enrollments/{enrollment_id}/status", "POST"),
        ("/admin/enrollments/{enrollment_id}/delete", "POST"),
        ("/admin/authoring", "GET"),
        ("/admin/authoring/courses", "POST"),
        ("/admin/authoring/courses/{course_id}", "GET"),
        ("/admin/authoring/courses/{course_id}/modules", "POST"),
        ("/admin/authoring/courses/{course_id}/ai-plan", "POST"),
        ("/admin/authoring/modules/{module_id}", "GET"),
        ("/admin/authoring/modules/{module_id}/autosave", "POST"),
        ("/admin/authoring/modules/{module_id}/content", "POST"),
        ("/admin/authoring/modules/{module_id}/resources", "POST"),
        ("/admin/authoring/modules/{module_id}/activities", "POST"),
        ("/admin/authoring/modules/{module_id}/google", "POST"),
        ("/admin/authoring/modules/{module_id}/drive", "GET"),
        ("/admin/authoring/modules/{module_id}/drive-link", "POST"),
        ("/admin/authoring/modules/{module_id}/odf/{kind}", "GET"),
        ("/admin/authoring/items/{item_id}/forum", "GET"),
        ("/admin/authoring/items/{item_id}/forum", "POST"),
        ("/admin/authoring/items/{item_id}/preview", "GET"),
        ("/admin/authoring/innovation", "GET"),
        ("/admin/authoring/innovation/courses/{course_id}", "GET"),
        ("/admin/authoring/innovation/modules/{module_id}", "GET"),
        ("/admin/authoring/innovation/modules/{module_id}/ai", "POST"),
        ("/admin/authoring/innovation/modules/{module_id}/xr", "POST"),
        ("/admin/authoring/innovation/modules/{module_id}/tool", "POST"),
        ("/admin/authoring/innovation/courses/{course_id}/publish", "POST"),
        ("/admin/authoring/innovation/courses/{course_id}/duplicate", "POST"),
        ("/admin/authoring/innovation/courses/{course_id}/export", "GET"),
    }
    missing = [
        f"{method} {path}"
        for path, method in sorted(required)
        if not any(route_path == path and method in methods for route_path, methods in snapshot)
    ]
    registered = [
        f"{'/'.join(sorted(methods)) or '-'} {path}"
        for path, methods in snapshot
        if path.startswith((
            "/login",
            "/course-studio",
            "/admin/authoring",
            "/admin/system",
            "/admin/users",
            "/admin/roles",
            "/admin/enrollments",
            "/admin/home-content",
            "/admin",
        ))
    ]
    print("NUVEDRA unified routes: " + " | ".join(registered), flush=True)
    if missing:
        raise RuntimeError("Faltan rutas unificadas: " + ", ".join(missing))


_register_administration()
_register_unified_studio()
_register_integrated_portal()
_register_public_login()
_validate()
