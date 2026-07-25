from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path("/tmp/nexus-quality-smoke.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "quality-session-secret-at-least-thirty-two-characters"
os.environ["NEXUS_SESSION_SECRET"] = "quality-admin-secret-at-least-thirty-two-characters"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "quality.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Quality-Password-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Administrador de calidad"

from fastapi.testclient import TestClient  # noqa: E402

from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: se esperaba {status} y se recibió {response.status_code}: {response.text[:500]}"
        )


def course_report(client: TestClient, course_id: int) -> dict:
    response = client.get("/admin/quality/report.json")
    expect(response, 200, "informe de calidad")
    report = response.json()
    if report.get("format") != "NEXUS-QUALITY-1.0":
        raise RuntimeError("El informe de calidad no tiene el formato esperado.")
    found = next((course for course in report.get("courses", []) if course.get("course_id") == course_id), None)
    if not found:
        raise RuntimeError("El curso de prueba no apareció en el informe de calidad.")
    return found


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(
            client.post(
                "/admin/login",
                data={"email": "quality.admin@example.com", "password": "Initial-Quality-Password-2026!"},
            ),
            303,
            "inicio administrativo",
        )
        expect(
            client.post(
                "/admin/password",
                data={"password": "Updated-Quality-Password-2026!", "confirm": "Updated-Quality-Password-2026!"},
            ),
            303,
            "cambio de contraseña",
        )

        dashboard = client.get("/admin")
        expect(dashboard, 200, "panel administrativo")
        if "/admin/quality" not in dashboard.text or "Calidad académica" not in dashboard.text:
            raise RuntimeError("El Centro de Calidad no aparece en el portal administrativo.")

        created = client.post(
            "/admin/authoring/courses",
            data={
                "course_code": "QUAL-1001",
                "title": "Curso de validación de calidad",
                "description": "Curso creado para comprobar la mejora continua.",
                "term": "Pruebas 2026",
                "instructor_email": "quality.admin@example.com",
                "template": "blank",
            },
        )
        expect(created, 303, "creación del curso")
        match = re.fullmatch(r"/admin/authoring/courses/(\d+)", created.headers.get("location", ""))
        if not match:
            raise RuntimeError("La creación del curso no devolvió una ubicación válida.")
        course_id = int(match.group(1))

        expect(
            client.post(
                f"/admin/authoring/courses/{course_id}/modules",
                data={
                    "title": "Módulo incompleto",
                    "description": "",
                    "learning_outcomes": "",
                    "estimated_minutes": "60",
                    "position": "1",
                },
            ),
            303,
            "creación del módulo",
        )
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1",
                (course_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("No se encontró el módulo de prueba.")
        module_id = int(row[0])

        initial = course_report(client, course_id)
        if initial.get("score", 100) >= 75:
            raise RuntimeError(f"El curso incompleto recibió una puntuación demasiado alta: {initial}")
        if not initial.get("issues"):
            raise RuntimeError("El Centro de Calidad no detectó problemas en el curso incompleto.")

        expect(
            client.post(
                f"/admin/authoring/modules/{module_id}/update",
                data={
                    "title": "Módulo completo",
                    "description": "Módulo revisado mediante el Centro de Calidad.",
                    "learning_outcomes": "Analizar y aplicar los conceptos del módulo en un caso auténtico.",
                    "estimated_minutes": "90",
                    "position": "1",
                },
            ),
            303,
            "actualización del módulo",
        )
        expect(
            client.post(
                f"/admin/authoring/modules/{module_id}/content",
                data={
                    "title": "Contenido principal",
                    "body_html": "<h2>Introducción</h2><p>Este contenido presenta conceptos, ejemplos, aplicación práctica y una síntesis final con suficiente desarrollo para el aprendizaje.</p>",
                },
            ),
            303,
            "contenido del módulo",
        )
        expect(
            client.post(
                f"/admin/authoring/modules/{module_id}/activities",
                data={
                    "item_type": "assignment",
                    "title": "Aplicación auténtica",
                    "instructions": "Resuelva el caso y justifique sus decisiones.",
                    "points": "25",
                    "due_at": "",
                    "tool_name": "native",
                    "external_url": "",
                    "embed_url": "",
                    "configuration_json": "{}",
                },
            ),
            303,
            "actividad evaluativa",
        )

        improved = course_report(client, course_id)
        if improved.get("score", 0) <= initial.get("score", 0):
            raise RuntimeError(f"La puntuación no mejoró después de completar el curso: {initial} -> {improved}")
        if improved.get("modules_with_outcomes") != 1 or improved.get("assessments") < 1:
            raise RuntimeError(f"El informe no reflejó las mejoras realizadas: {improved}")

        detail = client.get(f"/admin/quality/courses/{course_id}")
        expect(detail, 200, "detalle de calidad")
        for marker in ("Informe de calidad", "Recomendaciones", "Revisión por módulo"):
            if marker not in detail.text:
                raise RuntimeError(f"La vista detallada no mostró {marker!r}.")

    print(
        "Centro de Calidad validado: detección de problemas, informe JSON, recomendaciones y mejora de puntuación.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
