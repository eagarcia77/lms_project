from __future__ import annotations

"""Entrada única y determinista de producción para NEXUS EDU XR.

La consola administrativa se registra sobre la aplicación principal. El Studio
unificado, el Centro de Innovación y el Portal Administrativo Integral se
incorporan a la misma aplicación FastAPI y comparten usuarios, permisos,
navegación, datos y diagnóstico.
"""

from fastapi import FastAPI

from app.admin_console import register_admin_console
from app.admin_portal import register_admin_portal
from app.admin_system import register_admin_system
from app.innovation_hub import register_innovation_hub
from app.main import app
from app.unified_authoring import register_unified_authoring

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


def _register_unified_studio() -> None:
    isolated = FastAPI(title="NEXUS Unified Authoring Router")
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
    app.openapi_schema = None


def _validate() -> None:
    snapshot = [
        (_path(route), set(getattr(route, "methods", set()) or set()))
        for route in app.router.routes
    ]
    required = {
        ("/healthz", "GET"),
        ("/course-studio", "GET"),
        ("/admin", "GET"),
        ("/admin/login", "GET"),
        ("/admin/courses", "GET"),
        ("/admin/system", "GET"),
        ("/admin/system/health", "GET"),
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
        if path.startswith(("/course-studio", "/admin/authoring", "/admin/system", "/admin"))
    ]
    print("NEXUS unified routes: " + " | ".join(registered), flush=True)
    if missing:
        raise RuntimeError("Faltan rutas unificadas: " + ", ".join(missing))


_register_administration()
_register_unified_studio()
_register_integrated_portal()
_validate()
