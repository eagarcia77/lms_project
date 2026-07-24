from __future__ import annotations

import html
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.admin_console import database_url, db, execute, page, require_admin, rows


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "no instalado"


def _table_count(conn: Any, table: str) -> int | None:
    try:
        result = rows(execute(conn, f"SELECT COUNT(*) AS total FROM {table}"))
        return int(result[0]["total"]) if result else 0
    except Exception:
        return None


def _configuration_snapshot() -> list[dict[str, Any]]:
    session_secret = os.getenv("NEXUS_SESSION_SECRET") or os.getenv("SESSION_SECRET") or ""
    google_ready = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    smtp_ready = bool(
        os.getenv("SMTP_HOST")
        and os.getenv("SMTP_USERNAME")
        and os.getenv("SMTP_PASSWORD")
        and os.getenv("SMTP_FROM_EMAIL")
    )
    return [
        {
            "name": "Base de datos",
            "ok": bool(os.getenv("DATABASE_URL")),
            "detail": "PostgreSQL de Render" if database_url().startswith("postgres") else "SQLite local",
        },
        {
            "name": "Secreto de sesión",
            "ok": len(session_secret) >= 32,
            "detail": "Configurado" if session_secret else "No configurado",
        },
        {
            "name": "Cookies seguras",
            "ok": os.getenv("COOKIE_SECURE", "false").lower() == "true",
            "detail": "HTTPS obligatorio" if os.getenv("COOKIE_SECURE", "false").lower() == "true" else "Revise COOKIE_SECURE",
        },
        {
            "name": "Google Workspace",
            "ok": google_ready,
            "detail": "OAuth configurado" if google_ready else "Faltan GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET",
        },
        {
            "name": "Recuperación por correo",
            "ok": smtp_ready,
            "detail": "SMTP configurado" if smtp_ready else "Opcional: configure las variables SMTP",
        },
        {
            "name": "Asistente de inteligencia artificial",
            "ok": bool(os.getenv("AI_BASE_URL")),
            "detail": "Proveedor externo configurado" if os.getenv("AI_BASE_URL") else "Se utilizarán las plantillas pedagógicas locales",
        },
        {
            "name": "Collabora Online",
            "ok": bool(os.getenv("COLLABORA_BASE_URL")),
            "detail": "Editor OpenDocument externo configurado" if os.getenv("COLLABORA_BASE_URL") else "Opcional; ODT, ODP y ODS siguen disponibles",
        },
    ]


def register_admin_system(app: FastAPI) -> None:
    @app.get("/admin/system", response_class=HTMLResponse, response_model=None)
    async def system_dashboard(request: Request):
        user = require_admin(request)
        database_ok = True
        database_error = ""
        counts: dict[str, int | None] = {}
        try:
            with db() as conn:
                execute(conn, "SELECT 1")
                for key, table in (
                    ("Cursos", "nexus_admin_courses"),
                    ("Módulos", "nexus_modules"),
                    ("Contenido y evaluaciones", "nexus_content_items"),
                    ("Administradores", "nexus_admin_users"),
                    ("Matrículas", "nexus_admin_enrollments"),
                    ("Eventos de auditoría", "nexus_admin_audit"),
                ):
                    counts[key] = _table_count(conn, table)
        except Exception as exc:  # pragma: no cover - depende del servicio externo
            database_ok = False
            database_error = str(exc)[:240]

        checks = _configuration_snapshot()
        checks.insert(
            0,
            {
                "name": "Conexión de datos",
                "ok": database_ok,
                "detail": "Conexión verificada" if database_ok else f"Error: {database_error}",
            },
        )
        check_html = "".join(
            "<tr>"
            f"<td>{html.escape(str(item['name']))}</td>"
            f"<td class='status'>{'Correcto' if item['ok'] else 'Atención'}</td>"
            f"<td>{html.escape(str(item['detail']))}</td>"
            "</tr>"
            for item in checks
        )
        metrics = "".join(
            f"<div class='card metric'><strong>{'—' if total is None else total}</strong>{html.escape(label)}</div>"
            for label, total in counts.items()
        )
        route_count = len(request.app.routes)
        packages = {
            "FastAPI": _package_version("fastapi"),
            "Uvicorn": _package_version("uvicorn"),
            "Cryptography": _package_version("cryptography"),
            "Psycopg": _package_version("psycopg"),
            "Bleach": _package_version("bleach"),
            "odfpy": _package_version("odfpy"),
        }
        package_rows = "".join(
            f"<tr><td>{html.escape(name)}</td><td>{html.escape(value)}</td></tr>"
            for name, value in packages.items()
        )
        body = f"""
<h2>Estado y administración del sistema</h2>
<p>Diagnóstico seguro de NEXUS EDU XR. Esta pantalla nunca muestra contraseñas, secretos ni tokens.</p>
<div class="grid">{metrics}<div class="card metric"><strong>{route_count}</strong>Rutas activas</div></div>
<section class="card"><h3>Preparación de servicios</h3><table><thead><tr><th>Componente</th><th>Estado</th><th>Detalle</th></tr></thead><tbody>{check_html}</tbody></table></section>
<div class="grid">
<section class="card"><h3>Accesos administrativos</h3><p><a class="button" href="/admin/authoring">Diseñar cursos y módulos</a></p><p><a class="button" href="/admin/users">Administrar usuarios</a></p><p><a class="button" href="/admin/enrollments">Administrar matrículas</a></p><p><a class="button" href="/admin/audit">Revisar auditoría</a></p><p><a class="button" href="/admin/backup">Crear respaldo</a></p></section>
<section class="card"><h3>Entorno de ejecución</h3><table><tbody><tr><th>Python</th><td>{html.escape(sys.version.split()[0])}</td></tr><tr><th>Sistema</th><td>{html.escape(platform.system())} {html.escape(platform.machine())}</td></tr><tr><th>Ambiente</th><td>{html.escape(os.getenv('APP_ENV', 'production'))}</td></tr><tr><th>Motor de datos</th><td>{'PostgreSQL' if database_url().startswith('postgres') else 'SQLite'}</td></tr></tbody></table><h4>Paquetes críticos</h4><table><tbody>{package_rows}</tbody></table></section>
</div>
"""
        return page("Estado del sistema", body, user)

    @app.get("/admin/system/health", response_class=JSONResponse, response_model=None)
    async def system_health(request: Request):
        require_admin(request)
        database_ok = True
        try:
            with db() as conn:
                execute(conn, "SELECT 1")
        except Exception:
            database_ok = False
        checks = _configuration_snapshot()
        return JSONResponse(
            {
                "status": "ok" if database_ok else "degraded",
                "database": database_ok,
                "routes": len(request.app.routes),
                "configuration": {item["name"]: bool(item["ok"]) for item in checks},
            }
        )
