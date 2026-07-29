from __future__ import annotations

import os
import re
from pathlib import Path

DB_PATH = Path('/tmp/nexus-integrated-portal-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['APP_NAME'] = 'NUVEDRA'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'portal-session-secret-at-least-thirty-two-characters'
os.environ['NEXUS_SESSION_SECRET'] = 'portal-admin-secret-at-least-thirty-two-characters'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'portal.admin@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Portal-Password-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Administración integrada'

from fastapi.testclient import TestClient  # noqa: E402
from app.production_entry import app  # noqa: E402


PUBLIC_BRAND = 'NUVEDRA'
LEGACY_PUBLIC_BRAND = 'NEXUS EDU XR'


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f'{label}: se esperaba {status} y se recibió {response.status_code}: {response.text[:500]}')


def assert_portal(response, label: str) -> None:
    expect(response, 200, label)
    required = ('Administración integral', 'Panel general', 'Diseño académico', 'Innovación IA/XR', 'Roles y permisos', 'Sistema')
    missing = [text for text in required if text not in response.text]
    if missing:
        raise RuntimeError(f'{label}: faltan elementos del portal integrado: {missing}')
    if PUBLIC_BRAND not in response.text:
        raise RuntimeError(f'{label}: no mostró la marca pública {PUBLIC_BRAND}.')
    if LEGACY_PUBLIC_BRAND in response.text:
        raise RuntimeError(f'{label}: todavía mostró la marca anterior {LEGACY_PUBLIC_BRAND}.')


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        login_page = client.get('/admin/login')
        expect(login_page, 200, 'acceso administrativo')
        if PUBLIC_BRAND not in login_page.text or LEGACY_PUBLIC_BRAND in login_page.text:
            raise RuntimeError('La pantalla de acceso administrativo no refleja correctamente la marca NUVEDRA.')

        login = client.post('/admin/login', data={'email': 'portal.admin@example.com', 'password': 'Initial-Portal-Password-2026!'})
        expect(login, 303, 'inicio de sesión')
        password = client.post('/admin/password', data={'password': 'Updated-Portal-Password-2026!', 'confirm': 'Updated-Portal-Password-2026!'})
        expect(password, 303, 'cambio de contraseña')

        dashboard = client.get('/admin')
        assert_portal(dashboard, 'panel general integrado')
        for text in ('Centro de operaciones', 'Operaciones principales', 'Servicios integrados', 'Personas y acceso', 'Gobernanza y continuidad'):
            if text not in dashboard.text:
                raise RuntimeError(f'El panel general no mostró {text!r}.')

        assert_portal(client.get('/admin/authoring'), 'Course Studio integrado')
        assert_portal(client.get('/admin/authoring/innovation'), 'Innovación integrada')
        assert_portal(client.get('/admin/roles'), 'Roles integrados')
        assert_portal(client.get('/admin/users'), 'Usuarios integrados')
        assert_portal(client.get('/admin/enrollments'), 'Matrículas integradas')
        assert_portal(client.get('/admin/audit'), 'Auditoría integrada')
        assert_portal(client.get('/admin/system'), 'Sistema integrado')

        course = client.post(
            '/admin/authoring/courses',
            data={
                'course_code': 'PORTAL-1001',
                'title': 'Curso del portal integrado',
                'description': 'Prueba de supervisión administrativa unificada.',
                'term': 'Pruebas 2026',
                'instructor_email': 'portal.admin@example.com',
                'template': 'blank',
            },
        )
        expect(course, 303, 'creación del curso integrado')
        if not re.fullmatch(r'/admin/authoring/courses/\d+', course.headers.get('location', '')):
            raise RuntimeError('La creación del curso no produjo una dirección válida.')

        courses = client.get('/admin/courses')
        assert_portal(courses, 'gestión integrada de cursos')
        for text in ('Gestión integrada de cursos', 'Curso del portal integrado', 'Diseñar', 'IA/XR', 'Matrículas'):
            if text not in courses.text:
                raise RuntimeError(f'La gestión integrada de cursos no mostró {text!r}.')

        backup = client.get('/admin/backup')
        expect(backup, 200, 'respaldo administrativo')
        if 'courses' not in backup.json() or 'audit' not in backup.json():
            raise RuntimeError('El respaldo administrativo está incompleto.')

        expect(client.get('/admin/logout'), 303, 'cierre de sesión')

    print('Portal NUVEDRA validado: marca, panel, diseño, innovación, roles, cursos, usuarios, matrículas, auditoría, sistema y respaldo.', flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
