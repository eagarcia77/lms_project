from __future__ import annotations

from app.production_entry import app

REQUIRED = {
    ("/healthz", "GET"),
    ("/course-studio", "GET"),
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
}


def main() -> None:
    snapshot = [
        (
            str(getattr(route, "path", "")),
            set(getattr(route, "methods", set()) or set()),
        )
        for route in app.routes
    ]
    registered = [
        f"{'/'.join(sorted(methods)) or '-'} {path}"
        for path, methods in snapshot
        if path.startswith(("/admin/authoring", "/admin/system", "/course-studio"))
    ]
    missing = [
        f"{method} {path}"
        for path, method in sorted(REQUIRED)
        if not any(route_path == path and method in methods for route_path, methods in snapshot)
    ]
    print("Rutas unificadas registradas:", flush=True)
    for route in registered:
        print(f"  - {route}", flush=True)
    if missing:
        print("Rutas ausentes:", flush=True)
        for route in missing:
            print(f"  - {route}", flush=True)
        raise SystemExit(1)
    print(f"Validación completada: {len(REQUIRED)} rutas obligatorias disponibles.", flush=True)


if __name__ == "__main__":
    main()
