from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.admin_console as admin_console
import app.unified_authoring as unified_authoring
from app.admin_authoring_v6 import _template_modules, ensure_schema
from app.admin_console import audit, db, database_url, execute, rows, session_user, utcnow
from app.home_admin_access import _session_emails

PREFIX = "/admin/authoring"
ADMIN_EDITORS = {"superadmin", "course_admin"}
ACADEMIC_EDITORS = {"instructor"}
COURSE_EDITOR_ROLES = {"instructor", "teaching_assistant", "course_builder", "facilitator"}
COURSE_STATES = {"draft", "active", "completed", "archived"}


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def _replace_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def _platform_account(request: Request) -> dict[str, Any] | None:
    admin = session_user(request)
    if admin:
        role = str(admin.get("role") or "")
        if role in ADMIN_EDITORS:
            return {**admin, "is_admin": True}
        return None

    emails = sorted(_session_emails(dict(request.session)))
    if not emails:
        return None
    placeholders = ",".join("?" for _ in emails)
    with db() as conn:
        found = rows(
            execute(
                conn,
                f"SELECT id,email,full_name,role,active FROM nexus_admin_users "
                f"WHERE active=1 AND role='instructor' AND LOWER(email) IN ({placeholders}) "
                "ORDER BY id LIMIT 1",
                tuple(emails),
            )
        )
    return {**found[0], "is_admin": False} if found else None


def _course(conn: Any, course_id: int) -> dict[str, Any]:
    found = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,)))
    if not found:
        raise HTTPException(404, "Curso no encontrado.")
    return found[0]


def _module(conn: Any, module_id: int) -> dict[str, Any]:
    found = rows(execute(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,)))
    if not found:
        raise HTTPException(404, "Módulo no encontrado.")
    return found[0]


def _can_edit_course(conn: Any, principal: dict[str, Any], course: dict[str, Any]) -> bool:
    if principal.get("is_admin"):
        return True
    email = str(principal.get("email") or "").strip().lower()
    if not email or str(principal.get("role") or "") not in ACADEMIC_EDITORS:
        return False
    if str(course.get("instructor_email") or "").strip().lower() == email:
        return True
    assigned = rows(
        execute(
            conn,
            "SELECT id FROM nexus_admin_enrollments WHERE course_id=? AND LOWER(user_email)=? "
            "AND status='active' AND course_role IN ('instructor','teaching_assistant','course_builder','facilitator')",
            (course["id"], email),
        )
    )
    return bool(assigned)


def _require_editor(request: Request, course_id: int | None = None) -> dict[str, Any]:
    principal = _platform_account(request)
    if not principal:
        raise HTTPException(403, "Se requiere un rol de administrador académico o Instructor.")
    if course_id is not None:
        with db() as conn:
            course = _course(conn, course_id)
            if not _can_edit_course(conn, principal, course):
                raise HTTPException(403, "No tiene permiso para modificar este curso.")
    return principal


def require_authoring_access(request: Request, allowed: set[str] | None = None) -> dict[str, Any]:
    """Role-aware replacement used by the existing module/content routes."""
    admin = session_user(request)
    if admin:
        role = str(admin.get("role") or "")
        if role in ADMIN_EDITORS:
            return admin
        raise HTTPException(403, "Su rol administrativo no permite diseñar cursos.")

    principal = _platform_account(request)
    if not principal:
        raise HTTPException(403, "Se requiere un rol de Instructor o administrador académico.")

    course_id: int | None = None
    with db() as conn:
        if request.path_params.get("course_id") is not None:
            course_id = int(request.path_params["course_id"])
        elif request.path_params.get("module_id") is not None:
            module = _module(conn, int(request.path_params["module_id"]))
            course_id = int(module["course_id"])
        elif request.path_params.get("item_id") is not None:
            found = rows(
                execute(
                    conn,
                    "SELECT m.course_id FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id WHERE i.id=?",
                    (int(request.path_params["item_id"]),),
                )
            )
            if not found:
                raise HTTPException(404, "Contenido no encontrado.")
            course_id = int(found[0]["course_id"])
        if course_id is not None:
            course = _course(conn, course_id)
            if not _can_edit_course(conn, principal, course):
                raise HTTPException(403, "No tiene permiso para modificar este curso.")
    return principal


def _page(title: str, body: str, principal: dict[str, Any]) -> HTMLResponse:
    if principal.get("is_admin"):
        return admin_console.page(title, body, principal)
    css = """
    :root{--green:#007b5f;--navy:#09283d;--gold:#fed141;--line:#cbd7df;--soft:#f3f7f8;--ink:#172033}
    *{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--ink);font:16px/1.55 Inter,Segoe UI,Arial,sans-serif}
    header{background:linear-gradient(120deg,var(--navy),var(--green));color:white;padding:20px 5vw;display:flex;align-items:center;gap:20px;flex-wrap:wrap}header a{color:white;font-weight:800}
    main{width:min(1240px,92%);margin:28px auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:20px;margin:16px 0;box-shadow:0 8px 24px rgba(9,40,61,.07)}
    label{display:block;font-weight:800;margin-top:11px}input,textarea,select{width:100%;padding:10px;border:1px solid #8093a7;border-radius:8px;font:inherit}textarea{min-height:90px}button,.button{display:inline-block;background:var(--green);color:white;border:0;border-radius:9px;padding:10px 15px;font-weight:800;text-decoration:none;margin:9px 5px 0 0;cursor:pointer}.secondary{background:var(--navy)}.badge{display:inline-block;background:#e2f3ee;border-radius:999px;padding:3px 9px;font-weight:800}.notice{background:#e7f1ff;border-left:5px solid #185adb;padding:12px}
    """
    return HTMLResponse(
        f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_escape(title)} · NEXUS</title><style>{css}</style></head><body><header><strong>NEXUS EDU XR · Espacio del Instructor</strong><a href="/">Plataforma</a><a href="/course-studio">Mis cursos</a></header><main>{body}</main></body></html>'
    )


def _insert_course(conn: Any, values: tuple[Any, ...]) -> int:
    if database_url().startswith("postgres"):
        row = execute(
            conn,
            """INSERT INTO nexus_admin_courses
            (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
            values,
        ).fetchone()
        return int(row[0])
    cursor = execute(
        conn,
        """INSERT INTO nexus_admin_courses
        (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        values,
    )
    return int(cursor.lastrowid)


def _course_cards(courses: list[dict[str, Any]]) -> str:
    return "".join(
        f'<section class="card"><span class="badge">{_escape(course.get("status") or "draft")}</span>'
        f'<h3>{_escape(course["course_code"])} · {_escape(course["title"])}</h3>'
        f'<p>{_escape(course.get("description"))}</p>'
        f'<a class="button" href="{PREFIX}/courses/{course["id"]}">Editar curso</a></section>'
        for course in courses
    ) or '<p class="notice">No hay cursos disponibles. Cree el primero.</p>'


def register_course_management(app: FastAPI) -> None:
    ensure_schema()
    unified_authoring.require_admin = require_authoring_access

    for path, method in (
        ("/course-studio", "GET"),
        (PREFIX, "GET"),
        (f"{PREFIX}/courses", "POST"),
        (f"{PREFIX}/courses/{{course_id}}", "GET"),
        (f"{PREFIX}/courses/{{course_id}}/modules", "POST"),
    ):
        _replace_route(app, path, method)

    @app.get("/course-studio", response_class=HTMLResponse, response_model=None)
    @app.get(PREFIX, response_class=HTMLResponse, response_model=None)
    async def course_home(request: Request):
        principal = _require_editor(request)
        with db() as conn:
            if principal.get("is_admin"):
                courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC,id DESC"))
            else:
                email = str(principal.get("email") or "").lower()
                courses = rows(
                    execute(
                        conn,
                        """SELECT DISTINCT c.* FROM nexus_admin_courses c
                        LEFT JOIN nexus_admin_enrollments e ON e.course_id=c.id AND e.status='active'
                        WHERE LOWER(COALESCE(c.instructor_email,''))=? OR
                        (LOWER(COALESCE(e.user_email,''))=? AND e.course_role IN ('instructor','teaching_assistant','course_builder','facilitator'))
                        ORDER BY c.updated_at DESC,c.id DESC""",
                        (email, email),
                    )
                )
        default_instructor = _escape(principal.get("email") if not principal.get("is_admin") else "")
        body = f'''
        <h1>Course Studio</h1><p>Cree, edite y organice cursos y módulos desde el mismo espacio.</p>
        <div class="grid"><section class="card"><h2>Crear curso</h2>
        <form method="post" action="{PREFIX}/courses">
        <label>Código<input name="course_code" required maxlength="40"></label>
        <label>Título<input name="title" required maxlength="180"></label>
        <label>Descripción<textarea name="description"></textarea></label>
        <label>Periodo<input name="term" placeholder="Agosto-Diciembre 2026"></label>
        <label>Instructor<input type="email" name="instructor_email" value="{default_instructor}"></label>
        <label>Plantilla<select name="template"><option value="blank">Curso en blanco</option><option value="5e">Modelo 5E</option><option value="backward">Diseño inverso</option><option value="project">Aprendizaje por proyectos</option><option value="immersive">Aprendizaje inmersivo</option></select></label>
        <button>Crear curso</button></form></section>
        <section class="card"><h2>Flujo recomendado</h2><p>1. Cree el curso. 2. Edite su información. 3. Añada módulos. 4. Abra cada módulo para desarrollar contenido y evaluación.</p></section></div>
        <h2>Cursos editables</h2><div class="grid">{_course_cards(courses)}</div>
        '''
        return _page("Course Studio", body, principal)

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
        principal = _require_editor(request)
        code = course_code.strip().upper()
        clean_title = title.strip()
        if not code or not clean_title:
            raise HTTPException(400, "Código y título son obligatorios.")
        instructor = instructor_email.strip().lower()
        if not principal.get("is_admin"):
            instructor = str(principal.get("email") or "").strip().lower()
        with db() as conn:
            duplicate = rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE UPPER(course_code)=?", (code,)))
            if duplicate:
                raise HTTPException(409, "Ya existe un curso con ese código.")
            now = utcnow()
            course_id = _insert_course(
                conn,
                (code, clean_title, description.strip(), term.strip(), "draft", instructor, principal["email"], now, now),
            )
            if template != "blank":
                for position, (module_title, module_description, outcomes) in enumerate(_template_modules(template, clean_title), 1):
                    execute(
                        conn,
                        """INSERT INTO nexus_modules
                        (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (course_id, module_title, module_description, outcomes, 60, position, "draft", now, now),
                    )
            if instructor:
                existing = rows(execute(conn, "SELECT id FROM nexus_admin_enrollments WHERE course_id=? AND LOWER(user_email)=?", (course_id, instructor)))
                if not existing:
                    execute(
                        conn,
                        "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                        (course_id, instructor, "instructor", "active", now),
                    )
            audit(conn, principal["email"], "course_created", "course", str(course_id), code, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def edit_course_page(course_id: int, request: Request):
        principal = _require_editor(request, course_id)
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
        status_options = "".join(
            f'<option value="{state}"{" selected" if state == str(course.get("status") or "draft") else ""}>{state.title()}</option>'
            for state in ("draft", "active", "completed", "archived")
        )
        module_forms = "".join(
            f'''<section class="card"><form method="post" action="{PREFIX}/modules/{module["id"]}/update">
            <h3>Módulo {_escape(module["position"])}</h3>
            <label>Título<input name="title" value="{_escape(module["title"])}" required></label>
            <label>Descripción<textarea name="description">{_escape(module.get("description"))}</textarea></label>
            <label>Resultados<textarea name="learning_outcomes">{_escape(module.get("learning_outcomes"))}</textarea></label>
            <label>Duración<input type="number" name="estimated_minutes" min="1" value="{int(module.get("estimated_minutes") or 60)}"></label>
            <label>Posición<input type="number" name="position" min="1" value="{int(module.get("position") or 1)}"></label>
            <button>Guardar módulo</button><a class="button secondary" href="{PREFIX}/modules/{module["id"]}">Editar contenido y evaluación</a></form></section>'''
            for module in modules
        ) or '<p class="notice">Este curso todavía no tiene módulos.</p>'
        back = PREFIX if principal.get("is_admin") else "/course-studio"
        body = f'''
        <p><a href="{back}">&larr; Volver a cursos</a></p>
        <h1>{_escape(course["course_code"])} · {_escape(course["title"])}</h1>
        <div class="grid"><section class="card"><h2>Editar información del curso</h2>
        <form method="post" action="{PREFIX}/courses/{course_id}/update">
        <label>Código<input name="course_code" value="{_escape(course["course_code"])}" required></label>
        <label>Título<input name="title" value="{_escape(course["title"])}" required></label>
        <label>Descripción<textarea name="description">{_escape(course.get("description"))}</textarea></label>
        <label>Periodo<input name="term" value="{_escape(course.get("term"))}"></label>
        <label>Instructor<input type="email" name="instructor_email" value="{_escape(course.get("instructor_email"))}"></label>
        <label>Estado<select name="status">{status_options}</select></label>
        <button>Guardar cambios del curso</button></form></section>
        <section class="card"><h2>Crear módulo</h2><form method="post" action="{PREFIX}/courses/{course_id}/modules">
        <label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label>
        <label>Resultados<textarea name="learning_outcomes"></textarea></label><label>Duración<input type="number" name="estimated_minutes" min="1" value="60"></label>
        <label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label><button>Crear módulo</button></form></section></div>
        <h2>Módulos</h2><div class="grid">{module_forms}</div>
        '''
        return _page("Editar curso", body, principal)

    @app.post(f"{PREFIX}/courses/{{course_id}}/update", response_model=None)
    async def update_course(
        course_id: int,
        request: Request,
        course_code: str = Form(...),
        title: str = Form(...),
        description: str = Form(""),
        term: str = Form(""),
        instructor_email: str = Form(""),
        status: str = Form("draft"),
    ):
        principal = _require_editor(request, course_id)
        code = course_code.strip().upper()
        clean_title = title.strip()
        if not code or not clean_title:
            raise HTTPException(400, "Código y título son obligatorios.")
        if status not in COURSE_STATES:
            raise HTTPException(400, "Estado de curso inválido.")
        with db() as conn:
            course = _course(conn, course_id)
            duplicate = rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE UPPER(course_code)=? AND id<>?", (code, course_id)))
            if duplicate:
                raise HTTPException(409, "Otro curso utiliza ese código.")
            instructor = instructor_email.strip().lower()
            if not principal.get("is_admin"):
                instructor = str(course.get("instructor_email") or principal.get("email") or "").strip().lower()
            execute(
                conn,
                """UPDATE nexus_admin_courses SET course_code=?,title=?,description=?,term=?,status=?,
                instructor_email=?,updated_at=? WHERE id=?""",
                (code, clean_title, description.strip(), term.strip(), status, instructor, utcnow(), course_id),
            )
            audit(conn, principal["email"], "course_updated", "course", str(course_id), code, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.post(f"{PREFIX}/courses/{{course_id}}/modules", response_model=None)
    async def create_module(
        course_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
        position: int = Form(1),
    ):
        principal = _require_editor(request, course_id)
        if not title.strip():
            raise HTTPException(400, "El título del módulo es obligatorio.")
        with db() as conn:
            _course(conn, course_id)
            now = utcnow()
            execute(
                conn,
                """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (course_id, title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), "draft", now, now),
            )
            execute(conn, "UPDATE nexus_admin_courses SET updated_at=? WHERE id=?", (now, course_id))
            audit(conn, principal["email"], "module_created", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.post(f"{PREFIX}/modules/{{module_id}}/update", response_model=None)
    async def update_module(
        module_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
        position: int = Form(1),
    ):
        with db() as conn:
            module = _module(conn, module_id)
        principal = _require_editor(request, int(module["course_id"]))
        if not title.strip():
            raise HTTPException(400, "El título del módulo es obligatorio.")
        with db() as conn:
            now = utcnow()
            execute(
                conn,
                """UPDATE nexus_modules SET title=?,description=?,learning_outcomes=?,estimated_minutes=?,
                position=?,updated_at=? WHERE id=?""",
                (title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), now, module_id),
            )
            execute(conn, "UPDATE nexus_admin_courses SET updated_at=? WHERE id=?", (now, module["course_id"]))
            audit(conn, principal["email"], "module_updated", "module", str(module_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{module['course_id']}", status_code=303)

    print("Creación y edición unificada de cursos y módulos registrada.", flush=True)
