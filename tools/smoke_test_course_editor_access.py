from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path('/tmp/nuvedra-course-editor-access-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['APP_NAME'] = 'NUVEDRA'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'course-editor-session-secret-at-least-thirty-two'
os.environ['NEXUS_SESSION_SECRET'] = 'course-editor-admin-secret-at-least-thirty-two'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'editor-admin@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Course-Editor-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Course Editor Administrator'
os.environ.pop('GOOGLE_CLIENT_ID', None)
os.environ.pop('GOOGLE_CLIENT_SECRET', None)

from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows  # noqa: E402
from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f'{label}: expected {status}, received {response.status_code}: {response.text[:1000]}'
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        login = client.post('/admin/login', data={
            'email': 'editor-admin@example.com',
            'password': 'Initial-Course-Editor-2026!',
        })
        expect(login, 303, 'administrator login')
        expect(client.post('/admin/password', data={
            'password': 'Updated-Course-Editor-2026!',
            'confirm': 'Updated-Course-Editor-2026!',
        }), 303, 'administrator password update')

        created = client.post('/admin/authoring/courses', data={
            'course_code': 'EDIT-1001',
            'title': 'Editable Course',
            'description': 'Course used to validate editing access.',
            'term': 'Fall 2026',
            'instructor_email': '',
            'template': 'blank',
        })
        expect(created, 303, 'course creation')
        course_id = int(created.headers['location'].rsplit('/', 1)[-1])

        course_page = client.get(f'/admin/authoring/courses/{course_id}')
        expect(course_page, 200, 'editable administrator course page')
        for marker in ('Editar configuración del curso', 'Editar contenido del curso', 'Abrir editor del profesor'):
            if marker not in course_page.text:
                raise RuntimeError(f'Course page did not show {marker!r}.')

        open_editor = client.post(f'/admin/authoring/courses/{course_id}/open-editor')
        expect(open_editor, 303, 'open instructor editor')
        if open_editor.headers.get('location') != f'/faculty/courses/{course_id}':
            raise RuntimeError('Course editor did not redirect to the instructor workspace.')

        with db() as conn:
            enrollment = rows(execute(
                conn,
                """SELECT course_role,status FROM nexus_admin_enrollments
                   WHERE course_id=? AND lower(user_email)='editor-admin@example.com'""",
                (course_id,),
            ))
            if not enrollment or enrollment[0]['course_role'] != 'instructor' or enrollment[0]['status'] != 'active':
                raise RuntimeError('Administrator was not granted active instructor access.')

        faculty_course = client.get(f'/faculty/courses/{course_id}')
        expect(faculty_course, 200, 'instructor course editor')
        if 'Crear módulo' not in faculty_course.text:
            raise RuntimeError('Instructor editor did not show module creation.')

        expect(client.post(f'/faculty/courses/{course_id}/modules', data={
            'title': 'Editable Module',
            'description': 'Module content can be edited.',
            'learning_outcomes': 'Create and revise course content.',
            'estimated_minutes': '45',
            'position': '1',
        }), 303, 'module creation')

        with db() as conn:
            module_id = int(rows(execute(
                conn,
                'SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1',
                (course_id,),
            ))[0]['id'])

        refreshed = client.get(f'/admin/authoring/courses/{course_id}')
        expect(refreshed, 200, 'course page after module creation')
        if 'Editable Module' not in refreshed.text or 'Editar contenido' not in refreshed.text:
            raise RuntimeError('Administrator course page did not expose module content editing.')

        module_editor = client.post(f'/admin/authoring/modules/{module_id}/open-editor')
        expect(module_editor, 303, 'open module editor')
        if module_editor.headers.get('location') != f'/faculty/modules/{module_id}':
            raise RuntimeError('Module editor did not redirect correctly.')

        faculty_module = client.get(f'/faculty/modules/{module_id}')
        expect(faculty_module, 200, 'faculty module editor')
        if 'Añadir contenido o evaluación' not in faculty_module.text:
            raise RuntimeError('Module editor did not show the content form.')

        expect(client.post(f'/faculty/modules/{module_id}/items', data={
            'item_type': 'page',
            'title': 'Editable Content Page',
            'body_html': '<p>This content can be edited.</p>',
            'external_url': '',
            'embed_url': '',
            'points': '',
            'due_at': '',
            'accessible_alternative': 'Equivalent text content.',
        }), 303, 'content creation')

        with db() as conn:
            item_id = int(rows(execute(
                conn,
                'SELECT id FROM nexus_content_items WHERE module_id=? ORDER BY id DESC LIMIT 1',
                (module_id,),
            ))[0]['id'])

        edit_item = client.get(f'/faculty/items/{item_id}/edit')
        expect(edit_item, 200, 'existing content editor')
        if 'Editable Content Page' not in edit_item.text or 'Guardar cambios' not in edit_item.text:
            raise RuntimeError('Existing course content could not be opened for editing.')

    print('Course editing validated: administrators can edit course settings, enable instructor access, and edit existing modules and content.', flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
