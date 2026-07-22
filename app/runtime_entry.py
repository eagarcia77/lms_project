from __future__ import annotations

"""Entrada estable de producción para NEXUS EDU XR.

Carga la aplicación principal generada por los instaladores y sustituye las rutas
antiguas de Course Studio por las rutas CRUD de Course Builder. Las rutas se
insertan directamente en el enrutador activo para evitar diferencias de
``include_router`` entre las versiones generadas durante Docker build.
"""

from app.course_builder import router as course_builder_router
from app.main import app


COURSE_PREFIXES = ("/course-studio", "/course-builder")


def _is_legacy_course_route(route: object) -> bool:
    path = str(getattr(route, "path", ""))
    return any(path == prefix or path.startswith(prefix + "/") for prefix in COURSE_PREFIXES)


def _route_snapshot(routes: list[object]) -> list[tuple[str, set[str]]]:
    return [
        (
            str(getattr(route, "path", "")),
            set(getattr(route, "methods", set()) or set()),
        )
        for route in routes
    ]


# Guardamos las rutas del constructor antes de modificar la aplicación principal.
builder_routes = list(course_builder_router.routes)
if not builder_routes:
    raise RuntimeError("Course Builder fue importado, pero su APIRouter no contiene rutas.")

# Las rutas se evalúan en orden. Retiramos primero la versión anterior y luego
# añadimos directamente los objetos APIRoute ya construidos por Course Builder.
app.router.routes = [
    route for route in app.router.routes if not _is_legacy_course_route(route)
]
app.router.routes.extend(builder_routes)
app.openapi_schema = None


def _validate_course_routes() -> None:
    routes = _route_snapshot(list(app.router.routes))
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
        available = ", ".join(
            f"{'/'.join(sorted(methods)) or '-'} {path}"
            for path, methods in routes
            if path.startswith(COURSE_PREFIXES)
        ) or "ninguna"
        raise RuntimeError(
            "Faltan rutas obligatorias de Course Builder: "
            + ", ".join(missing)
            + ". Rutas disponibles: "
            + available
        )

    registered = [
        f"{'/'.join(sorted(methods))} {path}"
        for path, methods in routes
        if path.startswith(COURSE_PREFIXES)
    ]
    print("Course Builder registrado: " + " | ".join(registered))


_validate_course_routes()
