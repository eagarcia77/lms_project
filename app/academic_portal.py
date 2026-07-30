from __future__ import annotations

import html
import json
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.admin_authoring_v6 import _template_modules, safe_url, sanitize_html
from app.admin_console import audit, db, database_url, execute, require_admin, rows, utcnow
from app.google_api import TOKEN_STORE, build_authorization_url, exchange_code, google_get
from app.unified_authoring import ACTIVITY_TYPES, CONTENT_TYPES, PREFIX, _course, _insert_item, _item, _module

AUTHOR_ROLES = {"instructor", "teaching_assistant", "course_builder", "facilitator"}
STUDENT_ROLES = {"student", "observer"}
ASSESSMENT_TYPES = {"assignment", "discussion", "quiz", "project", "presentation", "rubric", "assessment"}
ITEM_TYPES = {**CONTENT_TYPES, **ACTIVITY_TYPES, "assessment": "Evaluación"}


def _escape(value: Any, *, quote_attr: bool = False) -> str:
    return html.escape(str(value or ""), quote=quote_attr)


def _remove_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def _portal_css() -> str:
    return """
    :root{--navy:#101755;--indigo:#4338ca;--teal:#006b6b;--amber:#ffb000;--ink:#171a2b;--muted:#667085;--soft:#f7f8fc;--line:#d9deea;--white:#fff;--danger:#a61b1b;--focus:#ffbf47}
    *{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--ink);font:16px/1.55 Inter,Segoe UI,Arial,sans-serif}a{color:#1457a6}
    header{background:linear-gradient(120deg,var(--navy),#1f2b7b 58%,var(--indigo));color:white;padding:18px 4vw;display:flex;align-items:center;gap:18px;flex-wrap:wrap}header strong{font-size:1.25rem}header nav{margin-left:auto;display:flex;gap:14px;flex-wrap:wrap}header a{color:white;font-weight:800}
    main{width:min(1240px,94%);margin:28px auto 60px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.card{background:white;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 10px 28px rgba(25,35,90,.08);margin:16px 0}.card h2,.card h3{margin-top:0}.badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#e8e9ff;color:#29227b;font-weight:800;font-size:.85rem}.notice{background:#eaf4ff;border-left:5px solid #2372c9;padding:14px}.success{background:#e8f7f2;border-left:5px solid var(--teal);padding:14px}.error{background:#ffeaea;border-left:5px solid var(--danger);padding:14px}
    label{display:block;font-weight:800;margin-top:12px}input,select,textarea{width:100%;padding:11px 12px;border:1px solid #8792a7;border-radius:10px;font:inherit;background:white}textarea{min-height:120px}.button,button{display:inline-block;border:0;border-radius:10px;padding:11px 16px;background:linear-gradient(90deg,#0875c9,var(--indigo));color:white;text-decoration:none;font-weight:800;cursor:pointer;margin:8px 5px 0 0}.button.secondary{background:var(--teal)}.button.ghost{background:#eef0ff;color:#282171}.danger{background:var(--danger)}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--line)}th{background:#eef1f8}.module{border-left:5px solid var(--indigo)}.content-body img{max-width:100%;height:auto}.content-body iframe{width:100%;min-height:520px;border:1px solid var(--line);border-radius:12px}.actions{display:flex;gap:8px;flex-wrap:wrap}.muted{color:var(--muted)}
    a:focus,button:focus,input:focus,select:focus,textarea:focus{outline:4px solid var(--focus);outline-offset:2px}@media(max-width:760px){header nav{margin-left:0;width:100%}table{display:block;overflow:auto}}
    """


def _portal_page(title: str, body: str, user: dict[str, Any] | None = None) -> HTMLResponse:
    account = ""
    nav = '<a href="/portal">Inicio</a>'
    if user:
        account = f'<span>{_escape(user.get("name") or user.get("email"))}</span>'
        nav += '<a href="/portal/logout">Salir</a>'
    return HTMLResponse(
        f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_escape(title)} · NUVEDRA</title><style>{_portal_css()}</style></head><body><header><strong>NUVEDRA</strong><span>Espacio académico</span><nav>{nav}</nav>{account}</header><main>{body}</main></body></html>'''
    )


def _google_user(request: Request) -> dict[str, Any] | None:
    user = request.session.get("user")
    if not isinstance(user, dict) or not str(user.get("email") or "").strip():
        return None
    user = dict(user)
    user["email"] = str(user["email"]).strip().lower()
    return user


def _login_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(f"/portal/login?next={quote(path, safe='/')}", status_code=303)


def _safe_next(value: str, default: str = "/portal") -> str:
    value = value.strip()
    return value if value.startswith("/") and not value.startswith("//") else default


def _course_enrollment(conn: Any, course_id: int, email: str) -> dict[str, Any] | None:
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


def _require_course_role(conn: Any, course_id: int, email: str, allowed: set[str]) -> dict[str, Any]:
    enrollment = _course_enrollment(conn, course_id, email)
    if not enrollment or str(enrollment.get("course_role")) not in allowed:
        raise HTTPException(403, "No tiene permiso para acceder a este curso.")
    return enrollment


def _module_course_id(conn: Any, module_id: int) -> int:
    module = _module(conn, module_id)
    return int(module["course_id"])


def _item_course_id(conn: Any, item_id: int) -> tuple[int, dict[str, Any], dict[str, Any]]:
    item = _item(conn, item_id)
    module = _module(conn, int(item["module_id"]))
    return int(module["course_id"]), item, module


def _ensure_schema() -> None:
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


def _insert_course_with_professor(
    conn: Any,
    *,
    code: str,
    title: str,
    description: str,
    term: str,
    instructor_email: str,
    created_by: str,
) -> int:
    params = (code, title, description, term, "draft", instructor_email or None, created_by, utcnow(), utcnow())
    sql = """INSERT INTO nexus_admin_courses
             (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?)"""
    if database_url().startswith("postgres"):
        row = execute(conn, sql + " RETURNING id", params).fetchone()
        return int(row[0])
    cursor = execute(conn, sql, params)
    return int(cursor.lastrowid)


def _assign_professor(conn: Any, course_id: int, email: str) -> None:
    email = email.strip().lower()
    if not email:
        return
    found = rows(execute(conn, "SELECT id FROM nexus_admin_enrollments WHERE course_id=? AND user_email=?", (course_id, email)))
    if found:
        execute(conn, "UPDATE nexus_admin_enrollments SET course_role='instructor',status='active' WHERE id=?", (found[0]["id"],))
    else:
        execute(
            conn,
            "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
            (course_id, email, "instructor", "active", utcnow()),
        )


def _item_type_options(selected: str = "page") -> str:
    return "".join(
        f'<option value="{key}"{" selected" if key == selected else ""}>{_escape(label)}</option>'
        for key, label in ITEM_TYPES.items()
    )


def register_academic_portal(app: FastAPI) -> None:
    _ensure_schema()

    # The administrator creates the course shell and assigns the professor.
    _remove_route(app, f"{PREFIX}/courses", "POST")

    @app.post(f"{PREFIX}/courses", response_model=None)
    async def admin_create_course(
        request: Request,
        course_code: str = Form(...),
        title: str = Form(...),
        description: str = Form(""),
        term: str = Form(""),
        instructor_email: str = Form(""),
        template: str = Form("blank"),
    ):
        user = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        clean_title = title.strip()
        professor = instructor_email.strip().lower()
        if not code or not clean_title:
            raise HTTPException(400, "Código y título son obligatorios.")
        if not professor:
            raise HTTPException(400, "Asigne el correo del profesor que desarrollará el contenido.")
        with db() as conn:
            duplicate = rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE course_code=?", (code,)))
            if duplicate:
                raise HTTPException(409, "Ya existe un curso con ese código.")
            course_id = _insert_course_with_professor(
                conn,
                code=code,
                title=clean_title,
                description=description.strip(),
                term=term.strip(),
                instructor_email=professor,
                created_by=user["email"],
            )
            _assign_professor(conn, course_id, professor)
            if template != "blank":
                for position, (module_title, module_description, outcomes) in enumerate(_template_modules(template, clean_title), 1):
                    execute(
                        conn,
                        """INSERT INTO nexus_modules
                           (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (course_id, module_title, module_description, outcomes, 60, position, "draft", utcnow(), utcnow()),
                    )
            audit(conn, user["email"], "course_created_and_professor_assigned", "course", str(course_id), professor, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    # Google connection with a deterministic return path.
    _remove_route(app, "/auth/google/callback", "GET")

    @app.get("/portal/login", response_model=None)
    async def portal_login(request: Request, next: str = "/portal"):
        target = _safe_next(next)
        request.session["post_google_redirect"] = target
        try:
            return RedirectResponse(build_authorization_url(request), status_code=303)
        except HTTPException as exc:
            return _portal_page(
                "Conectar Google",
                f'<section class="card"><h2>Google todavía no está configurado</h2><p>{_escape(exc.detail)}</p><p class="notice">El administrador debe configurar GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REDIRECT_URI en Render.</p><a class="button" href="/login">Volver</a></section>',
            )

    @app.get("/portal/google-connect", response_model=None)
    async def google_connect(request: Request, next: str = "/portal"):
        return await portal_login(request, next)

    @app.get("/auth/google/callback", response_model=None)
    async def portal_google_callback(request: Request, code: str, state: str):
        await exchange_code(request, code, state)
        target = _safe_next(str(request.session.pop("post_google_redirect", "/portal")))
        return RedirectResponse(target, status_code=303)

    @app.get("/portal/logout", response_model=None)
    async def portal_logout(request: Request):
        sid = request.session.get("sid")
        if sid:
            TOKEN_STORE.pop(str(sid), None)
        request.session.pop("sid", None)
        request.session.pop("user", None)
        return RedirectResponse("/login", status_code=303)

    @app.get("/portal", response_class=HTMLResponse, response_model=None)
    async def portal_home(request: Request):
        user = _google_user(request)
        if not user:
            return _portal_page(
                "Acceso académico",
                '''<section class="card" style="max-width:680px;margin:auto"><h2>Acceso para profesores y estudiantes</h2><p>Utilice su cuenta de Google institucional. NUVEDRA mostrará únicamente los cursos y funciones que el administrador le haya asignado.</p><a class="button" href="/portal/login">Continuar con Google</a></section>''',
            )
        with db() as conn:
            enrollments = rows(
                execute(
                    conn,
                    """SELECT e.*,c.course_code,c.title,c.description,c.status AS course_status
                       FROM nexus_admin_enrollments e JOIN nexus_admin_courses c ON c.id=e.course_id
                       WHERE lower(e.user_email)=? AND e.status='active'
                       ORDER BY c.title""",
                    (user["email"],),
                )
            )
        author_cards = "".join(
            f'<section class="card"><span class="badge">Profesor</span><h3>{_escape(row["course_code"])}: {_escape(row["title"])}</h3><p>{_escape(row.get("description"))}</p><a class="button" href="/faculty/courses/{row["course_id"]}">Crear y editar contenido</a></section>'
            for row in enrollments if str(row.get("course_role")) in AUTHOR_ROLES
        )
        student_cards = "".join(
            f'<section class="card"><span class="badge">Estudiante</span><h3>{_escape(row["course_code"])}: {_escape(row["title"])}</h3><p>{_escape(row.get("description"))}</p><a class="button secondary" href="/learn/courses/{row["course_id"]}">Entrar al curso</a></section>'
            for row in enrollments if str(row.get("course_role")) in STUDENT_ROLES and str(row.get("course_status")) == "active"
        )
        body = f'<h2>Mis cursos</h2><p class="muted">Las funciones dependen del rol asignado por el administrador.</p>{("<h3>Cursos que desarrollo</h3><div class=grid>"+author_cards+"</div>") if author_cards else ""}{("<h3>Cursos en los que estudio</h3><div class=grid>"+student_cards+"</div>") if student_cards else ""}'
        if not author_cards and not student_cards:
            body += '<p class="notice">Su cuenta está conectada, pero todavía no tiene un curso activo asignado. Comuníquese con el administrador.</p>'
        return _portal_page("Mis cursos", body, user)

    @app.get("/faculty/courses/{course_id}", response_class=HTMLResponse, response_model=None)
    async def faculty_course(course_id: int, request: Request):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/courses/{course_id}")
        with db() as conn:
            enrollment = _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                count = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module["id"],)))
                module["item_total"] = int(count[0].get("total") or 0) if count else 0
        module_cards = "".join(
            f'<section class="card module"><span class="badge">{_escape(module.get("status") or "draft")}</span><h3>{int(module.get("position") or 1)}. {_escape(module["title"])}</h3><p>{_escape(module.get("description"))}</p><p>{int(module.get("item_total") or 0)} elementos</p><a class="button" href="/faculty/modules/{module["id"]}">Editar módulo</a></section>'
            for module in modules
        ) or '<p class="notice">Todavía no hay módulos. Cree el primero.</p>'
        body = f'''<p><a href="/portal">&larr; Mis cursos</a></p><h2>{_escape(enrollment["course_code"])}: {_escape(enrollment["title"])}</h2><p>Como profesor, puede crear módulos, contenido y evaluaciones. La información administrativa del curso permanece bajo control del administrador.</p><section class="card"><h3>Crear módulo</h3><form method="post" action="/faculty/courses/{course_id}/modules"><label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label><label>Resultados de aprendizaje<textarea name="learning_outcomes"></textarea></label><div class="grid"><label>Duración estimada<input type="number" name="estimated_minutes" min="1" value="60"></label><label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label></div><button>Crear módulo</button></form></section><h2>Módulos</h2><div class="grid">{module_cards}</div>'''
        return _portal_page("Curso del profesor", body, user)

    @app.post("/faculty/courses/{course_id}/modules", response_model=None)
    async def faculty_create_module(
        course_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
        position: int = Form(1),
    ):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/courses/{course_id}")
        if not title.strip():
            raise HTTPException(400, "El título es obligatorio.")
        with db() as conn:
            _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            execute(
                conn,
                """INSERT INTO nexus_modules
                   (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (course_id, title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), "draft", utcnow(), utcnow()),
            )
            audit(conn, user["email"], "faculty_module_created", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/courses/{course_id}", status_code=303)

    @app.get("/faculty/modules/{module_id}", response_class=HTMLResponse, response_model=None)
    async def faculty_module(module_id: int, request: Request):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/modules/{module_id}")
        with db() as conn:
            module = _module(conn, module_id)
            course_id = int(module["course_id"])
            course = _course(conn, course_id)
            _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
        item_rows = "".join(
            f'<tr><td>{int(item.get("position") or 1)}</td><td><strong>{_escape(item["title"])}</strong><br><small>{_escape(item.get("item_type"))}</small></td><td>{_escape(item.get("status") or "draft")}</td><td><a href="/faculty/items/{item["id"]}/edit">Editar</a> · <a href="{PREFIX}/items/{item["id"]}/preview" target="_blank">Vista previa</a></td></tr>'
            for item in items
        ) or '<tr><td colspan="4">No hay contenido.</td></tr>'
        body = f'''<p><a href="/faculty/courses/{course_id}">&larr; Volver al curso</a></p><h2>{_escape(course["course_code"])} · {_escape(module["title"])}</h2><div class="grid"><section class="card"><h3>Información del módulo</h3><form method="post" action="/faculty/modules/{module_id}/update"><label>Título<input name="title" required value="{_escape(module["title"], quote_attr=True)}"></label><label>Descripción<textarea name="description">{_escape(module.get("description"))}</textarea></label><label>Resultados de aprendizaje<textarea name="learning_outcomes">{_escape(module.get("learning_outcomes"))}</textarea></label><div class="grid"><label>Duración<input type="number" name="estimated_minutes" min="1" value="{int(module.get("estimated_minutes") or 60)}"></label><label>Posición<input type="number" name="position" min="1" value="{int(module.get("position") or 1)}"></label></div><label>Estado<select name="status"><option value="draft"{" selected" if module.get("status")=="draft" else ""}>Borrador</option><option value="published"{" selected" if module.get("status")=="published" else ""}>Publicado</option><option value="hidden"{" selected" if module.get("status")=="hidden" else ""}>Oculto</option></select></label><button>Guardar módulo</button></form></section><section class="card"><h3>Añadir contenido o evaluación</h3><form method="post" action="/faculty/modules/{module_id}/items"><label>Tipo<select name="item_type">{_item_type_options()}</select></label><label>Título<input name="title" required></label><label>Contenido o instrucciones<textarea name="body_html" placeholder="Escriba el contenido, las instrucciones o la pregunta."></textarea></label><label>Enlace externo o de Google<input type="url" name="external_url" placeholder="https://docs.google.com/..."></label><label>URL para incrustar, WebXR o multimedia<input type="url" name="embed_url"></label><div class="grid"><label>Puntos<input type="number" name="points" min="0" step="0.01"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label></div><label>Alternativa accesible<textarea name="accessible_alternative" placeholder="Descripción, transcripción o actividad equivalente."></textarea></label><button>Añadir al módulo</button></form><p class="notice"><strong>Google Hub sencillo:</strong> cree el archivo en <a href="https://docs.new" target="_blank" rel="noopener">Docs</a>, <a href="https://slides.new" target="_blank" rel="noopener">Slides</a>, <a href="https://sheets.new" target="_blank" rel="noopener">Sheets</a> o <a href="https://forms.new" target="_blank" rel="noopener">Forms</a>; luego pegue el enlace compartido arriba.</p></section></div><h2>Contenido del módulo</h2><section class="card"><table><thead><tr><th>Orden</th><th>Elemento</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{item_rows}</tbody></table></section>'''
        return _portal_page("Editar módulo", body, user)

    @app.post("/faculty/modules/{module_id}/update", response_model=None)
    async def faculty_update_module(
        module_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
        position: int = Form(1),
        status: str = Form("draft"),
    ):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/modules/{module_id}")
        if status not in {"draft", "published", "hidden"}:
            raise HTTPException(400, "Estado inválido.")
        with db() as conn:
            course_id = _module_course_id(conn, module_id)
            _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            execute(conn, "UPDATE nexus_modules SET title=?,description=?,learning_outcomes=?,estimated_minutes=?,position=?,status=?,updated_at=? WHERE id=?", (title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), status, utcnow(), module_id))
            audit(conn, user["email"], "faculty_module_updated", "module", str(module_id), status, request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/modules/{module_id}", status_code=303)

    @app.post("/faculty/modules/{module_id}/items", response_model=None)
    async def faculty_create_item(
        module_id: int,
        request: Request,
        item_type: str = Form(...),
        title: str = Form(...),
        body_html: str = Form(""),
        external_url: str = Form(""),
        embed_url: str = Form(""),
        points: str = Form(""),
        due_at: str = Form(""),
        accessible_alternative: str = Form(""),
    ):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/modules/{module_id}")
        if item_type not in ITEM_TYPES:
            raise HTTPException(400, "Tipo inválido.")
        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Puntuación inválida.") from exc
        with db() as conn:
            course_id = _module_course_id(conn, module_id)
            _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            accessible = accessible_alternative.strip()
            content = sanitize_html(body_html)
            if accessible:
                content += f'<h3>Alternativa accesible</h3><p>{_escape(accessible)}</p>'
            _insert_item(
                conn,
                module_id,
                item_type,
                title.strip(),
                body_html=content,
                external_url=external_url,
                embed_url=embed_url,
                metadata={"accessible_alternative": accessible, "created_by": user["email"]},
                points=points_value,
                due_at=due_at,
                status="draft",
            )
            audit(conn, user["email"], "faculty_item_created", "module", str(module_id), item_type, request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/modules/{module_id}", status_code=303)

    @app.get("/faculty/items/{item_id}/edit", response_class=HTMLResponse, response_model=None)
    async def faculty_edit_item(item_id: int, request: Request):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/items/{item_id}/edit")
        with db() as conn:
            course_id, item, module = _item_course_id(conn, item_id)
            _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
        metadata = json.dumps(json.loads(str(item.get("metadata_json") or "{}")), ensure_ascii=False, indent=2)
        body = f'''<p><a href="/faculty/modules/{module["id"]}">&larr; Volver al módulo</a></p><h2>Editar contenido o evaluación</h2><section class="card"><form method="post" action="/faculty/items/{item_id}/edit"><label>Tipo<select name="item_type">{_item_type_options(str(item.get("item_type") or "page"))}</select></label><label>Título<input name="title" required value="{_escape(item["title"], quote_attr=True)}"></label><label>Contenido HTML<textarea name="body_html" style="min-height:260px">{_escape(item.get("body_html"))}</textarea></label><label>Enlace externo o Google<input type="url" name="external_url" value="{_escape(item.get("external_url"), quote_attr=True)}"></label><label>URL incrustada<input type="url" name="embed_url" value="{_escape(item.get("embed_url"), quote_attr=True)}"></label><label>Configuración avanzada JSON<textarea name="metadata_json">{_escape(metadata)}</textarea></label><div class="grid"><label>Puntos<input type="number" min="0" step="0.01" name="points" value="{_escape(item.get("points"), quote_attr=True)}"></label><label>Fecha límite<input type="datetime-local" name="due_at" value="{_escape(item.get("due_at"), quote_attr=True)}"></label><label>Orden<input type="number" min="1" name="position" value="{int(item.get("position") or 1)}"></label></div><label>Estado<select name="status"><option value="draft"{" selected" if item.get("status")=="draft" else ""}>Borrador</option><option value="published"{" selected" if item.get("status")=="published" else ""}>Publicado</option><option value="scheduled"{" selected" if item.get("status")=="scheduled" else ""}>Programado</option><option value="hidden"{" selected" if item.get("status")=="hidden" else ""}>Oculto</option></select></label><button>Guardar cambios</button></form></section>'''
        return _portal_page("Editar contenido", body, user)

    @app.post("/faculty/items/{item_id}/edit", response_model=None)
    async def faculty_update_item(
        item_id: int,
        request: Request,
        item_type: str = Form(...),
        title: str = Form(...),
        body_html: str = Form(""),
        external_url: str = Form(""),
        embed_url: str = Form(""),
        metadata_json: str = Form("{}"),
        points: str = Form(""),
        due_at: str = Form(""),
        position: int = Form(1),
        status: str = Form("draft"),
    ):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/faculty/items/{item_id}/edit")
        if item_type not in ITEM_TYPES or status not in {"draft", "published", "scheduled", "hidden"}:
            raise HTTPException(400, "Tipo o estado inválido.")
        try:
            metadata = json.loads(metadata_json or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "El JSON no es válido.") from exc
        if not isinstance(metadata, dict):
            raise HTTPException(400, "El JSON debe ser un objeto.")
        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Puntuación inválida.") from exc
        with db() as conn:
            course_id, item, module = _item_course_id(conn, item_id)
            _require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            execute(
                conn,
                """UPDATE nexus_content_items SET item_type=?,title=?,body_html=?,external_url=?,embed_url=?,metadata_json=?,points=?,due_at=?,position=?,status=?,updated_at=? WHERE id=?""",
                (item_type, title.strip(), sanitize_html(body_html), safe_url(external_url) or None, safe_url(embed_url) or None, json.dumps(metadata, ensure_ascii=False), points_value, due_at.strip() or None, max(1, position), status, utcnow(), item_id),
            )
            audit(conn, user["email"], "faculty_item_updated", "item", str(item_id), status, request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/modules/{module['id']}", status_code=303)

    @app.get("/learn/courses/{course_id}", response_class=HTMLResponse, response_model=None)
    async def student_course(course_id: int, request: Request):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/learn/courses/{course_id}")
        with db() as conn:
            enrollment = _require_course_role(conn, course_id, user["email"], STUDENT_ROLES)
            if str(enrollment.get("course_status")) != "active":
                raise HTTPException(403, "El curso todavía no está disponible.")
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? AND status='published' ORDER BY position,id", (course_id,)))
            for module in modules:
                module["items"] = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? AND status='published' ORDER BY position,id", (module["id"],)))
        modules_html = "".join(
            f'<section class="card module"><h3>{int(module.get("position") or 1)}. {_escape(module["title"])}</h3><p>{_escape(module.get("description"))}</p><ul>{"".join(f"<li><a href=/learn/items/{item[\"id\"]}>{_escape(item[\"title\"])}</a> <small>({_escape(item.get(\"item_type\"))})</small></li>" for item in module["items"]) or "<li>No hay contenido publicado.</li>"}</ul></section>'
            for module in modules
        ) or '<p class="notice">El profesor todavía no ha publicado módulos.</p>'
        return _portal_page("Curso", f'<p><a href="/portal">&larr; Mis cursos</a></p><h2>{_escape(enrollment["course_code"])}: {_escape(enrollment["title"])}</h2><p>{_escape(enrollment.get("description"))}</p>{modules_html}', user)

    @app.get("/learn/items/{item_id}", response_class=HTMLResponse, response_model=None)
    async def student_item(item_id: int, request: Request):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/learn/items/{item_id}")
        with db() as conn:
            course_id, item, module = _item_course_id(conn, item_id)
            _require_course_role(conn, course_id, user["email"], STUDENT_ROLES)
            if str(item.get("status")) != "published" or str(module.get("status")) != "published":
                raise HTTPException(403, "El contenido no está publicado.")
            submissions = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, user["email"])))
        external = f'<p><a class="button secondary" href="{_escape(item.get("external_url"), quote_attr=True)}" target="_blank" rel="noopener">Abrir recurso</a></p>' if item.get("external_url") else ""
        embed = f'<iframe src="{_escape(item.get("embed_url"), quote_attr=True)}" title="{_escape(item.get("title"), quote_attr=True)}" allow="fullscreen; xr-spatial-tracking"></iframe>' if item.get("embed_url") else ""
        assessment = ""
        if str(item.get("item_type")) in ASSESSMENT_TYPES and str(_course_enrollment.__name__):
            existing = submissions[0] if submissions else {}
            assessment = f'''<section class="card"><h3>Responder evaluación</h3>{'<p class="success">Su respuesta está guardada. Puede actualizarla mientras la evaluación permanezca disponible.</p>' if submissions else ''}<form method="post" action="/learn/items/{item_id}/submit"><label>Respuesta<textarea name="response_text" required>{_escape(existing.get("response_text"))}</textarea></label><label>Enlace de evidencia (opcional)<input type="url" name="response_url" value="{_escape(existing.get("response_url"), quote_attr=True)}"></label><button>Guardar y entregar</button></form></section>'''
        return _portal_page("Contenido", f'<p><a href="/learn/courses/{course_id}">&larr; Volver al curso</a></p><section class="card content-body"><span class="badge">{_escape(item.get("item_type"))}</span><h2>{_escape(item["title"])}</h2>{item.get("body_html") or ""}{external}{embed}</section>{assessment}', user)

    @app.post("/learn/items/{item_id}/submit", response_model=None)
    async def student_submit(item_id: int, request: Request, response_text: str = Form(...), response_url: str = Form("")):
        user = _google_user(request)
        if not user:
            return _login_redirect(f"/learn/items/{item_id}")
        clean_response = response_text.strip()
        if not clean_response:
            raise HTTPException(400, "La respuesta no puede estar vacía.")
        with db() as conn:
            course_id, item, module = _item_course_id(conn, item_id)
            enrollment = _require_course_role(conn, course_id, user["email"], {"student"})
            if str(item.get("item_type")) not in ASSESSMENT_TYPES or str(item.get("status")) != "published" or str(module.get("status")) != "published" or str(enrollment.get("course_status")) != "active":
                raise HTTPException(403, "Esta evaluación no está disponible.")
            url = safe_url(response_url) or None
            found = rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, user["email"])))
            if found:
                execute(conn, "UPDATE nuvedra_submissions SET response_text=?,response_url=?,status='submitted',updated_at=? WHERE id=?", (clean_response, url, utcnow(), found[0]["id"]))
            else:
                execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)", (item_id, user["email"], clean_response, url, "submitted", utcnow(), utcnow()))
            audit(conn, user["email"], "student_assessment_submitted", "item", str(item_id), "submitted", request.client.host if request.client else "")
        return RedirectResponse(f"/learn/items/{item_id}", status_code=303)

    # Replace the fragile Drive selector with a friendly, optional Google workflow.
    _remove_route(app, f"{PREFIX}/modules/{{module_id}}/drive", "GET")

    @app.get(f"{PREFIX}/modules/{{module_id}}/drive", response_class=HTMLResponse, response_model=None)
    async def safe_drive_selector(module_id: int, request: Request):
        admin = require_admin(request, {"course_admin"})
        with db() as conn:
            module = _module(conn, module_id)
        files_html = ""
        message = ""
        if request.session.get("sid"):
            try:
                payload = await google_get(request, "https://www.googleapis.com/drive/v3/files", params={"q": "trashed=false", "pageSize": 30, "orderBy": "modifiedTime desc", "fields": "files(id,name,mimeType,webViewLink,modifiedTime)"})
                files_html = "".join(
                    f'<section class="card"><h3>{_escape(file.get("name") or "Archivo")}</h3><p>{_escape(file.get("mimeType"))}</p><form method="post" action="{PREFIX}/modules/{module_id}/drive-link"><input type="hidden" name="file_id" value="{_escape(file.get("id"), quote_attr=True)}"><input type="hidden" name="title" value="{_escape(file.get("name"), quote_attr=True)}"><input type="hidden" name="mime_type" value="{_escape(file.get("mimeType"), quote_attr=True)}"><input type="hidden" name="web_view_link" value="{_escape(file.get("webViewLink"), quote_attr=True)}"><button>Vincular</button></form></section>'
                    for file in payload.get("files", [])
                ) or '<p class="notice">Google Drive no devolvió archivos.</p>'
            except HTTPException as exc:
                message = f'<p class="error">No se pudo leer Google Drive: {_escape(exc.detail)}</p>'
        else:
            message = '<p class="notice">Google Drive es opcional. Conecte Google para seleccionar archivos o simplemente pegue un enlace compartido.</p>'
        body = f'''<p><a href="{PREFIX}/modules/{module_id}">&larr; Volver al módulo</a></p><h2>Google Hub sencillo</h2>{message}<div class="grid"><section class="card"><h3>Opción 1: pegar enlace compartido</h3><form method="post" action="{PREFIX}/modules/{module_id}/google-link"><label>Tipo<select name="kind"><option value="document">Google Docs</option><option value="presentation">Google Slides</option><option value="spreadsheet">Google Sheets</option><option value="assessment">Google Forms</option><option value="video">Google Meet o video</option></select></label><label>Título<input name="title" required></label><label>Enlace compartido<input type="url" name="url" required></label><button>Vincular al módulo</button></form></section><section class="card"><h3>Opción 2: seleccionar desde Drive</h3><a class="button" href="/portal/google-connect?next={quote(f'{PREFIX}/modules/{module_id}/drive', safe='/')}">Conectar Google</a><p>La cuenta de Google queda separada de la cuenta administrativa y solo se utiliza para seleccionar o crear recursos.</p></section></div><div class="grid">{files_html}</div>'''
        return _portal_page("Google Drive", body, admin)

    @app.post(f"{PREFIX}/modules/{{module_id}}/google-link", response_model=None)
    async def admin_google_link(module_id: int, request: Request, kind: str = Form(...), title: str = Form(...), url: str = Form(...)):
        admin = require_admin(request, {"course_admin"})
        if kind not in {"document", "presentation", "spreadsheet", "assessment", "video"}:
            raise HTTPException(400, "Tipo de recurso inválido.")
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, kind, title.strip(), external_url=url, metadata={"source": "google_link", "linked_by": admin["email"]})
            audit(conn, admin["email"], "google_link_added", "module", str(module_id), kind, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)

    print("Portal académico por roles registrado: administrador, profesor y estudiante.", flush=True)
