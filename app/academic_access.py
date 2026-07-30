from __future__ import annotations

import html
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.admin_console as admin_console
from app.admin_authoring_v6 import _template_modules
from app.admin_console import audit, db, database_url, execute, require_admin, rows, utcnow
from app.unified_authoring import PREFIX, _course, _item, _module

AUTHOR_ROLES = {"instructor", "teaching_assistant", "course_builder", "facilitator"}
STUDENT_ROLES = {"student", "observer"}
ASSESSMENT_TYPES = {"assignment", "discussion", "quiz", "project", "presentation", "rubric", "assessment"}
COURSE_STATES = {"draft", "active", "archived"}


def esc(value: Any, *, attr: bool = False) -> str:
    return html.escape(str(value or ""), quote=attr)


def remove_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def safe_next(value: str, default: str = "/portal") -> str:
    value = value.strip()
    return value if value.startswith("/") and not value.startswith("//") else default


def login_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(f"/portal/login?next={quote(path, safe='/')}", status_code=303)


def google_user(request: Request) -> dict[str, Any] | None:
    user = request.session.get("user")
    if not isinstance(user, dict):
        return None
    email = str(user.get("email") or "").strip().lower()
    if not email:
        return None
    result = dict(user)
    result["email"] = email
    return result


def portal_css() -> str:
    return """
    :root{--navy:#101755;--indigo:#4338ca;--teal:#006b6b;--ink:#171a2b;--muted:#667085;--soft:#f7f8fc;--line:#d9deea;--danger:#a61b1b;--focus:#ffbf47}
    *{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--ink);font:16px/1.55 Inter,Segoe UI,Arial,sans-serif}a{color:#1457a6}
    header{background:linear-gradient(120deg,var(--navy),#1f2b7b 58%,var(--indigo));color:white;padding:18px 4vw;display:flex;align-items:center;gap:18px;flex-wrap:wrap}header strong{font-size:1.25rem}header nav{margin-left:auto;display:flex;gap:14px;flex-wrap:wrap}header a{color:white;font-weight:800}
    main{width:min(1240px,94%);margin:28px auto 60px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.card{background:white;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 10px 28px rgba(25,35,90,.08);margin:16px 0}.card h2,.card h3{margin-top:0}.badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#e8e9ff;color:#29227b;font-weight:800;font-size:.85rem}.notice{background:#eaf4ff;border-left:5px solid #2372c9;padding:14px}.success{background:#e8f7f2;border-left:5px solid var(--teal);padding:14px}.error{background:#ffeaea;border-left:5px solid var(--danger);padding:14px}
    label{display:block;font-weight:800;margin-top:12px}input,select,textarea{width:100%;padding:11px 12px;border:1px solid #8792a7;border-radius:10px;font:inherit;background:white}textarea{min-height:120px}.button,button{display:inline-block;border:0;border-radius:10px;padding:11px 16px;background:linear-gradient(90deg,#0875c9,var(--indigo));color:white;text-decoration:none;font-weight:800;cursor:pointer;margin:8px 5px 0 0}.button.secondary{background:var(--teal)}.button.ghost{background:#eef0ff;color:#282171}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--line)}th{background:#eef1f8}.module{border-left:5px solid var(--indigo)}.content-body img{max-width:100%;height:auto}.content-body iframe{width:100%;min-height:520px;border:1px solid var(--line);border-radius:12px}.muted{color:var(--muted)}
    a:focus,button:focus,input:focus,select:focus,textarea:focus{outline:4px solid var(--focus);outline-offset:2px}@media(max-width:760px){header nav{margin-left:0;width:100%}table{display:block;overflow:auto}}
    """


def portal_page(title: str, body: str, user: dict[str, Any] | None = None) -> HTMLResponse:
    nav = '<a href="/portal">Inicio</a>'
    account = ""
    if user:
        nav += '<a href="/portal/logout">Salir</a>'
        account = f'<span>{esc(user.get("name") or user.get("email"))}</span>'
    return HTMLResponse(
        f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · NUVEDRA</title><style>{portal_css()}</style></head><body><header><strong>NUVEDRA</strong><span>Espacio académico</span><nav>{nav}</nav>{account}</header><main>{body}</main></body></html>'''
    )


def enrollment(conn: Any, course_id: int, email: str) -> dict[str, Any] | None:
    found = rows(
        execute(
            conn,
            """SELECT e.*,c.course_code,c.title,c.description,c.status AS course_status,c.instructor_email
               FROM nexus_admin_enrollments e
               JOIN nexus_admin_courses c ON c.id=e.course_id
               WHERE e.course_id=? AND lower(e.user_email)=? AND e.status='active'""",
            (course_id, email.lower()),
        )
    )
    return found[0] if found else None


def require_course_role(conn: Any, course_id: int, email: str, allowed: set[str]) -> dict[str, Any]:
    result = enrollment(conn, course_id, email)
    if not result or str(result.get("course_role")) not in allowed:
        raise HTTPException(403, "No tiene permiso para acceder a este curso.")
    return result


def module_course_id(conn: Any, module_id: int) -> int:
    return int(_module(conn, module_id)["course_id"])


def item_bundle(conn: Any, item_id: int) -> tuple[int, dict[str, Any], dict[str, Any]]:
    item = _item(conn, item_id)
    module = _module(conn, int(item["module_id"]))
    return int(module["course_id"]), item, module


def ensure_academic_schema() -> None:
    pk = "INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY" if database_url().startswith("postgres") else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with db() as conn:
        execute(
            conn,
            f"""CREATE TABLE IF NOT EXISTS nuvedra_submissions (
                id {pk}, item_id INTEGER NOT NULL, student_email TEXT NOT NULL,
                response_text TEXT, response_url TEXT, status TEXT NOT NULL DEFAULT 'submitted',
                submitted_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(item_id,student_email)
            )""",
        )


def _insert_course(conn: Any, params: tuple[Any, ...]) -> int:
    sql = """INSERT INTO nexus_admin_courses
             (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?)"""
    if database_url().startswith("postgres"):
        row = execute(conn, sql + " RETURNING id", params).fetchone()
        return int(row[0])
    cursor = execute(conn, sql, params)
    return int(cursor.lastrowid)


def assign_professor(conn: Any, course_id: int, email: str) -> None:
    email = email.strip().lower()
    found = rows(execute(conn, "SELECT id FROM nexus_admin_enrollments WHERE course_id=? AND user_email=?", (course_id, email)))
    if found:
        execute(conn, "UPDATE nexus_admin_enrollments SET course_role='instructor',status='active' WHERE id=?", (found[0]["id"],))
    else:
        execute(
            conn,
            "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
            (course_id, email, "instructor", "active", utcnow()),
        )


def _selected(current: Any, candidate: str) -> str:
    return " selected" if str(current or "") == candidate else ""


def register_admin_course_creation(app: FastAPI) -> None:
    remove_route(app, f"{PREFIX}/courses", "POST")
    remove_route(app, f"{PREFIX}/courses/{{course_id}}", "GET")
    remove_route(app, f"{PREFIX}/courses/{{course_id}}/update", "POST")

    @app.post(f"{PREFIX}/courses", response_model=None)
    async def create_course(
        request: Request,
        course_code: str = Form(...),
        title: str = Form(...),
        description: str = Form(""),
        term: str = Form(""),
        instructor_email: str = Form(""),
        template: str = Form("blank"),
    ):
        admin = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        clean_title = title.strip()
        professor = instructor_email.strip().lower()
        if not code or not clean_title:
            raise HTTPException(400, "Código y título son obligatorios.")
        if not professor:
            raise HTTPException(400, "Asigne el correo del profesor que desarrollará el contenido.")
        with db() as conn:
            if rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE course_code=?", (code,))):
                raise HTTPException(409, "Ya existe un curso con ese código.")
            now = utcnow()
            course_id = _insert_course(
                conn,
                (code, clean_title, description.strip(), term.strip(), "draft", professor, admin["email"], now, now),
            )
            assign_professor(conn, course_id, professor)
            if template != "blank":
                for position, (module_title, module_description, outcomes) in enumerate(_template_modules(template, clean_title), 1):
                    execute(
                        conn,
                        """INSERT INTO nexus_modules
                           (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (course_id, module_title, module_description, outcomes, 60, position, "draft", now, now),
                    )
            audit(conn, admin["email"], "course_created_and_professor_assigned", "course", str(course_id), professor, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def admin_course_page(course_id: int, request: Request):
        admin = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(
                execute(
                    conn,
                    """SELECT m.*,(SELECT COUNT(*) FROM nexus_content_items i WHERE i.module_id=m.id) AS item_total
                       FROM nexus_modules m WHERE m.course_id=? ORDER BY m.position,m.id""",
                    (course_id,),
                )
            )
            enrollment_counts = rows(
                execute(
                    conn,
                    "SELECT course_role,COUNT(*) AS total FROM nexus_admin_enrollments WHERE course_id=? AND status='active' GROUP BY course_role",
                    (course_id,),
                )
            )
        counts = {str(row["course_role"]): int(row.get("total") or 0) for row in enrollment_counts}
        module_rows = "".join(
            f'<tr><td>{int(module.get("position") or 1)}. <strong>{esc(module["title"])}</strong></td><td>{esc(module.get("status") or "draft")}</td><td>{int(module.get("item_total") or 0)}</td><td><a href="{PREFIX}/modules/{module["id"]}">Revisar estructura</a></td></tr>'
            for module in modules
        ) or '<tr><td colspan="4">El profesor todavía no ha creado módulos.</td></tr>'
        body = f'''
        <p><a href="{PREFIX}">&larr; Todos los cursos</a></p>
        <h2>{esc(course["course_code"])}: {esc(course["title"])}</h2>
        <p class="notice"><strong>Separación de funciones:</strong> el administrador configura y asigna el curso; el profesor desarrolla módulos, contenido y evaluaciones desde <code>/portal</code>; el estudiante solo consulta lo publicado y responde evaluaciones.</p>
        <div class="grid">
          <section class="card">
            <h3>Configuración administrativa</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/update">
              <label>Código<input name="course_code" required maxlength="40" value="{esc(course["course_code"], attr=True)}"></label>
              <label>Título<input name="title" required maxlength="180" value="{esc(course["title"], attr=True)}"></label>
              <label>Descripción<textarea name="description">{esc(course.get("description"))}</textarea></label>
              <label>Periodo<input name="term" value="{esc(course.get("term"), attr=True)}"></label>
              <label>Profesor responsable<input type="email" name="instructor_email" required value="{esc(course.get("instructor_email"), attr=True)}"></label>
              <div class="grid">
                <label>Inicio<input type="date" name="start_date" value="{esc(course.get("start_date"), attr=True)}"></label>
                <label>Fin<input type="date" name="end_date" value="{esc(course.get("end_date"), attr=True)}"></label>
              </div>
              <label>Estado<select name="status"><option value="draft"{_selected(course.get("status"), "draft")}>Borrador</option><option value="active"{_selected(course.get("status"), "active")}>Activo para estudiantes</option><option value="archived"{_selected(course.get("status"), "archived")}>Archivado</option></select></label>
              <button>Guardar configuración</button>
            </form>
          </section>
          <section class="card">
            <h3>Asignaciones y acceso</h3>
            <p><strong>Profesor principal:</strong><br>{esc(course.get("instructor_email") or "Sin asignar")}</p>
            <p><span class="badge">{counts.get("instructor", 0)} profesores</span> <span class="badge">{counts.get("student", 0)} estudiantes</span> <span class="badge">{counts.get("observer", 0)} observadores</span></p>
            <a class="button" href="/admin/enrollments">Administrar matrículas</a>
            <a class="button secondary" href="{PREFIX}/innovation/courses/{course_id}">Calidad e innovación</a>
            <p>El profesor accede a <strong>/portal</strong> con el correo asignado. Los estudiantes también entran por <strong>/portal</strong>, pero reciben una vista de solo lectura con acceso a las evaluaciones.</p>
          </section>
        </div>
        <h2>Estructura desarrollada por el profesor</h2>
        <section class="card"><table><thead><tr><th>Módulo</th><th>Estado</th><th>Elementos</th><th>Supervisión</th></tr></thead><tbody>{module_rows}</tbody></table></section>
        '''
        return admin_console.page("Configuración del curso", body, admin)

    @app.post(f"{PREFIX}/courses/{{course_id}}/update", response_model=None)
    async def update_course(
        course_id: int,
        request: Request,
        course_code: str = Form(...),
        title: str = Form(...),
        description: str = Form(""),
        term: str = Form(""),
        instructor_email: str = Form(...),
        start_date: str = Form(""),
        end_date: str = Form(""),
        status: str = Form("draft"),
    ):
        admin = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        clean_title = title.strip()
        professor = instructor_email.strip().lower()
        if not code or not clean_title or not professor:
            raise HTTPException(400, "Código, título y profesor son obligatorios.")
        if status not in COURSE_STATES:
            raise HTTPException(400, "Estado del curso inválido.")
        if start_date and end_date and start_date > end_date:
            raise HTTPException(400, "La fecha final no puede ser anterior a la inicial.")
        with db() as conn:
            course = _course(conn, course_id)
            if rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE course_code=? AND id<>?", (code, course_id))):
                raise HTTPException(409, "Ya existe otro curso con ese código.")
            previous = str(course.get("instructor_email") or "").strip().lower()
            execute(
                conn,
                """UPDATE nexus_admin_courses SET course_code=?,title=?,description=?,term=?,status=?,instructor_email=?,start_date=?,end_date=?,updated_at=? WHERE id=?""",
                (code, clean_title, description.strip(), term.strip(), status, professor, start_date.strip() or None, end_date.strip() or None, utcnow(), course_id),
            )
            assign_professor(conn, course_id, professor)
            if previous and previous != professor:
                execute(
                    conn,
                    "UPDATE nexus_admin_enrollments SET status='inactive' WHERE course_id=? AND user_email=? AND course_role='instructor'",
                    (course_id, previous),
                )
            audit(conn, admin["email"], "course_configuration_updated", "course", str(course_id), f"{code}:{professor}:{status}", request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)
