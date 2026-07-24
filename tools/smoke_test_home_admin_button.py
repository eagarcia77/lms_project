from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path('/tmp/nexus-home-admin-button-test.db')
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['ENVIRONMENT'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SESSION_SECRET'] = 'home-button-session-secret-at-least-thirty-two-characters'
os.environ['NEXUS_SESSION_SECRET'] = 'home-button-admin-secret-at-least-thirty-two-characters'
os.environ['NEXUS_BOOTSTRAP_ADMIN_EMAIL'] = 'home.admin@example.com'
os.environ['NEXUS_BOOTSTRAP_ADMIN_PASSWORD'] = 'Initial-Home-Admin-Password-2026!'
os.environ['NEXUS_BOOTSTRAP_ADMIN_NAME'] = 'Administrador de portada'

from fastapi.testclient import TestClient  # noqa: E402
from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f'{label}: se esperaba {status} y se recibió {response.status_code}: {response.text[:500]}')


def main() -> None:
    index = Path('app/static/index.html').read_text(encoding='utf-8')
    script = Path('app/static/app.js').read_text(encoding='utf-8')
    styles = Path('app/static/styles.css').read_text(encoding='utf-8')
    required_static = {
        'index.html': ('id="admin-access"', 'hidden', 'href="/admin"'),
        'app.js': ('async function updateAdminAccess()', '/api/admin/access', 'adminLink.hidden = false'),
        'styles.css': ('.admin-access-button{', '.admin-access-button[hidden]'),
    }
    for name, markers in required_static.items():
        content = {'index.html': index, 'app.js': script, 'styles.css': styles}[name]
        missing = [marker for marker in markers if marker not in content]
        if missing:
            raise RuntimeError(f'{name} no contiene la integración del botón administrativo: {missing}')

    with TestClient(app, follow_redirects=False) as client:
        public_access = client.get('/api/admin/access')
        expect(public_access, 200, 'consulta pública de acceso administrativo')
        if public_access.json().get('allowed') is not False:
            raise RuntimeError('Un visitante anónimo pudo ver el acceso administrativo.')

        expect(client.get('/'), 200, 'portada pública')
        login = client.post(
            '/admin/login',
            data={
                'email': 'home.admin@example.com',
                'password': 'Initial-Home-Admin-Password-2026!',
            },
        )
        expect(login, 303, 'inicio de sesión administrativa')
        password = client.post(
            '/admin/password',
            data={
                'password': 'Updated-Home-Admin-Password-2026!',
                'confirm': 'Updated-Home-Admin-Password-2026!',
            },
        )
        expect(password, 303, 'cambio de contraseña administrativa')

        admin_access = client.get('/api/admin/access')
        expect(admin_access, 200, 'consulta autenticada de acceso administrativo')
        payload = admin_access.json()
        if payload.get('allowed') is not True or payload.get('authenticatedAdmin') is not True:
            raise RuntimeError(f'La sesión administrativa no habilitó el botón: {payload!r}')
        if payload.get('href') != '/admin' or payload.get('role') != 'superadmin':
            raise RuntimeError(f'El acceso administrativo devolvió datos inesperados: {payload!r}')

        expect(client.get('/admin/logout'), 303, 'cierre de sesión administrativa')
        after_logout = client.get('/api/admin/access')
        expect(after_logout, 200, 'consulta después del cierre de sesión')
        if after_logout.json().get('allowed') is not False:
            raise RuntimeError('El botón administrativo permaneció autorizado después de cerrar sesión.')

    print('Botón de administración validado: oculto para visitantes y visible únicamente para administradores.', flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
