from __future__ import annotations

import hashlib
import html
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

APP_TITLE = "NEXUS EDU XR · Diseñador de cursos"
ACTIVITY_TYPES = {
    "assignment": "Asignación",
    "discussion": "Foro de discusión",
    "quiz": "Examen / Google Forms",
    "project": "Proyecto",
    "presentation": "Presentación evaluada",
    "document": "Contenido / Google Docs",
    "slides": "Presentación / Google Slides",
    "meet": "Videoconferencia / Google Meet",
    "rubric": "Rúbrica o actividad evaluativa",
}
GOOGLE_NEW_URLS = {
    "document": "https://docs.new",
    "slides": "https://slides.new",
    "quiz": "https://forms.new",
    "meet": "https://meet.google.com/new",
}


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _is_postgres() -> bool:
    return _database_url().startswith(("postgresql://", "postgres://"))


@contextmanager
def _connection() -> Iterator[Any]:
    if _is_postgres():
        conn = psycopg.connect(_database_url(), row_factory=dict_row)
    else:
        path = Path(os.getenv("COURSE_BUILDER_DB", "data/course_builder.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _execute(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    if _is_postgres():
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def _schema() -> None:
    if _is_postgres():
        statements = [
            """CREATE TABLE IF NOT EXISTS cb_courses (
                id BIGSERIAL PRIMARY KEY,
                owner_key TEXT NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                term TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(owner_key, code)
            )""",
            """CREATE TABLE IF NOT EXISTS cb_modules (
                id BIGSERIAL PRIMARY KEY,
                course_id BIGINT NOT NULL REFERENCES cb_courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS cb_activities (
                id BIGSERIAL PRIMARY KEY,
                module_id BIGINT NOT NULL REFERENCES cb_modules(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                instructions TEXT NOT NULL DEFAULT '',
                points INTEGER NOT NULL DEFAULT 0,
                due_date TEXT NOT NULL DEFAULT '',
                resource_url TEXT NOT NULL DEFAULT '',
                is_graded BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""",
        ]
    else:
        statements = [
            """CREATE TABLE IF NOT EXISTS cb_courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_key TEXT NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                term TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(owner_key, code)
            )""",
            """CREATE TABLE IF NOT EXISTS cb_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL REFERENCES cb_courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS cb_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL REFERENCES cb_modules(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                instructions TEXT NOT NULL DEFAULT '',
                points INTEGER NOT NULL DEFAULT 0,
                due_date TEXT NOT NULL DEFAULT '',
                resource_url TEXT NOT NULL DEFAULT '',
                is_graded INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )""",
        ]
    with _connection() as conn:
        for statement in statements:
            _execute(conn, statement)


def _session_user(request: Request) -> tuple[str | None, str]:
    session: Mapping[str, Any] = getattr(request, "session", {}) or {}
    candidates: list[Mapping[str, Any]] = [session]
    for key in ("user", "profile", "account", "google_user"):
        value = session.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)

    email = ""
    user_id = ""
    display_name = ""
    for data in candidates:
        email = email or str(data.get("email") or "").strip().lower()
        user_id = user_id or str(data.get("user_id") or data.get("id") or data.get("sub") or "").strip()
        display_name = display_name or str(data.get("name") or data.get("display_name") or "").strip()

    if email:
        return f"email:{email}", display_name or email
    if user_id:
        return f"id:{user_id}", display_name or "Usuario NEXUS"
    if session:
        stable = repr(sorted((str(k), str(v)) for k, v in session.items() if "token" not in str(k).lower()))
        return "session:" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32], display_name or "Usuario NEXUS"
    return None, ""


def _csrf(request: Request) -> str:
    token = request.session.get("_course_builder_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["_course_builder_csrf"] = token
    return str(token)


def _verify_csrf(request: Request, submitted: str) -> bool:
    expected = str(request.session.get("_course_builder_csrf") or "")
    return bool(expected and submitted and secrets.compare_digest(expected, submitted))


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redirect(path: str, message: str = "") -> RedirectResponse:
    if message:
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}message={quote(message)}"
    return RedirectResponse(path, status_code=303)


def _layout(title: str, user_name: str, content: str, message: str = "") -> str:
    flash = f'<div class="flash" role="status">{_e(message)}</div>' if message else ""
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title>
<style>
:root{{--ink:#102c2c;--green:#006c55;--light:#f4f8f7;--line:#d8e4e1;--danger:#a52a2a}}
*{{box-sizing:border-box}} body{{margin:0;font-family:Inter,Arial,sans-serif;color:var(--ink);background:var(--light)}}
header{{background:white;border-bottom:1px solid var(--line);padding:16px 5%;display:flex;gap:20px;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:5}}
header a{{color:var(--green);font-weight:700;text-decoration:none}} main{{max-width:1200px;margin:28px auto;padding:0 20px 60px}}
.hero,.panel,.module,.activity{{background:white;border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 24px rgba(16,44,44,.05)}}
.hero{{padding:24px;margin-bottom:22px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}}
.panel{{padding:20px;margin-bottom:20px}} .module{{padding:18px;margin:18px 0}} .activity{{padding:14px;margin:10px 0}}
h1,h2,h3{{margin-top:0}} label{{font-weight:700;display:block;margin:12px 0 6px}} input,textarea,select{{width:100%;padding:11px;border:1px solid #aec5c0;border-radius:9px;font:inherit}} textarea{{min-height:90px;resize:vertical}}
.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}} button,.button{{display:inline-block;background:var(--green);color:white;border:0;border-radius:9px;padding:11px 15px;font-weight:700;text-decoration:none;cursor:pointer}} .button.secondary{{background:#e5f0ed;color:var(--ink)}} .danger{{background:var(--danger)}}
.actions{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}} .muted{{color:#58706c}} .flash{{background:#e5f6ef;border-left:5px solid var(--green);padding:12px;margin-bottom:18px;border-radius:8px}}
.badge{{display:inline-block;background:#e5f0ed;padding:4px 8px;border-radius:999px;font-size:.86rem}} .empty{{padding:24px;border:2px dashed #b8cbc7;border-radius:14px;text-align:center;color:#58706c}}
summary{{cursor:pointer;font-weight:800;color:var(--green)}} details{{margin-top:14px}} form.inline{{display:inline}} @media(max-width:650px){{header{{align-items:flex-start;flex-direction:column}}}}
</style></head>
<body><header><div><strong>NEXUS EDU XR</strong> · Diseñador de cursos</div><nav><a href="/">Panel</a> &nbsp; <a href="/course-studio">Cursos</a> &nbsp; <a href="/logout">Cerrar sesión</a></nav></header>
<main>{flash}{content}<p class="muted">Sesión: {_e(user_name)}</p></main></body></html>"""


def _course_counts(conn: Any, owner_key: str) -> list[dict[str, Any]]:
    cursor = _execute(conn, """
        SELECT c.id,c.code,c.title,c.description,c.term,c.created_at,
               COUNT(DISTINCT m.id) AS module_count,
               COUNT(DISTINCT a.id) AS activity_count
        FROM cb_courses c
        LEFT JOIN cb_modules m ON m.course_id=c.id
        LEFT JOIN cb_activities a ON a.module_id=m.id
        WHERE c.owner_key=?
        GROUP BY c.id,c.code,c.title,c.description,c.term,c.created_at
        ORDER BY c.created_at DESC
    """, (owner_key,))
    return [dict(row) for row in cursor.fetchall()]


def _owned_course(conn: Any, owner_key: str, course_id: int) -> dict[str, Any] | None:
    row = _execute(conn, "SELECT * FROM cb_courses WHERE id=? AND owner_key=?", (course_id, owner_key)).fetchone()
    return dict(row) if row else None


@router.get("/course-builder", include_in_schema=False)
async def course_builder_alias() -> RedirectResponse:
    return _redirect("/course-studio")


@router.get("/course-studio", response_class=HTMLResponse, include_in_schema=False)
async def course_studio(request: Request) -> HTMLResponse | RedirectResponse:
    owner_key, user_name = _session_user(request)
    if not owner_key:
        return _redirect("/login?next=/course-studio")
    _schema()
    token = _csrf(request)
    with _connection() as conn:
        courses = _course_counts(conn, owner_key)

    cards = "".join(f"""
    <article class="panel">
      <span class="badge">{_e(c['code'])}</span><h3>{_e(c['title'])}</h3>
      <p>{_e(c['description'])}</p><p class="muted">{_e(c['term'])} · {c['module_count']} módulos · {c['activity_count']} actividades</p>
      <div class="actions"><a class="button" href="/course-studio/courses/{c['id']}">Diseñar curso</a>
      <form class="inline" method="post" action="/course-studio/courses/{c['id']}/delete" onsubmit="return confirm('¿Eliminar este curso y todo su contenido?')"><input type="hidden" name="csrf" value="{token}"><button class="danger">Eliminar</button></form></div>
    </article>""" for c in courses)
    if not cards:
        cards = '<div class="empty">Todavía no hay cursos. Cree el primero con el formulario.</div>'

    content = f"""
    <section class="hero"><h1>Crear y organizar cursos</h1><p>Cree el curso, abra su estructura y añada módulos, asignaciones, foros, exámenes, proyectos y recursos de Google.</p></section>
    <section class="panel"><h2>Nuevo curso</h2>
      <form method="post" action="/course-studio/courses">
        <input type="hidden" name="csrf" value="{token}">
        <div class="row"><div><label for="code">Código</label><input id="code" name="code" required maxlength="40" placeholder="EDUC 5000"></div><div><label for="title">Título</label><input id="title" name="title" required maxlength="160"></div><div><label for="term">Término</label><input id="term" name="term" maxlength="80" placeholder="Agosto–Diciembre 2026"></div></div>
        <label for="description">Descripción</label><textarea id="description" name="description" maxlength="2000"></textarea>
        <button type="submit">Crear curso</button>
      </form>
    </section>
    <h2>Mis cursos</h2><section class="grid">{cards}</section>"""
    return HTMLResponse(_layout(APP_TITLE, user_name, content, request.query_params.get("message", "")))


@router.post("/course-studio/courses", include_in_schema=False)
async def create_course(request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    if not owner_key:
        return _redirect("/login?next=/course-studio")
    form = await request.form()
    if not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect("/course-studio", "La sesión del formulario expiró. Intente nuevamente.")
    code = str(form.get("code") or "").strip().upper()
    title = str(form.get("title") or "").strip()
    description = str(form.get("description") or "").strip()
    term = str(form.get("term") or "").strip()
    if not code or not title:
        return _redirect("/course-studio", "El código y el título son obligatorios.")
    _schema()
    try:
        with _connection() as conn:
            if _is_postgres():
                course_id = _execute(conn, "INSERT INTO cb_courses(owner_key,code,title,description,term) VALUES (?,?,?,?,?) RETURNING id", (owner_key, code, title, description, term)).fetchone()["id"]
            else:
                cursor = _execute(conn, "INSERT INTO cb_courses(owner_key,code,title,description,term,created_at) VALUES (?,?,?,?,?,?)", (owner_key, code, title, description, term, _now()))
                course_id = cursor.lastrowid
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            return _redirect("/course-studio", "Ya existe un curso con ese código.")
        raise
    return _redirect(f"/course-studio/courses/{course_id}", "Curso creado. Ahora añada los módulos.")


@router.get("/course-studio/courses/{course_id}", response_class=HTMLResponse, include_in_schema=False)
async def course_detail(course_id: int, request: Request) -> HTMLResponse | RedirectResponse:
    owner_key, user_name = _session_user(request)
    if not owner_key:
        return _redirect(f"/login?next=/course-studio/courses/{course_id}")
    _schema()
    token = _csrf(request)
    with _connection() as conn:
        course = _owned_course(conn, owner_key, course_id)
        if not course:
            return _redirect("/course-studio", "Curso no encontrado.")
        modules = [dict(row) for row in _execute(conn, "SELECT * FROM cb_modules WHERE course_id=? ORDER BY position,id", (course_id,)).fetchall()]
        for module in modules:
            module["activities"] = [dict(row) for row in _execute(conn, "SELECT * FROM cb_activities WHERE module_id=? ORDER BY id", (module["id"],)).fetchall()]

    module_html = []
    type_options = "".join(f'<option value="{_e(key)}">{_e(label)}</option>' for key, label in ACTIVITY_TYPES.items())
    for module in modules:
        activities = []
        for activity in module["activities"]:
            launch = ""
            if activity.get("resource_url"):
                launch = f'<a class="button secondary" target="_blank" rel="noopener" href="{_e(activity["resource_url"])}">Abrir recurso</a>'
            google_new = GOOGLE_NEW_URLS.get(str(activity.get("activity_type")))
            if google_new and not activity.get("resource_url"):
                launch = f'<a class="button secondary" target="_blank" rel="noopener" href="{google_new}">Crear en Google</a>'
            graded = "Evaluada" if bool(activity.get("is_graded")) else "Sin puntuación"
            activities.append(f"""
              <div class="activity"><strong>{_e(activity['title'])}</strong> <span class="badge">{_e(ACTIVITY_TYPES.get(activity['activity_type'], activity['activity_type']))}</span>
              <p>{_e(activity['instructions'])}</p><p class="muted">{graded} · {activity['points']} puntos · Fecha: {_e(activity['due_date'] or 'sin fecha')}</p>
              <div class="actions">{launch}<details><summary>Guardar o cambiar enlace</summary><form method="post" action="/course-studio/activities/{activity['id']}/resource"><input type="hidden" name="csrf" value="{token}"><label>URL de Docs, Slides, Forms, Meet u otro recurso</label><input type="url" name="resource_url" value="{_e(activity['resource_url'])}" placeholder="https://..."><button>Guardar enlace</button></form></details>
              <form class="inline" method="post" action="/course-studio/activities/{activity['id']}/delete" onsubmit="return confirm('¿Eliminar esta actividad?')"><input type="hidden" name="csrf" value="{token}"><button class="danger">Eliminar</button></form></div></div>""")
        activity_html = "".join(activities) or '<p class="muted">No hay actividades en este módulo.</p>'
        module_html.append(f"""
        <section class="module"><div class="actions" style="justify-content:space-between"><div><span class="badge">Módulo {module['position']}</span><h2>{_e(module['title'])}</h2><p>{_e(module['description'])}</p></div>
        <form method="post" action="/course-studio/modules/{module['id']}/delete" onsubmit="return confirm('¿Eliminar el módulo y sus actividades?')"><input type="hidden" name="csrf" value="{token}"><button class="danger">Eliminar módulo</button></form></div>
        <h3>Actividades</h3>{activity_html}
        <details><summary>+ Añadir actividad o evaluación</summary>
          <form method="post" action="/course-studio/modules/{module['id']}/activities">
            <input type="hidden" name="csrf" value="{token}"><label>Título</label><input name="title" required maxlength="180">
            <div class="row"><div><label>Tipo</label><select name="activity_type">{type_options}</select></div><div><label>Puntos</label><input type="number" name="points" min="0" max="10000" value="100"></div><div><label>Fecha de entrega</label><input type="datetime-local" name="due_date"></div></div>
            <label>Instrucciones</label><textarea name="instructions" maxlength="5000"></textarea><label>Enlace de Google o recurso (opcional)</label><input type="url" name="resource_url" placeholder="https://docs.google.com/...">
            <label><input style="width:auto" type="checkbox" name="is_graded" value="1" checked> Incluir en la evaluación del curso</label><button>Añadir actividad</button>
          </form></details></section>""")
    modules_rendered = "".join(module_html) or '<div class="empty">Este curso no tiene módulos. Añada el primero.</div>'
    content = f"""
      <section class="hero"><span class="badge">{_e(course['code'])}</span><h1>{_e(course['title'])}</h1><p>{_e(course['description'])}</p><a href="/course-studio">← Volver a mis cursos</a></section>
      <section class="panel"><h2>Nuevo módulo</h2><form method="post" action="/course-studio/courses/{course_id}/modules"><input type="hidden" name="csrf" value="{token}"><div class="row"><div><label>Título del módulo</label><input name="title" required maxlength="180"></div><div><label>Posición</label><input type="number" name="position" min="1" max="999" value="{len(modules)+1}"></div></div><label>Descripción</label><textarea name="description" maxlength="2000"></textarea><button>Crear módulo</button></form></section>
      <h2>Estructura del curso</h2>{modules_rendered}"""
    return HTMLResponse(_layout(f"{course['code']} · Course Studio", user_name, content, request.query_params.get("message", "")))


@router.post("/course-studio/courses/{course_id}/modules", include_in_schema=False)
async def create_module(course_id: int, request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    if not owner_key:
        return _redirect("/login")
    form = await request.form()
    if not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect(f"/course-studio/courses/{course_id}", "La sesión del formulario expiró.")
    title = str(form.get("title") or "").strip()
    description = str(form.get("description") or "").strip()
    try:
        position = max(1, int(str(form.get("position") or "1")))
    except ValueError:
        position = 1
    with _connection() as conn:
        if not _owned_course(conn, owner_key, course_id):
            return _redirect("/course-studio", "Curso no encontrado.")
        if _is_postgres():
            _execute(conn, "INSERT INTO cb_modules(course_id,title,description,position) VALUES (?,?,?,?)", (course_id, title, description, position))
        else:
            _execute(conn, "INSERT INTO cb_modules(course_id,title,description,position,created_at) VALUES (?,?,?,?,?)", (course_id, title, description, position, _now()))
    return _redirect(f"/course-studio/courses/{course_id}", "Módulo creado correctamente.")


def _module_owner(conn: Any, module_id: int) -> tuple[int, str] | None:
    row = _execute(conn, "SELECT m.course_id,c.owner_key FROM cb_modules m JOIN cb_courses c ON c.id=m.course_id WHERE m.id=?", (module_id,)).fetchone()
    return (int(row["course_id"]), str(row["owner_key"])) if row else None


def _activity_owner(conn: Any, activity_id: int) -> tuple[int, str] | None:
    row = _execute(conn, "SELECT m.course_id,c.owner_key FROM cb_activities a JOIN cb_modules m ON m.id=a.module_id JOIN cb_courses c ON c.id=m.course_id WHERE a.id=?", (activity_id,)).fetchone()
    return (int(row["course_id"]), str(row["owner_key"])) if row else None


@router.post("/course-studio/modules/{module_id}/activities", include_in_schema=False)
async def create_activity(module_id: int, request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    if not owner_key:
        return _redirect("/login")
    form = await request.form()
    if not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect("/course-studio", "La sesión del formulario expiró.")
    title = str(form.get("title") or "").strip()
    activity_type = str(form.get("activity_type") or "assignment").strip()
    instructions = str(form.get("instructions") or "").strip()
    due_date = str(form.get("due_date") or "").strip()
    resource_url = str(form.get("resource_url") or "").strip()
    is_graded = bool(form.get("is_graded"))
    try:
        points = min(10000, max(0, int(str(form.get("points") or "0"))))
    except ValueError:
        points = 0
    if activity_type not in ACTIVITY_TYPES:
        activity_type = "assignment"
    with _connection() as conn:
        ownership = _module_owner(conn, module_id)
        if not ownership or ownership[1] != owner_key:
            return _redirect("/course-studio", "Módulo no encontrado.")
        course_id = ownership[0]
        if _is_postgres():
            _execute(conn, "INSERT INTO cb_activities(module_id,title,activity_type,instructions,points,due_date,resource_url,is_graded) VALUES (?,?,?,?,?,?,?,?)", (module_id, title, activity_type, instructions, points, due_date, resource_url, is_graded))
        else:
            _execute(conn, "INSERT INTO cb_activities(module_id,title,activity_type,instructions,points,due_date,resource_url,is_graded,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (module_id, title, activity_type, instructions, points, due_date, resource_url, 1 if is_graded else 0, _now()))
    return _redirect(f"/course-studio/courses/{course_id}", "Actividad creada correctamente.")


@router.post("/course-studio/activities/{activity_id}/resource", include_in_schema=False)
async def update_resource(activity_id: int, request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    form = await request.form()
    if not owner_key or not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect("/login")
    resource_url = str(form.get("resource_url") or "").strip()
    with _connection() as conn:
        ownership = _activity_owner(conn, activity_id)
        if not ownership or ownership[1] != owner_key:
            return _redirect("/course-studio", "Actividad no encontrada.")
        _execute(conn, "UPDATE cb_activities SET resource_url=? WHERE id=?", (resource_url, activity_id))
    return _redirect(f"/course-studio/courses/{ownership[0]}", "Enlace guardado.")


@router.post("/course-studio/activities/{activity_id}/delete", include_in_schema=False)
async def delete_activity(activity_id: int, request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    form = await request.form()
    if not owner_key or not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect("/login")
    with _connection() as conn:
        ownership = _activity_owner(conn, activity_id)
        if not ownership or ownership[1] != owner_key:
            return _redirect("/course-studio")
        _execute(conn, "DELETE FROM cb_activities WHERE id=?", (activity_id,))
    return _redirect(f"/course-studio/courses/{ownership[0]}", "Actividad eliminada.")


@router.post("/course-studio/modules/{module_id}/delete", include_in_schema=False)
async def delete_module(module_id: int, request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    form = await request.form()
    if not owner_key or not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect("/login")
    with _connection() as conn:
        ownership = _module_owner(conn, module_id)
        if not ownership or ownership[1] != owner_key:
            return _redirect("/course-studio")
        _execute(conn, "DELETE FROM cb_modules WHERE id=?", (module_id,))
    return _redirect(f"/course-studio/courses/{ownership[0]}", "Módulo eliminado.")


@router.post("/course-studio/courses/{course_id}/delete", include_in_schema=False)
async def delete_course(course_id: int, request: Request) -> RedirectResponse:
    owner_key, _ = _session_user(request)
    form = await request.form()
    if not owner_key or not _verify_csrf(request, str(form.get("csrf") or "")):
        return _redirect("/login")
    with _connection() as conn:
        if _owned_course(conn, owner_key, course_id):
            _execute(conn, "DELETE FROM cb_courses WHERE id=? AND owner_key=?", (course_id, owner_key))
    return _redirect("/course-studio", "Curso eliminado.")
