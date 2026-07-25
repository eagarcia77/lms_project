from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path('/tmp/nexus-academic-roles-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'academic-session-secret-at-least-thirty-two-characters'
os.environ['NEXUS_SESSION_SECRET'] = 'academic-admin-secret-at-least-thirty-two-characters'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'academic.admin@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Academic-Admin-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Administrador académico de prueba'

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get('/__test/platform-session/{role}', include_in_schema=False)
async def set_platform_session(request: Request, role: str):
    profiles = {
        'instructor': ('instructor.user@example.com', 'Instructor de prueba'),
        'student': ('student.user@example.com', 'Estudiante de prueba'),
    }
    email, name = profiles[role]
    request.session.clear()
    request.session['user'] = {'email': email, 'name': name}
    return {'ok': True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f'{label}: se esperaba {status} y se recibió {response.status_code}: '
            f'{response.text[:500]}'
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(
            client.post(
                '/admin/login',
                data={
                    'email': 'academic.admin@example.com',
                    'password': 'Initial-Academic-Admin-2026!',
                },
            ),
            303,
            'inicio administrativo',
        )
        expect(
            client.post(
                '/admin/password',
                data={
                    'password': 'Updated-Academic-Admin-2026!',
                    'confirm': 'Updated-Academic-Admin-2026!',
                },
            ),
            303,
            'cambio de contraseña administrativa',
        )

        roles_page = client.get('/admin/roles')
        expect(roles_page, 200, 'matriz de roles')
        for label in ('Instructor', 'Estudiante'):
            if label not in roles_page.text:
                raise RuntimeError(f'No se mostró el rol académico {label}.')

        users = (
            ('Instructor de prueba', 'instructor.user@example.com', 'instructor', 'Temporary-Instructor-2026!'),
            ('Estudiante de prueba', 'student.user@example.com', 'student', 'Temporary-Student-2026!'),
        )
        for full_name, email, role, password in users:
            expect(
                client.post(
                    '/admin/users',
                    data={
                        'full_name': full_name,
                        'email': email,
                        'role': role,
                        'password': password,
                    },
                ),
                303,
                f'creación de {role}',
            )

        course = client.post(
            '/admin/authoring/courses',
            data={
                'course_code': 'ACADEMIC-1001',
                'title': 'Curso para roles académicos',
                'description': 'Validación de Instructor y Estudiante.',
                'term': 'Pruebas 2026',
                'instructor_email': 'instructor.user@example.com',
                'template': 'blank',
            },
        )
        expect(course, 303, 'creación de curso académico')
        match = re.fullmatch(r'/admin/authoring/courses/(\d+)', course.headers.get('location', ''))
        if not match:
            raise RuntimeError('No se recibió el identificador del curso académico.')
        course_id = int(match.group(1))

        for email, course_role in (
            ('instructor.user@example.com', 'instructor'),
            ('student.user@example.com', 'student'),
        ):
            expect(
                client.post(
                    '/admin/enrollments',
                    data={
                        'course_id': str(course_id),
                        'user_email': email,
                        'course_role': course_role,
                    },
                ),
                303,
                f'matrícula de {course_role}',
            )

        with sqlite3.connect(DB_PATH) as conn:
            stored = dict(
                conn.execute(
                    "SELECT email,role FROM nexus_admin_users WHERE email IN (?,?)",
                    ('instructor.user@example.com', 'student.user@example.com'),
                ).fetchall()
            )
        if stored != {
            'instructor.user@example.com': 'instructor',
            'student.user@example.com': 'student',
        }:
            raise RuntimeError(f'Los roles institucionales no se guardaron correctamente: {stored!r}')

        expect(client.get('/admin/logout'), 303, 'cierre administrativo')

        for email, password in (
            ('instructor.user@example.com', 'Temporary-Instructor-2026!'),
            ('student.user@example.com', 'Temporary-Student-2026!'),
        ):
            denied = client.post('/admin/login', data={'email': email, 'password': password})
            expect(denied, 303, f'bloqueo administrativo de {email}')
            if denied.headers.get('location') != '/admin/login?error=1':
                raise RuntimeError(f'La cuenta académica no fue rechazada de forma segura: {denied.headers!r}')

        client.get('/__test/platform-session/instructor')
        instructor_me = client.get('/api/me')
        expect(instructor_me, 200, 'identidad de instructor')
        instructor = instructor_me.json()
        if instructor.get('platformRole') != 'instructor' or not instructor.get('isInstructor') or instructor.get('isAdmin'):
            raise RuntimeError(f'Identidad de instructor incorrecta: {instructor!r}')
        if not any(item.get('course_role') == 'instructor' for item in instructor.get('courseRoles', [])):
            raise RuntimeError('El instructor no recibió su rol de curso.')
        if client.get('/api/admin/access').json().get('allowed') is not False:
            raise RuntimeError('El instructor pudo ver el botón administrativo.')

        client.get('/__test/platform-session/student')
        student_me = client.get('/api/platform/access')
        expect(student_me, 200, 'identidad de estudiante')
        student = student_me.json()
        if student.get('platformRole') != 'student' or not student.get('isStudent') or student.get('isAdmin'):
            raise RuntimeError(f'Identidad de estudiante incorrecta: {student!r}')
        if not any(item.get('course_role') == 'student' for item in student.get('courseRoles', [])):
            raise RuntimeError('El estudiante no recibió su matrícula.')
        if client.get('/api/admin/access').json().get('allowed') is not False:
            raise RuntimeError('El estudiante pudo ver el botón administrativo.')

    print(
        'Roles académicos validados: Instructor y Estudiante, matrículas, identidad y separación administrativa.',
        flush=True,
    )


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
