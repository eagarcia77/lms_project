from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nexus-admin-home-access-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "admin-home-session-secret-at-least-thirty-two-characters"
os.environ["NEXUS_SESSION_SECRET"] = "admin-home-secret-at-least-thirty-two-characters"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "administrator@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Administrator-Password-2026!"
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
    index = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")

    static_checks = {
        "index.html": ('id="admin-access-top"', 'id="admin-access-nav"', "hidden"),
        "app.js": ("NEXUS_ADMIN_HOME_ACCESS_V1", "/api/admin/access"),
        "styles.css": ("NEXUS_ADMIN_HOME_ACCESS_V1", ".admin-access-button"),
    }
    contents = {"index.html": index, "app.js": script, "styles.css": styles}
    for name, markers in static_checks.items():
        missing = [marker for marker in markers if marker not in contents[name]]
        if missing:
            raise RuntimeError(f"{name} no contiene el acceso Administrador: {missing}")

    with TestClient(app, follow_redirects=False) as client:
        home = client.get("/")
        expect(home, 200, "portada")

        anonymous = client.get("/api/admin/access")
        expect(anonymous, 200, "acceso anónimo")
        if anonymous.json().get("allowed") is not False:
            raise RuntimeError("Un visitante anónimo recibió acceso Administrador.")

        login_page = client.get("/admin/login")
        expect(login_page, 200, "página de acceso administrativo")

        login = client.post(
            "/admin/login",
            data={
                "email": "administrator@example.com",
                "password": "Initial-Administrator-Password-2026!",
            },
        )
        expect(login, 303, "inicio administrativo")

        password = client.post(
            "/admin/password",
            data={
                "password": "Updated-Administrator-Password-2026!",
                "confirm": "Updated-Administrator-Password-2026!",
            },
        )
        expect(password, 303, "cambio de contraseña")

        access = client.get("/api/admin/access")
        expect(access, 200, "acceso administrativo autenticado")
        payload = access.json()
        if payload.get("allowed") is not True:
            raise RuntimeError(f"La sesión administrativa no habilitó Administrador: {payload!r}")
        if payload.get("authenticatedAdmin") is not True or payload.get("href") != "/admin":
            raise RuntimeError(f"La respuesta de Administrador es incorrecta: {payload!r}")

        dashboard = client.get("/admin")
        expect(dashboard, 200, "portal Administrador")
        for marker in ("Administración", "Cursos", "Usuarios"):
            if marker not in dashboard.text:
                raise RuntimeError(f"El portal Administrador no mostró {marker!r}.")

        logout = client.get("/admin/logout")
        expect(logout, 303, "cierre administrativo")
        after_logout = client.get("/api/admin/access")
        expect(after_logout, 200, "acceso después de salir")
        if after_logout.json().get("allowed") is not False:
            raise RuntimeError("Administrador permaneció visible después de cerrar sesión.")

    print(
        "Administrador validado: portada, autorización, inicio de sesión, portal y cierre seguro.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
