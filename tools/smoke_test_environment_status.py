from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("APP_NAME", "NEXUS EDU XR · STAGING")
os.environ.setdefault("APP_ENV", "staging")
os.environ.setdefault("RELEASE_CHANNEL", "staging")
os.environ.setdefault(
    "SESSION_SECRET", "staging-environment-test-session-secret-at-least-32-characters"
)
os.environ.setdefault(
    "NEXUS_SESSION_SECRET", "staging-environment-test-admin-secret-at-least-32-characters"
)

_database = Path(tempfile.gettempdir()) / "nexus-environment-status-smoke.db"
try:
    _database.unlink()
except FileNotFoundError:
    pass
os.environ["DATABASE_URL"] = f"sqlite:///{_database}"

from fastapi.testclient import TestClient

from app.production_entry import app

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
SCRIPT = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"


def main() -> None:
    client = TestClient(app)

    release_response = client.get("/api/release")
    if release_response.status_code != 200:
        raise RuntimeError(
            f"/api/release devolvió {release_response.status_code} en vez de 200."
        )
    release = release_response.json()
    expected = {
        "environment": "staging",
        "releaseChannel": "staging",
        "isProduction": False,
        "isStaging": True,
    }
    mismatches = {
        key: {"expected": value, "received": release.get(key)}
        for key, value in expected.items()
        if release.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Identidad de staging incorrecta: {mismatches}")

    index = INDEX.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    markers = {
        "index.html": ('id="environment-banner"', "ENTORNO DE PRUEBA"),
        "app.js": ("NEXUS_ENVIRONMENT_BANNER_V1", "/api/release", "isStaging"),
        "styles.css": ("NEXUS_ENVIRONMENT_BANNER_V1", ".environment-banner"),
    }
    content = {"index.html": index, "app.js": script, "styles.css": styles}
    missing = {
        name: [marker for marker in required if marker not in content[name]]
        for name, required in markers.items()
    }
    missing = {name: values for name, values in missing.items() if values}
    if missing:
        raise RuntimeError(f"Banda de staging incompleta: {missing}")

    forbidden = ("location.reload(", "new MutationObserver", "client.navigate")
    detected = [value for value in forbidden if value in script]
    if detected:
        raise RuntimeError(f"La interfaz de staging contiene patrones inestables: {detected}")

    print(
        "Entorno staging validado: identidad, ruta de versión y banda visual estables.",
        flush=True,
    )


if __name__ == "__main__":
    main()
