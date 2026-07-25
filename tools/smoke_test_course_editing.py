from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path('/tmp/nexus-course-editing-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'course-edit-session-secret-at-least-thirty-two-characters'
os.environ['NEXUS_SESSION_SECRET'] = 'course-edit-admin-secret-at-least-thirty-two-characters'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'course.editor@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Course-Editor-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Administrador de cursos'

from fastapi.testclient import TestClient  # noqa: E402
from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f'{label}: se esperaba {status} y se recibió {response.status_code}: '
            f'{response.text[:700]}'
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(
            client.post(
                '/admin/login',
                data={'email': 'course.editor@example.com', 'password': 'Initial-Course-Editor-2026!'},
            ),
            303,
            'inicio administrativo',
        )
        expect(
            client.post(
                '/admin/password',
                data={'password': 'Updated-Course-Editor-2026!', 'confirm': 'Updated-Course-Editor-2026!'},
            ),
            303,
            'cambio de contraseña',
        )

        studio = client.get('/course-studio')
        expect(studio, 200, 'Course Studio')
        if 'Crear curso' not in studio.text or 'Editar curso' not in studio.text:
            raise RuntimeError('Course Studio no mostró los controles de creación y edición.')

        created = client.post(
            '/admin/authoring/courses',
            data={
                'course_code': 'EDIT-1001',
                'title': 'Curso para editar',
                'description': 'Versión inicial.',
                'term': 'Pruebas 2026',
                'instructor_email': 'instructor@example.com',
                'template': 'blank',
            },
        )
        expect(created, 303, 'creación del curso')
        match = re.fullmatch(r'/admin/authoring/courses/(\d+)', created.headers.get('location', ''))
        if not match:
            raise RuntimeError('La creación no devolvió una dirección de edición válida.')
        course_id = int(match.group(1))

        expect(
            client.post(
                f'/admin/authoring/courses/{course_id}/update',
                data={
                    'course_code': 'EDIT-1001',
                    'title': 'Curso actualizado correctamente',
                    'description': 'Descripción modificada desde Course Studio.',
                    'term': 'Agosto-Diciembre 2026',
                    'instructor_email': 'instructor@example.com',
                    'status': 'active',
                },
            ),
            303,
            'actualización del curso',
        )

        expect(
            client.post(
                f'/admin/authoring/courses/{course_id}/modules',
                data={
                    'title': 'Módulo inicial',
                    'description': 'Descripción inicial.',
                    'learning_outcomes': 'Aplicar el contenido.',
                    'estimated_minutes': '60',
                    'position': '1',
                },
            ),
            303,
            'creación del módulo',
        )
        with sqlite3.connect(DB_PATH) as conn:
            module = conn.execute(
                'SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1',
                (course_id,),
            ).fetchone()
        if not module:
            raise RuntimeError('El módulo nuevo no se almacenó.')
        module_id = int(module[0])

        expect(
            client.post(
                f'/admin/authoring/modules/{module_id}/update',
                data={
                    'title': 'Módulo actualizado',
                    'description': 'Descripción actualizada.',
                    'learning_outcomes': 'Crear y evaluar una solución.',
                    'estimated_minutes': '90',
                    'position': '2',
                },
            ),
            303,
            'actualización del módulo',
        )
        expect(
            client.post(
                f'/admin/authoring/modules/{module_id}/content',
                data={'title': 'Contenido actualizado', 'body_html': '<h2>Contenido</h2><p>Guardado correctamente.</p>'},
            ),
            303,
            'guardado del contenido',
        )

        courses_api = client.get('/api/courses')
        expect(courses_api, 200, 'catálogo unificado')
        catalog = courses_api.json()
        updated = next((item for item in catalog if item.get('id') == course_id), None)
        if not updated or updated.get('title') != 'Curso actualizado correctamente' or not updated.get('can_edit'):
            raise RuntimeError(f'La portada no recibió el curso actualizado: {updated!r}')

        detail = client.get(f'/api/courses/{course_id}')
        expect(detail, 200, 'detalle unificado')
        payload = detail.json()
        if payload['course']['title'] != 'Curso actualizado correctamente':
            raise RuntimeError('El detalle del curso no reflejó la actualización.')
        if not payload['modules'] or payload['modules'][0]['title'] != 'Módulo actualizado':
            raise RuntimeError(f'El módulo actualizado no llegó al catálogo: {payload["modules"]!r}')

        with sqlite3.connect(DB_PATH) as conn:
            legacy = conn.execute("SELECT id FROM nexus_admin_courses WHERE course_code='NTEL 3770'").fetchone()
        if not legacy:
            raise RuntimeError('El curso histórico NTEL 3770 no fue migrado al catálogo editable.')
        legacy_id = int(legacy[0])
        expect(
            client.post(
                f'/admin/authoring/courses/{legacy_id}/update',
                data={
                    'course_code': 'NTEL 3770',
                    'title': 'Redes Inalámbricas — editado',
                    'description': 'Curso histórico ahora editable.',
                    'term': '',
                    'instructor_email': '',
                    'status': 'active',
                },
            ),
            303,
            'edición de curso histórico',
        )
        legacy_detail = client.get(f'/api/courses/{legacy_id}')
        expect(legacy_detail, 200, 'curso histórico en portada')
        if legacy_detail.json()['course']['title'] != 'Redes Inalámbricas — editado':
            raise RuntimeError('El curso histórico no reflejó los cambios realizados.')

        page = client.get(f'/admin/authoring/courses/{course_id}')
        expect(page, 200, 'página de edición')
        for marker in ('Guardar cambios del curso', 'Guardar módulo', 'Editar contenido y evaluación'):
            if marker not in page.text:
                raise RuntimeError(f'La página de edición no mostró {marker!r}.')

    script = Path('app/static/app.js').read_text(encoding='utf-8')
    for marker in ('NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND', 'data-edit-course', 'location.href = "/course-studio"'):
        if marker not in script:
            raise RuntimeError(f'La portada no quedó conectada al editor: falta {marker!r}.')

    print(
        'Edición de cursos validada: creación, actualización, módulos, contenido, catálogo y cursos históricos.',
        flush=True,
    )


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
