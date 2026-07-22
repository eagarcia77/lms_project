from __future__ import annotations

"""Entrada estable de producción para NEXUS EDU XR.

Carga la aplicación principal generada por los instaladores y registra Course
Builder al final, después de retirar las rutas antiguas de Course Studio. Esto
evita depender de modificaciones textuales a ``app.main`` durante Docker build.
"""

from app.course_builder import router as course_builder_router
from app.main import app


COURSE_PREFIXES = ("/course-studio", "/course-builder")


def _is_legacy_course_route(route: object) -> bool:
    path = str(getattr(route, "path", ""))
    return any(path == prefix or path.startswith(prefix + "/") for prefix in COURSE_PREFIXES)


# Las rutas se evalúan en orden. Retiramos primero la versión anterior para que
# los formularios CRUD sean los que atiendan todas las solicitudes del estudio.
app.router.routes = [route for route in app.router.routes if not _is_legacy_course_route(route)]
app.include_router(course_builder_router)


def _validate_course_routes() -> None:
    routes = [
        (str(getattr(route, "path", "")), set(getattr(route, "methods", set()) or set()))
        for route in app.routes
    ]
    required = {
        ("/course-studio", "GET"),
        ("/course-studio/courses", "POST"),
        ("/course-studio/courses/{course_id}", "GET"),
        ("/course-studio/courses/{course_id}/modules", "POST"),
        ("/course-studio/modules/{module_id}/activities", "POST"),
    }
    missing = [
        f"{method} {path}"
        for path, method in sorted(required)
        if not any(route_path == path and method in methods for route_path, methods in routes)
    ]
    if missing:
        raise RuntimeError("Faltan rutas obligatorias de Course Builder: " + ", ".join(missing))


_validate_course_routes()
