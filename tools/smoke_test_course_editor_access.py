from __future__ import annotations

import json
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
            f'{label}: expected {status}, received {response.status_code}: {response.text[:1200]}'
        )


def require_marker(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f'{label} did not show {marker!r}: {response.text[:1400]}')


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
            'description': 'Course used to validate visual editing access.',
            'term': 'Fall 2026',
            'instructor_email': '',
            'template': 'blank',
        })
        expect(created, 303, 'course creation')
        course_id = int(created.headers['location'].rsplit('/', 1)[-1])

        course_page = client.get(f'/admin/authoring/courses/{course_id}')
        expect(course_page, 200, 'editable administrator course page')
        for marker in (
            'Editar configuración del curso',
            'Editar contenido del curso',
            'Abrir editor del profesor',
            'Administrar matrículas',
        ):
            require_marker(course_page, marker, 'administrator course page')

        open_editor = client.post(f'/admin/authoring/courses/{course_id}/open-editor')
        expect(open_editor, 303, 'open instructor editor')
        if open_editor.headers.get('location') != f'/faculty/courses/{course_id}':
            raise RuntimeError('Course editor did not preserve the legacy instructor redirect.')

        with db() as conn:
            enrollment = rows(execute(
                conn,
                """SELECT course_role,status FROM nexus_admin_enrollments
                   WHERE course_id=? AND lower(user_email)='editor-admin@example.com'""",
                (course_id,),
            ))
            if not enrollment or enrollment[0]['course_role'] != 'instructor' or enrollment[0]['status'] != 'active':
                raise RuntimeError('Administrator was not granted active instructor access.')

        legacy_course = client.get(f'/faculty/courses/{course_id}')
        expect(legacy_course, 303, 'legacy instructor course route')
        if legacy_course.headers.get('location') != f'/faculty/studio/courses/{course_id}':
            raise RuntimeError('Legacy course route did not redirect to the visual studio.')

        visual_course = client.get(f'/faculty/studio/courses/{course_id}')
        expect(visual_course, 200, 'visual course studio')
        require_marker(visual_course, 'data-testid="visual-course-studio"', 'visual course studio')
        require_marker(visual_course, 'data-autosave-key=', 'visual course studio')
        require_marker(visual_course, 'Preview as student', 'visual course studio')

        expect(client.post(f'/faculty/studio/courses/{course_id}/modules', data={
            'title': 'Editable Module',
            'description': 'Module content can be edited visually.',
            'learning_outcomes': 'Create and revise course content.',
            'estimated_minutes': '45',
        }), 303, 'visual module creation')

        with db() as conn:
            module_id = int(rows(execute(
                conn,
                'SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1',
                (course_id,),
            ))[0]['id'])

        refreshed = client.get(f'/admin/authoring/courses/{course_id}')
        expect(refreshed, 200, 'course page after module creation')
        require_marker(refreshed, 'Editable Module', 'administrator course page')
        require_marker(refreshed, 'Editar contenido', 'administrator course page')

        legacy_module = client.get(f'/faculty/modules/{module_id}')
        expect(legacy_module, 303, 'legacy module route')
        if legacy_module.headers.get('location') != f'/faculty/studio/modules/{module_id}':
            raise RuntimeError('Legacy module route did not redirect to the visual studio.')

        visual_module = client.get(f'/faculty/studio/modules/{module_id}')
        expect(visual_module, 200, 'visual module studio')
        require_marker(visual_module, 'data-testid="visual-module-studio"', 'visual module studio')
        require_marker(visual_module, 'data-select-type="assessment"', 'visual module studio')
        require_marker(visual_module, 'data-assessment-settings', 'visual module studio')
        require_marker(visual_module, 'https://forms.new', 'visual module studio')

        expect(client.post(f'/faculty/studio/modules/{module_id}/items', data={
            'item_type': 'page',
            'title': 'Editable Content Page',
            'body_html': '<h2>Visual content</h2><p>This content can be edited.</p>',
            'external_url': '',
            'embed_url': '',
            'points': '',
            'due_at': '',
            'accessible_alternative': 'Equivalent text content.',
            'assessment_response_type': 'text',
            'attempts': '1',
            'time_limit': '0',
            'rubric': '',
        }), 303, 'visual content creation')

        expect(client.post(f'/faculty/studio/modules/{module_id}/items', data={
            'item_type': 'assessment',
            'title': 'Module Assessment',
            'body_html': '<p>Explain the central concept.</p>',
            'external_url': '',
            'embed_url': '',
            'points': '25',
            'due_at': '2026-12-10T23:59',
            'accessible_alternative': 'Written assessment prompt.',
            'assessment_response_type': 'text',
            'attempts': '2',
            'time_limit': '45',
            'rubric': 'Accuracy, evidence, and clarity.',
        }), 303, 'assessment creation')

        with db() as conn:
            content = rows(execute(
                conn,
                "SELECT * FROM nexus_content_items WHERE module_id=? AND title='Editable Content Page'",
                (module_id,),
            ))[0]
            item_id = int(content['id'])
            assessment = rows(execute(
                conn,
                "SELECT * FROM nexus_content_items WHERE module_id=? AND title='Module Assessment'",
                (module_id,),
            ))[0]
            assessment_metadata = json.loads(assessment['metadata_json'])
            if assessment_metadata.get('assessment', {}).get('attempts') != 2:
                raise RuntimeError('Assessment attempts were not stored correctly.')
            if assessment_metadata.get('assessment', {}).get('time_limit') != 45:
                raise RuntimeError('Assessment time limit was not stored correctly.')

        legacy_item = client.get(f'/faculty/items/{item_id}/edit')
        expect(legacy_item, 303, 'legacy item edit route')
        if legacy_item.headers.get('location') != f'/faculty/studio/items/{item_id}/edit':
            raise RuntimeError('Legacy item route did not redirect to the visual editor.')

        item_editor = client.get(f'/faculty/studio/items/{item_id}/edit')
        expect(item_editor, 200, 'visual existing-content editor')
        require_marker(item_editor, 'data-testid="visual-item-editor"', 'visual item editor')
        require_marker(item_editor, 'data-rich-editor', 'visual item editor')
        require_marker(item_editor, 'Editable Content Page', 'visual item editor')

        updated = client.post(f'/faculty/studio/items/{item_id}/edit', data={
            'item_type': 'page',
            'title': 'Updated Content Page',
            'body_html': '<h2>Updated</h2><p>The visual editor saved this revision.</p>',
            'external_url': '',
            'embed_url': '',
            'points': '',
            'due_at': '',
            'position': '1',
            'status': 'published',
            'accessible_alternative': 'Updated equivalent text content.',
            'assessment_response_type': 'text',
            'attempts': '1',
            'time_limit': '0',
            'rubric': '',
        })
        expect(updated, 303, 'visual content update')

        expect(client.post(f'/faculty/studio/items/{item_id}/duplicate'), 303, 'content duplication')
        expect(client.post(f'/faculty/studio/modules/{module_id}/duplicate'), 303, 'module duplication')

        with db() as conn:
            updated_row = rows(execute(conn, 'SELECT title,status,body_html FROM nexus_content_items WHERE id=?', (item_id,)))[0]
            if updated_row['title'] != 'Updated Content Page' or updated_row['status'] != 'published':
                raise RuntimeError('Existing content was not updated and published.')
            copies = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE title LIKE '%Copy%'"))[0]
            if int(copies['total'] or 0) < 1:
                raise RuntimeError('Content duplication did not create a copy.')
            module_copies = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE title LIKE '%Copy%'"))[0]
            if int(module_copies['total'] or 0) < 1:
                raise RuntimeError('Module duplication did not create a copy.')

    print(
        'Visual Course Studio validated: administrator-to-instructor access, visual module and content editing, assessment settings, publishing, and duplication.',
        flush=True,
    )


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
