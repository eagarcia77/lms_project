from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-course-workspace-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "course-workspace-session-secret-at-least-thirty-two"
os.environ["NEXUS_SESSION_SECRET"] = "course-workspace-admin-secret-at-least-thirty-two"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "courses.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Course-Password-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Administración de cursos"

from fastapi.testclient import TestClient  # noqa: E402
from app.admin_console import db, execute, rows  # noqa: E402
from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: se esperaba {status} y se recibió {response.status_code}: {response.text[:600]}"
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        login = client.post(
            "/admin/login",
            data={
                "email": "courses.admin@example.com",
                "password": "Initial-Course-Password-2026!",
            },
        )
        expect(login, 303, "inicio de sesión")
        password = client.post(
            "/admin/password",
            data={
                "password": "Updated-Course-Password-2026!",
                "confirm": "Updated-Course-Password-2026!",
            },
        )
        expect(password, 303, "cambio de contraseña")

        workspace = client.get("/admin/authoring")
        expect(workspace, 200, "espacio de cursos")
        for marker in ("NUVEDRA Course Workspace", "Cursos existentes", "Flujo integrado"):
            if marker not in workspace.text:
                raise RuntimeError(
                    f"El espacio de cursos no mostró {marker!r}. "
                    f"Respuesta recibida: {workspace.text[:800]}"
                )

        create = client.post(
            "/admin/authoring/courses",
            data={
                "course_code": "NUV-1001",
                "title": "Curso integrado NUVEDRA",
                "description": "Curso para validar edición y tecnologías emergentes.",
                "term": "Agosto-Diciembre 2026",
                "instructor_email": "faculty@example.com",
                "template": "blank",
            },
        )
        expect(create, 303, "creación del curso")
        location = create.headers.get("location", "")
        if not location.startswith("/admin/authoring/courses/"):
            raise RuntimeError("La creación del curso no devolvió una ruta válida.")
        course_id = int(location.rsplit("/", 1)[-1])

        course = client.get(location)
        expect(course, 200, "configuración administrativa del curso")
        for marker in (
            "Editar configuración del curso",
            "Editar contenido del curso",
            "Abrir editor del profesor",
            "Administrar matrículas",
        ):
            if marker not in course.text:
                raise RuntimeError(
                    f"La configuración editable del curso no mostró {marker!r}. "
                    f"Respuesta recibida: {course.text[:1200]}"
                )

        update_course = client.post(
            f"/admin/authoring/courses/{course_id}/update",
            data={
                "course_code": "NUV-1001",
                "title": "Curso integrado NUVEDRA actualizado",
                "description": "Contenido actualizado.",
                "term": "Agosto-Diciembre 2026",
                "instructor_email": "faculty@example.com",
                "start_date": "2026-08-10",
                "end_date": "2026-12-18",
                "status": "active",
            },
        )
        expect(update_course, 303, "actualización del curso")

        create_module = client.post(
            f"/admin/authoring/courses/{course_id}/modules",
            data={
                "title": "Módulo de innovación",
                "description": "Google Workspace, H5P y WebXR.",
                "learning_outcomes": "Crear una experiencia digital accesible.",
                "estimated_minutes": "90",
                "position": "1",
            },
        )
        expect(create_module, 303, "creación técnica del módulo")
        with db() as conn:
            module_rows = rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))
        if not module_rows:
            raise RuntimeError("El módulo no se guardó.")
        module_id = int(module_rows[0]["id"])

        edit_module = client.get(f"/admin/authoring/modules/{module_id}/edit")
        expect(edit_module, 200, "pantalla de edición del módulo")
        update_module = client.post(
            f"/admin/authoring/modules/{module_id}/edit",
            data={
                "title": "Módulo de innovación actualizado",
                "description": "Experiencias digitales y emergentes.",
                "learning_outcomes": "Diseñar y evaluar una experiencia accesible.",
                "estimated_minutes": "120",
                "position": "1",
                "status": "published",
            },
        )
        expect(update_module, 303, "actualización del módulo")

        google_hub = client.get(f"/admin/authoring/courses/{course_id}/google-hub")
        expect(google_hub, 200, "Google Hub")
        for marker in ("Crear recurso Google", "Google Drive", "Google Classroom"):
            if marker not in google_hub.text:
                raise RuntimeError(f"Google Hub no mostró {marker!r}.")

        emerging = client.get(f"/admin/authoring/courses/{course_id}/emerging")
        expect(emerging, 200, "centro de tecnologías emergentes")
        for marker in ("Añadir experiencia", "H5P/Lumi", "Realidad aumentada"):
            if marker not in emerging.text:
                raise RuntimeError(f"El centro de tecnologías emergentes no mostró {marker!r}.")

        add_emerging = client.post(
            f"/admin/authoring/courses/{course_id}/emerging/add",
            data={
                "module_id": str(module_id),
                "item_type": "simulation",
                "title": "Simulación accesible",
                "instructions": "Explore la simulación y documente sus decisiones.",
                "tool_name": "phet",
                "external_url": "https://phet.colorado.edu/",
                "embed_url": "",
                "accessible_alternative": "Utilice la descripción textual y el conjunto de datos alterno.",
            },
        )
        expect(add_emerging, 303, "incorporación de tecnología emergente")

        with db() as conn:
            item_rows = rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=?", (module_id,)))
        if not item_rows:
            raise RuntimeError("La experiencia emergente no se guardó.")
        item_id = int(item_rows[0]["id"])

        item_page = client.get(f"/admin/authoring/items/{item_id}/edit")
        expect(item_page, 200, "edición del contenido")
        update_item = client.post(
            f"/admin/authoring/items/{item_id}/edit",
            data={
                "item_type": "simulation",
                "title": "Simulación accesible actualizada",
                "body_html": "<h2>Actividad</h2><p>Complete la experiencia.</p>",
                "external_url": "https://phet.colorado.edu/",
                "embed_url": "",
                "metadata_json": '{"tool":"phet","accessible":true}',
                "points": "20",
                "due_at": "",
                "position": "1",
                "status": "published",
            },
        )
        expect(update_item, 303, "actualización del contenido")

    print(
        "Course Workspace validado: configuración editable, contenido, Google Hub y tecnologías emergentes.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
