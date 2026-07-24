from __future__ import annotations

"""Entrada de producción determinista para NEXUS EDU XR.

Esta entrada evita modificar ``app.runtime_entry`` durante la construcción. Carga la
aplicación base y registra explícitamente, en un orden estable, el constructor de
cursos, la consola administrativa y Course Studio V6.
"""

from app.admin_authoring_v6 import register_authoring_v6
from app.admin_console import register_admin_console
from app.course_builder import router as course_builder_router
from app.main import app


COURSE_PREFIXES = ("/course-studio", "/course-builder")


def _path(route: object) -> str:
    return str(getattr(route, "path", ""))


def _remove_routes(prefixes: tuple[str, ...]) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not any(_path(route) == prefix or _path(route).startswith(prefix + "/") for prefix in prefixes)
    ]
    app.openapi_schema = None


def _register_course_builder() -> None:
    routes = list(course_builder_router.routes)
    if not routes:
        raise RuntimeError("El APIRouter de Course Builder no contiene rutas.")
    _remove_routes(COURSE_PREFIXES)
    app.router.routes.extend(routes)
    app.openapi_schema = None


def _register_admin() -> None:
    # app.main no registra la consola administrativa. Se hace aquí una sola vez.
    if not any(_path(route) == "/admin/login" for route in app.router.routes):
        register_admin_console(app)
    # V6 elimina cualquier versión anterior bajo /admin/authoring y registra el
    # conjunto completo de rutas académicas.
    register_authoring_v6(app)


def _validate() -> None:
    snapshot = [
        (_path(route), set(getattr(route, "methods", set()) or set()))
        for route in app.router.routes
    ]
    required = {
        ("/healthz", "GET"),
        ("/course-studio", "GET"),
        ("/course-studio/courses", "POST"),
        ("/course-studio/courses/{course_id}/modules", "POST"),
        ("/course-studio/modules/{module_id}/activities", "POST"),
        ("/admin/login", "GET"),
        ("/admin/courses", "GET"),
        ("/admin/authoring", "GET"),
        ("/admin/authoring/courses", "POST"),
        ("/admin/authoring/courses/{course_id}", "GET"),
        ("/admin/authoring/courses/{course_id}/modules", "POST"),
        ("/admin/authoring/courses/{course_id}/ai-plan", "POST"),
        ("/admin/authoring/modules/{module_id}/items/new", "GET"),
        ("/admin/authoring/modules/{module_id}/items", "POST"),
        ("/admin/authoring/modules/{module_id}/google", "POST"),
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
    print("NEXUS production routes: " + " | ".join(registered), flush=True)
    if missing:
        raise RuntimeError("Faltan rutas de producción: " + ", ".join(missing))


_register_course_builder()
_register_admin()
_validate()
