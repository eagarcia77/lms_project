from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path("/tmp/nexus-smoke-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "smoke-session-secret-at-least-thirty-two-characters"
os.environ["NEXUS_SESSION_SECRET"] = "smoke-admin-secret-at-least-thirty-two-characters"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "smoke.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Smoke-Password-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Administrador de prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: se esperaba {status} y se recibió {response.status_code}: "
            f"{response.text[:500]}"
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.get("/healthz"), 200, "healthz")
        expect(client.get("/admin/login"), 200, "pantalla de acceso")

        login = client.post(
            "/admin/login",
            data={
                "email": "smoke.admin@example.com",
                "password": "Initial-Smoke-Password-2026!",
            },
        )
        expect(login, 303, "inicio de sesión administrativo")
        if login.headers.get("location") != "/admin/password":
            raise RuntimeError("La cuenta inicial no solicitó el cambio obligatorio de contraseña.")

        password = client.post(
            "/admin/password",
            data={
                "password": "Updated-Smoke-Password-2026!",
                "confirm": "Updated-Smoke-Password-2026!",
            },
        )
        expect(password, 303, "cambio de contraseña")
        expect(client.get("/admin"), 200, "panel administrativo")
        expect(client.get("/admin/system"), 200, "estado del sistema")
        expect(client.get("/admin/system/health"), 200, "salud administrativa")

        course = client.post(
            "/admin/authoring/courses",
            data={
                "course_code": "SMOKE-1001",
                "title": "Curso funcional de prueba",
                "description": "Validación automática de NEXUS EDU XR.",
                "term": "Pruebas 2026",
                "instructor_email": "smoke.admin@example.com",
                "template": "blank",
            },
        )
        expect(course, 303, "creación de curso")
        location = course.headers.get("location", "")
        match = re.fullmatch(r"/admin/authoring/courses/(\d+)", location)
        if not match:
            raise RuntimeError(f"Redirección de curso inesperada: {location}")
        course_id = int(match.group(1))
        expect(client.get(location), 200, "página del curso")

        module = client.post(
            f"/admin/authoring/courses/{course_id}/modules",
            data={
                "title": "Módulo 1: Introducción",
                "description": "Módulo generado por la prueba funcional.",
                "learning_outcomes": "Crear contenido y actividades correctamente.",
                "estimated_minutes": "60",
                "position": "1",
            },
        )
        expect(module, 303, "creación de módulo")

        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1",
                (course_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("El módulo no fue almacenado en la base de datos.")
        module_id = int(row[0])

        content = client.post(
            f"/admin/authoring/modules/{module_id}/content",
            data={
                "title": "Contenido principal",
                "body_html": "<h2>Introducción</h2><p>Contenido guardado correctamente.</p>",
            },
        )
        expect(content, 303, "guardado de contenido")

        assignment = client.post(
            f"/admin/authoring/modules/{module_id}/activities",
            data={
                "item_type": "assignment",
                "title": "Asignación diagnóstica",
                "instructions": "Complete la actividad de prueba.",
                "points": "10",
                "due_at": "",
                "tool_name": "native",
                "external_url": "",
                "embed_url": "",
                "configuration_json": "{}",
            },
        )
        expect(assignment, 303, "creación de asignación")

        discussion = client.post(
            f"/admin/authoring/modules/{module_id}/activities",
            data={
                "item_type": "discussion",
                "title": "Foro de prueba",
                "instructions": "Comparta una reflexión breve.",
                "points": "5",
                "due_at": "",
                "tool_name": "native",
                "external_url": "",
                "embed_url": "",
                "configuration_json": "{}",
            },
        )
        expect(discussion, 303, "creación de foro")

        with sqlite3.connect(DB_PATH) as conn:
            item = conn.execute(
                "SELECT id FROM nexus_content_items WHERE module_id=? AND item_type='discussion' ORDER BY id DESC LIMIT 1",
                (module_id,),
            ).fetchone()
        if not item:
            raise RuntimeError("El foro no fue almacenado.")
        forum_id = int(item[0])
        expect(client.get(f"/admin/authoring/items/{forum_id}/forum"), 200, "apertura del foro")
        expect(
            client.post(
                f"/admin/authoring/items/{forum_id}/forum",
                data={"body": "Aportación de validación automática."},
            ),
            303,
            "publicación en foro",
        )

        module_page = client.get(f"/admin/authoring/modules/{module_id}")
        expect(module_page, 200, "Studio del módulo")
        for expected_text in ("Contenido principal", "Asignación diagnóstica", "Foro de prueba"):
            if expected_text not in module_page.text:
                raise RuntimeError(f"No se encontró {expected_text!r} en el Studio del módulo.")

        odt = client.get(f"/admin/authoring/modules/{module_id}/odf/odt")
        expect(odt, 200, "exportación ODT")
        if not odt.content:
            raise RuntimeError("La exportación ODT está vacía.")

        expect(client.get(f"/admin/authoring/items/{forum_id}/preview"), 200, "vista previa")
        expect(client.get("/admin/logout"), 303, "cierre de sesión")

    print("Prueba funcional completada: acceso, administración, curso, módulo, contenido, evaluación, foro y ODT.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
