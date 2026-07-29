from __future__ import annotations

import json
import os
from pathlib import Path

DB_PATH = Path("/tmp/eagr-learning-xr-branding-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["APP_NAME"] = "EAGR Learning XR · STAGING"
os.environ["APP_ENV"] = "staging"
os.environ["RELEASE_CHANNEL"] = "staging"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "eagr-brand-session-secret-at-least-thirty-two-characters"
os.environ["NEXUS_SESSION_SECRET"] = "eagr-brand-admin-secret-at-least-thirty-two-characters"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "eagr.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-EAGR-Administrator-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Administrador EAGR Learning XR"

from fastapi.testclient import TestClient  # noqa: E402

from app.production_entry import app  # noqa: E402

BRAND = "EAGR Learning XR"
OLD_BRAND = "NEXUS EDU XR"


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: se esperaba {status} y se recibió {response.status_code}: "
            f"{response.text[:500]}"
        )


def require_brand(text: str, label: str) -> None:
    if BRAND not in text:
        raise RuntimeError(f"{label} no muestra la marca {BRAND}.")
    if OLD_BRAND in text:
        raise RuntimeError(f"{label} todavía muestra la marca anterior {OLD_BRAND}.")


def validate_static_files() -> None:
    index = Path("app/static/index.html").read_text(encoding="utf-8")
    manifest_text = Path("app/static/manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    admin_portal = Path("app/admin_portal.py").read_text(encoding="utf-8")
    admin_console = Path("app/admin_console.py").read_text(encoding="utf-8")

    require_brand(index, "portada estática")
    require_brand(manifest_text, "manifiesto")
    require_brand(admin_portal, "portal administrativo")
    require_brand(admin_console, "consola administrativa")

    if manifest.get("name") != BRAND or manifest.get("short_name") != "EAGR XR":
        raise RuntimeError(f"El manifiesto contiene nombres incorrectos: {manifest!r}")

    if "NEXUS_SESSION_SECRET" not in admin_console:
        raise RuntimeError("La compatibilidad de NEXUS_SESSION_SECRET fue alterada.")
    if "nexus_admin_users" not in admin_console:
        raise RuntimeError("La tabla técnica nexus_admin_users fue alterada.")


def main() -> None:
    validate_static_files()

    with TestClient(app, follow_redirects=False) as client:
        home = client.get("/")
        expect(home, 200, "portada")
        require_brand(home.text, "portada")

        release = client.get("/api/release")
        expect(release, 200, "identidad de versión")
        payload = release.json()
        if payload.get("application") != "EAGR Learning XR · STAGING":
            raise RuntimeError(f"/api/release devolvió una marca incorrecta: {payload!r}")
        if payload.get("isStaging") is not True or payload.get("isProduction") is not False:
            raise RuntimeError(f"/api/release no identifica staging correctamente: {payload!r}")

        login_page = client.get("/admin/login")
        expect(login_page, 200, "acceso administrativo")
        require_brand(login_page.text, "acceso administrativo")

        login = client.post(
            "/admin/login",
            data={
                "email": "eagr.admin@example.com",
                "password": "Initial-EAGR-Administrator-2026!",
            },
        )
        expect(login, 303, "inicio administrativo")

        password = client.post(
            "/admin/password",
            data={
                "password": "Updated-EAGR-Administrator-2026!",
                "confirm": "Updated-EAGR-Administrator-2026!",
            },
        )
        expect(password, 303, "cambio de contraseña")

        dashboard = client.get("/admin")
        expect(dashboard, 200, "portal administrativo")
        require_brand(dashboard.text, "portal administrativo")

    print(
        "Marca validada: EAGR Learning XR en portada, manifiesto, versión y administración; "
        "identificadores técnicos preservados.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
