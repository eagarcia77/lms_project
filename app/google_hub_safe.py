from __future__ import annotations

from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.academic_access import AUTHOR_ROLES, STUDENT_ROLES, esc, google_user, portal_page, remove_route, safe_next
from app.admin_console import audit, db, require_admin
from app.google_api import TOKEN_STORE, build_authorization_url, exchange_code, google_get
from app.unified_authoring import PREFIX, _insert_item, _module


def register_portal_home_and_google(app: FastAPI) -> None:
    remove_route(app, "/auth/google/callback", "GET")

    @app.get("/portal/login", response_model=None)
    async def portal_login(request: Request, next: str = "/portal"):
        target = safe_next(next)
        request.session["post_google_redirect"] = target
        try:
            return RedirectResponse(build_authorization_url(request), status_code=303)
        except HTTPException as exc:
            body = f'<section class="card"><h2>Google todavía no está configurado</h2><p>{esc(exc.detail)}</p><p class="notice">El administrador debe configurar GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REDIRECT_URI en Render.</p><a class="button" href="/login">Volver</a></section>'
            return portal_page("Conectar Google", body)

    @app.get("/portal/google-connect", response_model=None)
    async def google_connect(request: Request, next: str = "/portal"):
        return await portal_login(request, next)

    @app.get("/auth/google/callback", response_model=None)
    async def google_callback(request: Request, code: str, state: str):
        await exchange_code(request, code, state)
        target = safe_next(str(request.session.pop("post_google_redirect", "/portal")))
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
        user = google_user(request)
        if not user:
            body = '''<section class="card" style="max-width:680px;margin:auto"><h2>Acceso para profesores y estudiantes</h2><p>Utilice su cuenta de Google institucional. NUVEDRA mostrará únicamente los cursos y funciones asignados por el administrador.</p><a class="button" href="/portal/login">Continuar con Google</a></section>'''
            return portal_page("Acceso académico", body)
        from app.admin_console import execute, rows
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
            f'<section class="card"><span class="badge">Profesor</span><h3>{esc(row["course_code"])}: {esc(row["title"])}</h3><p>{esc(row.get("description"))}</p><a class="button" href="/faculty/courses/{row["course_id"]}">Crear y editar contenido</a></section>'
            for row in enrollments if str(row.get("course_role")) in AUTHOR_ROLES
        )
        student_cards = "".join(
            f'<section class="card"><span class="badge">Estudiante</span><h3>{esc(row["course_code"])}: {esc(row["title"])}</h3><p>{esc(row.get("description"))}</p><a class="button secondary" href="/learn/courses/{row["course_id"]}">Entrar al curso</a></section>'
            for row in enrollments if str(row.get("course_role")) in STUDENT_ROLES and str(row.get("course_status")) == "active"
        )
        body = '<h2>Mis cursos</h2><p class="muted">Las funciones dependen del rol asignado por el administrador.</p>'
        if author_cards:
            body += f'<h3>Cursos que desarrollo</h3><div class="grid">{author_cards}</div>'
        if student_cards:
            body += f'<h3>Cursos en los que estudio</h3><div class="grid">{student_cards}</div>'
        if not author_cards and not student_cards:
            body += '<p class="notice">Su cuenta está conectada, pero todavía no tiene un curso activo asignado. Comuníquese con el administrador.</p>'
        return portal_page("Mis cursos", body, user)

    remove_route(app, f"{PREFIX}/modules/{{module_id}}/drive", "GET")

    @app.get(f"{PREFIX}/modules/{{module_id}}/drive", response_class=HTMLResponse, response_model=None)
    async def safe_drive_selector(module_id: int, request: Request):
        admin = require_admin(request, {"course_admin"})
        with db() as conn:
            _module(conn, module_id)
        files_html = ""
        message = ""
        if request.session.get("sid"):
            try:
                payload = await google_get(
                    request,
                    "https://www.googleapis.com/drive/v3/files",
                    params={"q": "trashed=false", "pageSize": 30, "orderBy": "modifiedTime desc", "fields": "files(id,name,mimeType,webViewLink,modifiedTime)"},
                )
                cards: list[str] = []
                for file in payload.get("files", []):
                    cards.append(
                        f'<section class="card"><h3>{esc(file.get("name") or "Archivo")}</h3><p>{esc(file.get("mimeType"))}</p><form method="post" action="{PREFIX}/modules/{module_id}/drive-link"><input type="hidden" name="file_id" value="{esc(file.get("id"), attr=True)}"><input type="hidden" name="title" value="{esc(file.get("name"), attr=True)}"><input type="hidden" name="mime_type" value="{esc(file.get("mimeType"), attr=True)}"><input type="hidden" name="web_view_link" value="{esc(file.get("webViewLink"), attr=True)}"><button>Vincular</button></form></section>'
                    )
                files_html = "".join(cards) or '<p class="notice">Google Drive no devolvió archivos.</p>'
            except HTTPException as exc:
                message = f'<p class="error">No se pudo leer Google Drive: {esc(exc.detail)}</p>'
            except Exception:
                message = '<p class="error">Google Drive no respondió correctamente. Puede continuar pegando el enlace compartido.</p>'
        else:
            message = '<p class="notice">Google Drive es opcional. Conecte Google para seleccionar archivos o simplemente pegue un enlace compartido.</p>'
        return_path = quote(f"{PREFIX}/modules/{module_id}/drive", safe="/")
        body = f'''<p><a href="{PREFIX}/modules/{module_id}">&larr; Volver al módulo</a></p><h2>Google Hub sencillo</h2>{message}<div class="grid"><section class="card"><h3>Opción 1: pegar enlace compartido</h3><form method="post" action="{PREFIX}/modules/{module_id}/google-link"><label>Tipo<select name="kind"><option value="document">Google Docs</option><option value="presentation">Google Slides</option><option value="spreadsheet">Google Sheets</option><option value="assessment">Google Forms</option><option value="video">Google Meet o video</option></select></label><label>Título<input name="title" required></label><label>Enlace compartido<input type="url" name="url" required></label><button>Vincular al módulo</button></form></section><section class="card"><h3>Opción 2: seleccionar desde Drive</h3><a class="button" href="/portal/google-connect?next={return_path}">Conectar Google</a><p>La conexión con Google es independiente de la cuenta administrativa y solamente se usa para seleccionar o crear recursos.</p></section></div><div class="grid">{files_html}</div>'''
        return portal_page("Google Drive", body, admin)

    @app.post(f"{PREFIX}/modules/{{module_id}}/google-link", response_model=None)
    async def add_google_link(module_id: int, request: Request, kind: str = Form(...), title: str = Form(...), url: str = Form(...)):
        admin = require_admin(request, {"course_admin"})
        if kind not in {"document", "presentation", "spreadsheet", "assessment", "video"}:
            raise HTTPException(400, "Tipo de recurso inválido.")
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, kind, title.strip(), external_url=url, metadata={"source": "google_link", "linked_by": admin["email"]})
            audit(conn, admin["email"], "google_link_added", "module", str(module_id), kind, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)
