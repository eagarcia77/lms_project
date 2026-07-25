from __future__ import annotations

from app.production_entry import app

REQUIRED = {
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
    ("/admin/audit", "GET"),
    ("/admin/backup", "GET"),
    ("/admin/system", "GET"),
    ("/admin/system/health", "GET"),
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


def main() -> None:
    snapshot = [
        (str(getattr(route, "path", "")), set(getattr(route, "methods", set()) or set()))
        for route in app.routes
    ]
    registered = [
        f"{'/'.join(sorted(methods)) or '-'} {path}"
        for path, methods in snapshot
        if path.startswith(("/api/admin", "/api/platform", "/api/courses", "/admin", "/course-studio"))
    ]
    missing = [
        f"{method} {path}"
        for path, method in sorted(REQUIRED)
        if not any(route_path == path and method in methods for route_path, methods in snapshot)
    ]
    print("Rutas de la plataforma integral registradas:", flush=True)
    for route in registered:
        print(f"  - {route}", flush=True)
    if missing:
        print("Rutas ausentes:", flush=True)
        for route in missing:
            print(f"  - {route}", flush=True)
        raise SystemExit(1)
    print(f"Validación completada: {len(REQUIRED)} rutas integradas disponibles.", flush=True)


if __name__ == "__main__":
    main()
