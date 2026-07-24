from __future__ import annotations

"""Entrada única de producción para NEXUS EDU XR.

Carga la aplicación base y registra una sola experiencia de autoría:
NEXUS Unified Course Studio. Las rutas antiguas de Course Builder y
Course Studio se eliminan dentro del registrador unificado.
"""

from app.admin_console import register_admin_console
from app.main import app
from app.unified_authoring import register_unified_authoring


def _path(route: object) -> str:
    return str(getattr(route, "path", ""))


def _register() -> None:
    if not any(_path(route) == "/admin/login" for route in app.router.routes):
        register_admin_console(app)
    register_unified_authoring(app)
    app.openapi_schema = None


def _validate() -> None:
    snapshot = [
        (_path(route), set(getattr(route, "methods", set()) or set()))
        for route in app.router.routes
    ]
    required = {
        ("/healthz", "GET"),
        ("/course-studio", "GET"),
        ("/admin/login", "GET"),
        ("/admin/courses", "GET"),
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
    }
    missing = [
        f"{method} {path}"
        for path, method in sorted(required)
        if not any(route_path == path and method in methods for route_path, methods in snapshot)
    ]
    registered = [
        f"{'/'.join(sorted(methods)) or '-'} {path}"
        for path, methods in snapshot
        if path.startswith(("/course-studio", "/admin"))
    ]
    print("NEXUS unified routes: " + " | ".join(registered), flush=True)
    if missing:
        raise RuntimeError("Faltan rutas unificadas: " + ", ".join(missing))


_register()
_validate()
