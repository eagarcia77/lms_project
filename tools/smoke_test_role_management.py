from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path('/tmp/nexus-role-management-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'roles-session-secret-at-least-thirty-two-characters'
os.environ['NEXUS_SESSION_SECRET'] = 'roles-admin-secret-at-least-thirty-two-characters'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'roles.admin@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Roles-Password-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Administrador de roles'

from fastapi.testclient import TestClient  # noqa: E402
from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f'{label}: se esperaba {status} y se recibió {response.status_code}: '
            f'{response.text[:500]}'
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.get('/admin/login'), 200, 'acceso administrativo')
        expect(
            client.post(
                '/admin/login',
                data={
                    'email': 'roles.admin@example.com',
                    'password': 'Initial-Roles-Password-2026!',
                },
            ),
            303,
            'inicio de sesión',
        )
        expect(
            client.post(
                '/admin/password',
                data={
                    'password': 'Updated-Roles-Password-2026!',
                    'confirm': 'Updated-Roles-Password-2026!',
                },
            ),
            303,
            'cambio de contraseña',
        )

        roles_page = client.get('/admin/roles')
        expect(roles_page, 200, 'matriz de roles')
        for text in ('Roles y permisos', 'Superadministrador', 'Administrador académico', 'Rol de curso'):
            if text not in roles_page.text:
                raise RuntimeError(f'La matriz de roles no mostró {text!r}.')

        expect(
            client.post(
                '/admin/users',
                data={
                    'full_name': 'Usuario delegado de prueba',
                    'email': 'delegated.user@example.com',
                    'role': 'support',
                    'password': 'Temporary-Delegate-2026!',
                },
            ),
            303,
            'creación de usuario delegado',
        )
        with sqlite3.connect(DB_PATH) as conn:
            delegated = conn.execute(
                'SELECT id,role,active,must_change_password FROM nexus_admin_users WHERE email=?',
                ('delegated.user@example.com',),
            ).fetchone()
            superadmin = conn.execute(
                'SELECT id FROM nexus_admin_users WHERE email=?',
                ('roles.admin@example.com',),
            ).fetchone()
        if not delegated or delegated[1] != 'support' or delegated[2] != 1 or delegated[3] != 1:
            raise RuntimeError('La cuenta delegada no se creó con los controles esperados.')
        if not superadmin:
            raise RuntimeError('No se encontró el superadministrador de prueba.')
        delegated_id = int(delegated[0])
        superadmin_id = int(superadmin[0])

        expect(
            client.post(f'/admin/users/{delegated_id}/role', data={'role': 'user_admin'}),
            303,
            'cambio de rol de plataforma',
        )
        expect(
            client.post(f'/admin/users/{delegated_id}/force-password-reset'),
            303,
            'restablecimiento obligatorio de contraseña',
        )
        expect(
            client.post(f'/admin/users/{delegated_id}/status', data={'active': '0'}),
            303,
            'suspensión de cuenta',
        )
        expect(
            client.post(f'/admin/users/{delegated_id}/status', data={'active': '1'}),
            303,
            'reactivación de cuenta',
        )
        expect(
            client.post(f'/admin/users/{superadmin_id}/status', data={'active': '0'}),
            400,
            'protección contra autosuspensión',
        )

        course = client.post(
            '/admin/authoring/courses',
            data={
                'course_code': 'ROLES-1001',
                'title': 'Curso para validar roles',
                'description': 'Prueba automática de roles por curso.',
                'term': 'Pruebas 2026',
                'instructor_email': 'delegated.user@example.com',
                'template': 'blank',
            },
        )
        expect(course, 303, 'creación de curso')
        match = re.fullmatch(r'/admin/authoring/courses/(\d+)', course.headers.get('location', ''))
        if not match:
            raise RuntimeError('La creación del curso no produjo una ruta válida.')
        course_id = int(match.group(1))

        expect(
            client.post(
                '/admin/enrollments',
                data={
                    'course_id': str(course_id),
                    'user_email': 'delegated.user@example.com',
                    'course_role': 'instructor',
                },
            ),
            303,
            'asignación de rol de curso',
        )
        with sqlite3.connect(DB_PATH) as conn:
            enrollment = conn.execute(
                'SELECT id,course_role,status FROM nexus_admin_enrollments WHERE course_id=? AND user_email=?',
                (course_id, 'delegated.user@example.com'),
            ).fetchone()
        if not enrollment or enrollment[1] != 'instructor' or enrollment[2] != 'active':
            raise RuntimeError('El rol inicial del curso no fue almacenado.')
        enrollment_id = int(enrollment[0])

        expect(
            client.post(
                f'/admin/enrollments/{enrollment_id}/role',
                data={'course_role': 'course_builder'},
            ),
            303,
            'cambio de rol dentro del curso',
        )
        expect(
            client.post(
                f'/admin/enrollments/{enrollment_id}/status',
                data={'status': 'inactive'},
            ),
            303,
            'suspensión de matrícula',
        )
        expect(
            client.post(
                f'/admin/enrollments/{enrollment_id}/status',
                data={'status': 'active'},
            ),
            303,
            'reactivación de matrícula',
        )

        with sqlite3.connect(DB_PATH) as conn:
            updated_user = conn.execute(
                'SELECT role,active,must_change_password FROM nexus_admin_users WHERE id=?',
                (delegated_id,),
            ).fetchone()
            updated_enrollment = conn.execute(
                'SELECT course_role,status FROM nexus_admin_enrollments WHERE id=?',
                (enrollment_id,),
            ).fetchone()
            actions = {
                row[0]
                for row in conn.execute(
                    "SELECT action FROM nexus_admin_audit WHERE action IN ('admin_role_changed','admin_user_status_changed','admin_password_reset_required','course_role_changed','enrollment_status_changed')"
                ).fetchall()
            }
        if updated_user != ('user_admin', 1, 1):
            raise RuntimeError(f'El usuario delegado terminó con valores inesperados: {updated_user!r}.')
        if updated_enrollment != ('course_builder', 'active'):
            raise RuntimeError(f'La matrícula terminó con valores inesperados: {updated_enrollment!r}.')
        required_actions = {
            'admin_role_changed',
            'admin_user_status_changed',
            'admin_password_reset_required',
            'course_role_changed',
            'enrollment_status_changed',
        }
        if not required_actions.issubset(actions):
            raise RuntimeError(f'Faltan eventos de auditoría de roles: {sorted(required_actions - actions)}')

        users_page = client.get('/admin/users')
        expect(users_page, 200, 'administración de usuarios')
        enrollments_page = client.get('/admin/enrollments')
        expect(enrollments_page, 200, 'administración de matrículas')
        for response, expected in (
            (users_page, 'Usuario delegado de prueba'),
            (users_page, 'Administrador de usuarios'),
            (enrollments_page, 'Diseñador o constructor del curso'),
        ):
            if expected not in response.text:
                raise RuntimeError(f'La interfaz de roles no mostró {expected!r}.')

        expect(
            client.post(f'/admin/enrollments/{enrollment_id}/delete'),
            303,
            'retiro del curso',
        )
        expect(client.get('/admin/logout'), 303, 'cierre de sesión')

    print(
        'Gestión de roles validada: cuentas, permisos, seguridad, roles de curso y auditoría.',
        flush=True,
    )


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
