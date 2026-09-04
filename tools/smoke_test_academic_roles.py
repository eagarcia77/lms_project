from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path('/tmp/nuvedra-academic-roles-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['APP_NAME'] = 'NUVEDRA'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'academic-role-session-secret-at-least-thirty-two'
os.environ['NEXUS_SESSION_SECRET'] = 'academic-role-admin-secret-at-least-thirty-two'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'admin@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Academic-Password-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Administración académica'
os.environ.pop('GOOGLE_CLIENT_ID', None)
os.environ.pop('GOOGLE_CLIENT_SECRET', None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.academic_access import AUTHOR_ROLES, STUDENT_ROLES, require_course_role  # noqa: E402
from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get('/__smoke/google-user/{kind}', include_in_schema=False)
async def smoke_google_user(kind: str, request: Request):
    users = {
        'professor': {'id': 'prof-1', 'name': 'Profesora Prueba', 'email': 'professor@example.com'},
        'student': {'id': 'student-1', 'name': 'Estudiante Prueba', 'email': 'student@example.com'},
        'observer': {'id': 'observer-1', 'name': 'Observador Prueba', 'email': 'observer@example.com'},
    }
    request.session['user'] = users[kind]
    return {'ok': True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f'{label}: se esperaba {status} y se recibió {response.status_code}: '
            f'{response.text[:800]}'
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        portal = client.get('/portal')
        expect(portal, 200, 'portal académico público')
        # The UI is English-first with a Spanish switch, so validate the functional
        # Google sign-in route instead of coupling the smoke test to translated copy.
        if 'href="/portal/login"' not in portal.text:
            raise RuntimeError('El portal académico no mostró un acceso funcional con Google.')
        google_login = client.get('/portal/login')
        expect(google_login, 303, 'inicio de autenticación Google')
        if not google_login.headers.get('location', '').startswith('/auth/google/login'):
            raise RuntimeError('El acceso académico no redirigió al flujo OAuth de Google.')

        login = client.post('/admin/login', data={
            'email': 'admin@example.com',
            'password': 'Initial-Academic-Password-2026!',
        })
        expect(login, 303, 'inicio de sesión administrativo')
        password = client.post('/admin/password', data={
            'password': 'Updated-Academic-Password-2026!',
            'confirm': 'Updated-Academic-Password-2026!',
        })
        expect(password, 303, 'cambio de contraseña administrativo')

        created = client.post('/admin/authoring/courses', data={
            'course_code': 'ROLE-1001',
            'title': 'Curso por roles',
            'description': 'Curso para validar administración, docencia y estudiantes.',
            'term': 'Agosto-Diciembre 2026',
            'instructor_email': 'professor@example.com',
            'template': 'blank',
        })
        expect(created, 303, 'creación administrativa del curso')
        location = created.headers.get('location', '')
        course_id = int(location.rsplit('/', 1)[-1])

        with db() as conn:
            professor = rows(execute(
                conn,
                "SELECT * FROM nexus_admin_enrollments WHERE course_id=? AND user_email='professor@example.com'",
                (course_id,),
            ))
            if not professor or professor[0]['course_role'] != 'instructor':
                raise RuntimeError('El profesor no quedó asignado automáticamente al curso.')
            require_course_role(conn, course_id, 'professor@example.com', AUTHOR_ROLES)
            try:
                require_course_role(conn, course_id, 'professor@example.com', STUDENT_ROLES)
            except Exception:
                pass
            else:
                raise RuntimeError('El profesor recibió permisos de estudiante incorrectamente.')
            execute(
                conn,
                "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                (course_id, 'student@example.com', 'student', 'active', utcnow()),
            )
            execute(
                conn,
                "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                (course_id, 'observer@example.com', 'observer', 'active', utcnow()),
            )

        expect(client.get('/__smoke/google-user/professor'), 200, 'sesión de profesor')
        legacy_faculty = client.get(f'/faculty/courses/{course_id}')
        expect(legacy_faculty, 303, 'redirección del espacio docente anterior')
        studio_location = f'/faculty/studio/courses/{course_id}'
        if legacy_faculty.headers.get('location', '') != studio_location:
            raise RuntimeError(
                'La ruta docente anterior no redirigió al Visual Course Studio: '
                f"{legacy_faculty.headers.get('location', '')!r}."
            )
        faculty = client.get(studio_location)
        expect(faculty, 200, 'Visual Course Studio del profesor')
        for marker in (
            'data-testid="visual-course-studio"',
            f'action="/faculty/studio/courses/{course_id}/modules"',
        ):
            if marker not in faculty.text:
                raise RuntimeError(f'El Visual Course Studio no mostró {marker!r}.')

        module_response = client.post(f'/faculty/courses/{course_id}/modules', data={
            'title': 'Módulo publicado',
            'description': 'Contenido preparado por el profesor.',
            'learning_outcomes': 'Aplicar el contenido del módulo.',
            'estimated_minutes': '60',
            'position': '1',
        })
        expect(module_response, 303, 'creación de módulo por profesor')
        with db() as conn:
            module_id = int(rows(execute(
                conn,
                'SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1',
                (course_id,),
            ))[0]['id'])

        item_response = client.post(f'/faculty/modules/{module_id}/items', data={
            'item_type': 'assessment',
            'title': 'Evaluación del módulo',
            'body_html': '<h2>Instrucciones</h2><p>Conteste la pregunta.</p>',
            'external_url': '',
            'embed_url': '',
            'points': '20',
            'due_at': '',
            'accessible_alternative': 'La misma pregunta está disponible en texto.',
        })
        expect(item_response, 303, 'creación de evaluación por profesor')
        with db() as conn:
            item_id = int(rows(execute(
                conn,
                'SELECT id FROM nexus_content_items WHERE module_id=? ORDER BY id DESC LIMIT 1',
                (module_id,),
            ))[0]['id'])

        expect(client.post(f'/faculty/modules/{module_id}/update', data={
            'title': 'Módulo publicado',
            'description': 'Contenido preparado por el profesor.',
            'learning_outcomes': 'Aplicar el contenido del módulo.',
            'estimated_minutes': '60',
            'position': '1',
            'status': 'published',
        }), 303, 'publicación de módulo por profesor')
        expect(client.post(f'/faculty/items/{item_id}/edit', data={
            'item_type': 'assessment',
            'title': 'Evaluación del módulo',
            'body_html': '<h2>Instrucciones</h2><p>Conteste la pregunta.</p>',
            'external_url': '',
            'embed_url': '',
            'metadata_json': '{}',
            'points': '20',
            'due_at': '',
            'position': '1',
            'status': 'published',
        }), 303, 'publicación de evaluación por profesor')

        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (utcnow(), course_id))

        drive = client.get(f'/admin/authoring/modules/{module_id}/drive')
        expect(drive, 200, 'Google Hub sencillo sin conexión Google')
        for marker in ('Google Hub sencillo', 'pegar enlace compartido', 'Conectar Google'):
            if marker not in drive.text:
                raise RuntimeError(f'Google Hub no mostró {marker!r}.')

        expect(client.get('/__smoke/google-user/student'), 200, 'sesión de estudiante')
        student_course = client.get(f'/learn/courses/{course_id}')
        expect(student_course, 200, 'vista del curso para estudiante')
        if 'Evaluación del módulo' not in student_course.text:
            raise RuntimeError('El estudiante no pudo ver la evaluación publicada.')
        expect(client.get(studio_location), 403, 'bloqueo del Visual Course Studio para estudiante')
        item = client.get(f'/learn/items/{item_id}')
        expect(item, 200, 'evaluación para estudiante')
        if f'action="/learn/items/{item_id}/submit"' not in item.text:
            raise RuntimeError('La evaluación no mostró un formulario de entrega funcional.')
        submission = client.post(f'/learn/items/{item_id}/submit', data={
            'response_text': 'Respuesta de validación.',
            'response_url': '',
        })
        expect(submission, 303, 'entrega de evaluación')
        with db() as conn:
            saved = rows(execute(
                conn,
                "SELECT * FROM nuvedra_submissions WHERE item_id=? AND student_email='student@example.com'",
                (item_id,),
            ))
            if not saved or saved[0]['response_text'] != 'Respuesta de validación.':
                raise RuntimeError('La respuesta del estudiante no quedó guardada.')

        expect(client.get('/__smoke/google-user/observer'), 200, 'sesión de observador')
        expect(client.get(f'/learn/items/{item_id}'), 200, 'lectura para observador')
        expect(client.get(studio_location), 403, 'bloqueo del Visual Course Studio para observador')
        expect(client.post(f'/learn/items/{item_id}/submit', data={
            'response_text': 'No debe guardarse.',
            'response_url': '',
        }), 403, 'bloqueo de entrega para observador')

    print('Portal por roles validado: administrador crea y asigna; profesor desarrolla en Visual Course Studio; estudiante visualiza y responde; Google Drive falla de forma segura.', flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
