from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

COOKIE_NAME = "nexus_admin_session"
SESSION_MAX_AGE = 60 * 60 * 8
ROLES = {"superadmin", "course_admin", "user_admin", "support", "auditor"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secret() -> str:
    value = os.getenv("NEXUS_SESSION_SECRET") or os.getenv("SECRET_KEY")
    if not value:
        raise RuntimeError("Configure NEXUS_SESSION_SECRET en Render.")
    return value


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="nexus-admin-v1")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = encoded.split("$", 2)
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=64)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./nexus.db")


@contextmanager
def db():
    url = database_url()
    if url.startswith("postgres"):
        if psycopg is None:
            raise RuntimeError("psycopg no está instalado")
        conn = psycopg.connect(url)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        path = url.removeprefix("sqlite:///")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def execute(conn, sql: str, params: tuple = ()):
    if database_url().startswith("postgres"):
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def rows(cur) -> list[dict[str, Any]]:
    data = cur.fetchall()
    if not data:
        return []
    if isinstance(data[0], sqlite3.Row):
        return [dict(x) for x in data]
    names = [d.name if hasattr(d, "name") else d[0] for d in cur.description]
    return [dict(zip(names, x)) for x in data]


def init_schema() -> None:
    statements = [
        """CREATE TABLE IF NOT EXISTS nexus_admin_users (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            email TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1, must_change_password INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, last_login TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_admin_courses (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            course_code TEXT UNIQUE NOT NULL, title TEXT NOT NULL, description TEXT,
            term TEXT, status TEXT NOT NULL DEFAULT 'draft', instructor_email TEXT,
            start_date TEXT, end_date TEXT, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_admin_enrollments (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            course_id INTEGER NOT NULL, user_email TEXT NOT NULL,
            course_role TEXT NOT NULL DEFAULT 'student', status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL, UNIQUE(course_id, user_email)
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_admin_audit (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            actor_email TEXT NOT NULL, action TEXT NOT NULL, entity_type TEXT,
            entity_id TEXT, details TEXT, ip_address TEXT, created_at TEXT NOT NULL
        )""",
    ]
    sqlite_statements = [s.replace("INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY", "INTEGER PRIMARY KEY AUTOINCREMENT") for s in statements]
    with db() as conn:
        for statement in (statements if database_url().startswith("postgres") else sqlite_statements):
            execute(conn, statement)
    bootstrap_admin()


def bootstrap_admin() -> None:
    email = os.getenv("NEXUS_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("NEXUS_BOOTSTRAP_ADMIN_PASSWORD", "")
    name = os.getenv("NEXUS_BOOTSTRAP_ADMIN_NAME", "Administrador NEXUS").strip()
    if not email or not password:
        return
    if len(password) < 12:
        raise RuntimeError("NEXUS_BOOTSTRAP_ADMIN_PASSWORD debe tener al menos 12 caracteres.")
    with db() as conn:
        existing = rows(execute(conn, "SELECT id FROM nexus_admin_users WHERE email=?", (email,)))
        if not existing:
            execute(conn, "INSERT INTO nexus_admin_users (email,full_name,password_hash,role,active,must_change_password,created_at) VALUES (?,?,?,?,?,?,?)",
                    (email, name, hash_password(password), "superadmin", 1, 1, utcnow()))
            audit(conn, email, "bootstrap_admin_created", "admin_user", email, "Cuenta inicial creada", "system")


def audit(conn, actor: str, action: str, entity_type: str = "", entity_id: str = "", details: str = "", ip: str = "") -> None:
    execute(conn, "INSERT INTO nexus_admin_audit (actor_email,action,entity_type,entity_id,details,ip_address,created_at) VALUES (?,?,?,?,?,?,?)",
            (actor, action, entity_type, entity_id, details, ip, utcnow()))


def session_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    with db() as conn:
        found = rows(execute(conn, "SELECT id,email,full_name,role,active,must_change_password FROM nexus_admin_users WHERE email=?", (payload.get("email"),)))
    return found[0] if found and found[0]["active"] else None


def require_admin(request: Request, allowed: set[str] | None = None) -> dict[str, Any]:
    user = session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Autenticación requerida")
    if allowed and user["role"] not in allowed and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Permiso insuficiente")
    return user


def page(title: str, body: str, user: dict[str, Any] | None = None) -> HTMLResponse:
    nav = ""
    if user:
        nav = f'''<nav><a href="/admin">Resumen</a><a href="/admin/courses">Cursos</a><a href="/admin/users">Usuarios</a><a href="/admin/enrollments">Matrículas</a><a href="/admin/audit">Auditoría</a><a href="/admin/backup">Respaldo</a><a href="/admin/logout">Salir</a></nav><p class="who">{html.escape(user['full_name'])} · {html.escape(user['role'])}</p>'''
    css = """
    :root{--navy:#102a43;--blue:#185adb;--ink:#172033;--muted:#52657a;--soft:#f3f7fb;--line:#cbd6e2;--focus:#ffbf47}
    *{box-sizing:border-box}body{margin:0;font:16px/1.5 Inter,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--soft)}
    header{background:var(--navy);color:white;padding:18px 4vw;display:flex;gap:24px;align-items:center;flex-wrap:wrap}header h1{font-size:1.25rem;margin:0}nav{display:flex;gap:14px;flex-wrap:wrap}nav a{color:white;font-weight:700}.who{margin-left:auto}
    main{width:min(1180px,92%);margin:28px auto}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:22px;margin:16px 0;box-shadow:0 8px 24px rgba(16,42,67,.07)}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}.metric strong{font-size:2rem;color:var(--blue);display:block}
    table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line)}th{background:#eaf1f8}
    label{font-weight:700;display:block;margin-top:12px}input,select,textarea{width:100%;padding:11px;border:1px solid #8093a7;border-radius:8px;font:inherit}textarea{min-height:90px}
    button,.button{display:inline-block;background:var(--blue);color:white;border:0;border-radius:9px;padding:11px 16px;font-weight:800;text-decoration:none;margin-top:14px;cursor:pointer}
    .danger{background:#a61b1b}.status{font-weight:800}.error{background:#ffe9e9;border-left:5px solid #a61b1b;padding:12px}.notice{background:#e7f1ff;border-left:5px solid var(--blue);padding:12px}
    a:focus,button:focus,input:focus,select:focus,textarea:focus{outline:4px solid var(--focus);outline-offset:2px}@media(max-width:700px){table{display:block;overflow:auto}.who{margin-left:0}}
    """
    return HTMLResponse(f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · NEXUS</title><style>{css}</style></head><body><header><h1>NEXUS EDU XR · Administración</h1>{nav}</header><main>{body}</main></body></html>''')


def register_admin_console(app: FastAPI) -> None:
    init_schema()

    @app.get("/admin/login", response_class=HTMLResponse)
    async def admin_login(request: Request, error: str = ""):
        if session_user(request):
            return RedirectResponse("/admin", status_code=303)
        message = '<p class="error">Credenciales inválidas.</p>' if error else ""
        return page("Acceso administrativo", f'''<section class="card" style="max-width:520px;margin:auto"><h2>Acceso administrativo</h2>{message}<p>Utilice la cuenta administrativa protegida de NEXUS.</p><form method="post" action="/admin/login"><label>Correo electrónico<input type="email" name="email" required autocomplete="username"></label><label>Contraseña<input type="password" name="password" required autocomplete="current-password"></label><button>Iniciar sesión</button></form></section>''')

    @app.post("/admin/login")
    async def admin_login_post(request: Request, email: str = Form(...), password: str = Form(...)):
        normalized = email.strip().lower()
        with db() as conn:
            found = rows(execute(conn, "SELECT * FROM nexus_admin_users WHERE email=?", (normalized,)))
            if not found or not found[0]["active"] or not verify_password(password, found[0]["password_hash"]):
                audit(conn, normalized or "unknown", "login_failed", "admin_user", normalized, "", request.client.host if request.client else "")
                return RedirectResponse("/admin/login?error=1", status_code=303)
            execute(conn, "UPDATE nexus_admin_users SET last_login=? WHERE email=?", (utcnow(), normalized))
            audit(conn, normalized, "login_success", "admin_user", normalized, "", request.client.host if request.client else "")
        response = RedirectResponse("/admin/password" if found[0]["must_change_password"] else "/admin", status_code=303)
        response.set_cookie(COOKIE_NAME, serializer().dumps({"email": normalized}), max_age=SESSION_MAX_AGE, httponly=True, secure=os.getenv("ENVIRONMENT", "production") != "development", samesite="lax")
        return response

    @app.get("/admin/logout")
    async def admin_logout():
        response = RedirectResponse("/admin/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response

    @app.get("/admin/password", response_class=HTMLResponse)
    async def change_password_page(request: Request):
        user = require_admin(request)
        return page("Cambiar contraseña", '''<section class="card" style="max-width:560px"><h2>Cambiar contraseña</h2><p class="notice">La contraseña inicial debe cambiarse antes de administrar la plataforma.</p><form method="post"><label>Nueva contraseña<input type="password" name="password" minlength="12" required></label><label>Confirmar contraseña<input type="password" name="confirm" minlength="12" required></label><button>Guardar contraseña</button></form></section>''', user)

    @app.post("/admin/password")
    async def change_password(request: Request, password: str = Form(...), confirm: str = Form(...)):
        user = require_admin(request)
        if password != confirm or len(password) < 12:
            raise HTTPException(400, "La contraseña debe coincidir y tener 12 caracteres o más")
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_users SET password_hash=?,must_change_password=0 WHERE email=?", (hash_password(password), user["email"]))
            audit(conn, user["email"], "password_changed", "admin_user", user["email"], "", request.client.host if request.client else "")
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin", response_class=HTMLResponse)
    async def dashboard(request: Request):
        user = require_admin(request)
        with db() as conn:
            metrics = {}
            for key, table in [("courses","nexus_admin_courses"),("users","nexus_admin_users"),("enrollments","nexus_admin_enrollments"),("events","nexus_admin_audit")]:
                metrics[key] = rows(execute(conn, f"SELECT COUNT(*) AS total FROM {table}"))[0]["total"]
            recent = rows(execute(conn, "SELECT actor_email,action,entity_type,created_at FROM nexus_admin_audit ORDER BY id DESC LIMIT 8"))
        recent_html = "".join(f"<tr><td>{html.escape(str(x['created_at']))}</td><td>{html.escape(x['actor_email'])}</td><td>{html.escape(x['action'])}</td><td>{html.escape(x.get('entity_type') or '')}</td></tr>" for x in recent)
        return page("Resumen", f'''<h2>Centro de administración</h2><p>Control institucional inspirado en las capacidades administrativas de un LMS empresarial, con permisos delegados y trazabilidad.</p><div class="grid"><div class="card metric"><strong>{metrics['courses']}</strong>Cursos</div><div class="card metric"><strong>{metrics['users']}</strong>Administradores</div><div class="card metric"><strong>{metrics['enrollments']}</strong>Matrículas</div><div class="card metric"><strong>{metrics['events']}</strong>Eventos auditados</div></div><section class="card"><h3>Actividad reciente</h3><table><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Entidad</th></tr></thead><tbody>{recent_html}</tbody></table></section>''', user)

    @app.get("/admin/courses", response_class=HTMLResponse)
    async def courses(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            data = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY id DESC"))
        items = "".join(f"<tr><td>{html.escape(x['course_code'])}</td><td>{html.escape(x['title'])}</td><td>{html.escape(x.get('term') or '')}</td><td class='status'>{html.escape(x['status'])}</td><td>{html.escape(x.get('instructor_email') or '')}</td><td><form method='post' action='/admin/courses/{x['id']}/status'><select name='status'><option>draft</option><option>active</option><option>completed</option><option>archived</option></select><button>Actualizar</button></form></td></tr>" for x in data)
        return page("Cursos", f'''<h2>Administración de cursos</h2><div class="grid"><section class="card"><h3>Crear curso</h3><form method="post" action="/admin/courses"><label>Código<input name="course_code" required></label><label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label><label>Periodo<input name="term" placeholder="2026-01"></label><label>Profesor<input type="email" name="instructor_email"></label><label>Estado<select name="status"><option value="draft">Borrador</option><option value="active">Activo</option></select></label><button>Crear curso</button></form></section><section class="card"><h3>Funciones disponibles</h3><p>Crear, activar, completar y archivar cursos. La próxima fase conectará copia de cursos, plantillas maestras y contenido del Course Studio.</p></section></div><section class="card"><table><thead><tr><th>Código</th><th>Curso</th><th>Periodo</th><th>Estado</th><th>Profesor</th><th>Administrar</th></tr></thead><tbody>{items}</tbody></table></section>''', user)

    @app.post("/admin/courses")
    async def create_course(request: Request, course_code: str = Form(...), title: str = Form(...), description: str = Form(""), term: str = Form(""), instructor_email: str = Form(""), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if status not in {"draft", "active"}:
            raise HTTPException(400, "Estado inválido")
        with db() as conn:
            execute(conn, "INSERT INTO nexus_admin_courses (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (course_code.strip(), title.strip(), description.strip(), term.strip(), instructor_email.strip().lower(), status, user["email"], utcnow(), utcnow()))
            audit(conn, user["email"], "course_created", "course", course_code, title, request.client.host if request.client else "")
        return RedirectResponse("/admin/courses", status_code=303)

    @app.post("/admin/courses/{course_id}/status")
    async def course_status(course_id: int, request: Request, status: str = Form(...)):
        user = require_admin(request, {"course_admin"})
        if status not in {"draft", "active", "completed", "archived"}:
            raise HTTPException(400, "Estado inválido")
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status=?,updated_at=? WHERE id=?", (status, utcnow(), course_id))
            audit(conn, user["email"], "course_status_changed", "course", str(course_id), status, request.client.host if request.client else "")
        return RedirectResponse("/admin/courses", status_code=303)

    @app.get("/admin/users", response_class=HTMLResponse)
    async def users_page(request: Request):
        user = require_admin(request, {"user_admin"})
        with db() as conn:
            data = rows(execute(conn, "SELECT id,email,full_name,role,active,created_at,last_login FROM nexus_admin_users ORDER BY id"))
        items = "".join(f"<tr><td>{html.escape(x['full_name'])}</td><td>{html.escape(x['email'])}</td><td>{html.escape(x['role'])}</td><td>{'Activo' if x['active'] else 'Suspendido'}</td><td>{html.escape(str(x.get('last_login') or ''))}</td></tr>" for x in data)
        options = "".join(f"<option value='{r}'>{r}</option>" for r in sorted(ROLES))
        return page("Usuarios", f'''<h2>Administración de usuarios y roles</h2><div class="grid"><section class="card"><h3>Crear administrador delegado</h3><form method="post" action="/admin/users"><label>Nombre<input name="full_name" required></label><label>Correo<input type="email" name="email" required></label><label>Rol<select name="role">{options}</select></label><label>Contraseña temporal<input type="password" name="password" minlength="12" required></label><button>Crear usuario</button></form></section><section class="card"><h3>Modelo de permisos</h3><p><b>superadmin:</b> control total. <b>course_admin:</b> cursos y matrículas. <b>user_admin:</b> cuentas y roles. <b>support:</b> soporte limitado. <b>auditor:</b> lectura de auditoría.</p></section></div><section class="card"><table><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th><th>Último acceso</th></tr></thead><tbody>{items}</tbody></table></section>''', user)

    @app.post("/admin/users")
    async def create_admin(request: Request, full_name: str = Form(...), email: str = Form(...), role: str = Form(...), password: str = Form(...)):
        user = require_admin(request, {"user_admin"})
        if role not in ROLES or len(password) < 12:
            raise HTTPException(400, "Rol o contraseña inválidos")
        normalized = email.strip().lower()
        with db() as conn:
            execute(conn, "INSERT INTO nexus_admin_users (email,full_name,password_hash,role,active,must_change_password,created_at) VALUES (?,?,?,?,?,?,?)", (normalized, full_name.strip(), hash_password(password), role, 1, 1, utcnow()))
            audit(conn, user["email"], "admin_user_created", "admin_user", normalized, role, request.client.host if request.client else "")
        return RedirectResponse("/admin/users", status_code=303)

    @app.get("/admin/enrollments", response_class=HTMLResponse)
    async def enrollments_page(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses_data = rows(execute(conn, "SELECT id,course_code,title FROM nexus_admin_courses ORDER BY title"))
            data = rows(execute(conn, "SELECT e.id,e.user_email,e.course_role,e.status,c.course_code,c.title FROM nexus_admin_enrollments e JOIN nexus_admin_courses c ON c.id=e.course_id ORDER BY e.id DESC"))
        opts = "".join(f"<option value='{x['id']}'>{html.escape(x['course_code'])} · {html.escape(x['title'])}</option>" for x in courses_data)
        items = "".join(f"<tr><td>{html.escape(x['course_code'])}</td><td>{html.escape(x['user_email'])}</td><td>{html.escape(x['course_role'])}</td><td>{html.escape(x['status'])}</td></tr>" for x in data)
        return page("Matrículas", f'''<h2>Matrículas y roles de curso</h2><section class="card"><form method="post" action="/admin/enrollments"><label>Curso<select name="course_id" required>{opts}</select></label><label>Correo del usuario<input type="email" name="user_email" required></label><label>Rol<select name="course_role"><option>student</option><option>instructor</option><option>teaching_assistant</option><option>course_builder</option><option>facilitator</option></select></label><button>Matricular</button></form></section><section class="card"><table><thead><tr><th>Curso</th><th>Usuario</th><th>Rol</th><th>Estado</th></tr></thead><tbody>{items}</tbody></table></section>''', user)

    @app.post("/admin/enrollments")
    async def create_enrollment(request: Request, course_id: int = Form(...), user_email: str = Form(...), course_role: str = Form("student")):
        user = require_admin(request, {"course_admin"})
        allowed = {"student", "instructor", "teaching_assistant", "course_builder", "facilitator"}
        if course_role not in allowed:
            raise HTTPException(400, "Rol de curso inválido")
        normalized = user_email.strip().lower()
        with db() as conn:
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, normalized, course_role, "active", utcnow()))
            audit(conn, user["email"], "enrollment_created", "course", str(course_id), f"{normalized}:{course_role}", request.client.host if request.client else "")
        return RedirectResponse("/admin/enrollments", status_code=303)

    @app.get("/admin/audit", response_class=HTMLResponse)
    async def audit_page(request: Request):
        user = require_admin(request, {"auditor"})
        with db() as conn:
            data = rows(execute(conn, "SELECT * FROM nexus_admin_audit ORDER BY id DESC LIMIT 500"))
        items = "".join(f"<tr><td>{html.escape(str(x['created_at']))}</td><td>{html.escape(x['actor_email'])}</td><td>{html.escape(x['action'])}</td><td>{html.escape(x.get('entity_type') or '')}</td><td>{html.escape(x.get('entity_id') or '')}</td><td>{html.escape(x.get('ip_address') or '')}</td></tr>" for x in data)
        return page("Auditoría", f'''<h2>Registro institucional de auditoría</h2><section class="card"><table><thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Entidad</th><th>ID</th><th>IP</th></tr></thead><tbody>{items}</tbody></table></section>''', user)

    @app.get("/admin/backup")
    async def backup(request: Request):
        user = require_admin(request, {"course_admin", "auditor"})
        with db() as conn:
            payload = {
                "generated_at": utcnow(),
                "courses": rows(execute(conn, "SELECT * FROM nexus_admin_courses")),
                "enrollments": rows(execute(conn, "SELECT * FROM nexus_admin_enrollments")),
                "audit": rows(execute(conn, "SELECT * FROM nexus_admin_audit")),
            }
            audit(conn, user["email"], "backup_exported", "system", "admin", "JSON export", request.client.host if request.client else "")
        return JSONResponse(payload, headers={"Content-Disposition": f"attachment; filename=nexus-backup-{datetime.now().date()}.json"})
