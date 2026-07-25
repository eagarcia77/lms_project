from __future__ import annotations

"""Entrada única y determinista de producción para NEXUS EDU XR.

La consola administrativa, la identidad académica, Course Studio, el catálogo
visible en la portada, el Centro de Innovación y el Centro de Calidad comparten
la misma aplicación, base de datos y sistema de permisos.
"""

from fastapi import FastAPI

from app.admin_console import register_admin_console
from app.admin_portal import register_admin_portal
from app.admin_system import register_admin_system
from app.course_management import register_course_management
from app.home_admin_access import register_home_admin_access
from app.innovation_hub import register_innovation_hub
from app.main import app
from app.platform_access import register_platform_access
from app.quality_center import register_quality_center
from app.role_management import register_role_management
from app.unified_authoring import register_unified_authoring
from app.unified_course_catalog import register_unified_course_catalog

AUTHORING_PREFIXES = ("/admin/authoring", "/course-studio", "/course-builder")


def _path(route: object) -> str:
    return str(getattr(route, "path", ""))


def _is_authoring_route(route: object) -> bool:
    path = _path(route)
    return any(path == prefix or path.startswith(prefix + "/") for prefix in AUTHORING_PREFIXES)


def _register_administration() -> None:
    if not any(_path(route) == "/admin/login" for route in app.router.routes):
        register_admin_console(app)
    if not any(_path(route) == "/admin/system" for route in app.router.routes):
        register_admin_system(app)
    register_role_management(app)
    register_home_admin_access(app)
    register_platform_access(app)
    register_quality_center(app)


def _register_unified_studio() -> None:
    isolated = FastAPI(title="NEXUS Unified Authoring Router")
    register_unified_authoring(isolated)
    register_innovation_hub(isolated)
    routes = [route for route in isolated.router.routes if _is_authoring_route(route)]
    if not routes:
        raise RuntimeError("El Studio unificado no produjo rutas para registrar.")

    app.router.routes = [route for route in app.router.routes if not _is_authoring_route(route)]
    app.router.routes.extend(routes)
    register_course_management(app)
    app.openapi_schema = None


def _register_catalog() -> None:
    register_unified_course_catalog(app)
    app.openapi_schema = None


def _register_integrated_portal() -> None:
    register_admin_portal(app)
    app.openapi_schema = None


def _validate() -> None:
    snapshot = [
        (_path(route), set(getattr(route, "methods", set()) or set()))
        for route in app.router.routes
    ]
    required = {
        ("/healthz", "GET"),
        ("/api/me", "GET"),
        ("/api/platform/access", "GET"),
        ("/api/admin/access", "GET"),
        ("/api/dashboard", "GET"),
        ("/api/courses", "GET"),
        ("/api/courses/{course_id}", "GET"),
        ("/api/xr", "GET"),
        ("/course-studio", "GET"),
        ("/admin", "GET"),
        ("/admin/login", "GET"),
        ("/admin/courses", "GET"),
        ("/admin/system", "GET"),
        ("/admin/system/health", "GET"),
        ("/admin/quality", "GET"),
        ("/admin/quality/report.json", "GET"),
        ("/admin/quality/courses/{course_id}", "GET"),
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
        ("/admin/authoring/courses/{course_id}/update", "POST"),
        ("/admin/authoring/courses/{course_id}/modules", "POST"),
        ("/admin/authoring/courses/{course_id}/ai-plan", "POST"),
        ("/admin/authoring/modules/{module_id}", "GET"),
        ("/admin/authoring/modules/{module_id}/update", "POST"),
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
        if path.startswith(("/course-studio", "/api/courses", "/api/platform", "/api/admin", "/admin/authoring", "/admin/system", "/admin/quality", "/admin/users", "/admin/roles", "/admin/enrollments", "/admin"))
    ]
    print("NEXUS unified routes: " + " | ".join(registered), flush=True)
    if missing:
        raise RuntimeError("Faltan rutas unificadas: " + ", ".join(missing))


_register_administration()
_register_unified_studio()
_register_catalog()
_register_integrated_portal()
_validate()
