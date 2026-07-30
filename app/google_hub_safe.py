from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.academic_access import AUTHOR_ROLES, STUDENT_ROLES, esc, google_user, portal_page, remove_route, safe_next
from app.admin_console import audit, db, require_admin
from app.unified_authoring import PREFIX, _insert_item, _module


def register_portal_home_and_google(app: FastAPI) -> None:
    """Register the academic portal without importing private Google API helpers.

    The authenticated V3 package owns OAuth and the Google API routes. This layer
    only links to those public routes, so changes to token-storage internals cannot
    prevent NUVEDRA from starting.
    """

    @app.get("/portal/login", response_model=None)
    async def portal_login(request: Request, next: str = "/portal"):
        request.session["post_google_redirect"] = safe_next(next)
        return RedirectResponse("/auth/google/login", status_code=303)

    @app.get("/portal/google-connect", response_model=None)
    async def google_connect(request: Request, next: str = "/portal"):
        return await portal_login(request, next)

    @app.get("/portal/logout", response_model=None)
    async def portal_logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/portal", response_class=HTMLResponse, response_model=None)
    async def portal_home(request: Request):
        user = google_user(request)
        if not user:
            body = '''<section class="card" style="max-width:680px;margin:auto"><h2>Acceso para profesores y estudiantes</h2><p>Utilice su cuenta institucional de Google. NUVEDRA mostrará únicamente los cursos y las funciones asignadas por el administrador.</p><a class="button" href="/portal/login">Continuar con Google</a></section>'''
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
            for row in enrollments
            if str(row.get("course_role")) in AUTHOR_ROLES
        )
        student_cards = "".join(
            f'<section class="card"><span class="badge">Estudiante</span><h3>{esc(row["course_code"])}: {esc(row["title"])}</h3><p>{esc(row.get("description"))}</p><a class="button secondary" href="/learn/courses/{row["course_id"]}">Entrar al curso</a></section>'
            for row in enrollments
            if str(row.get("course_role")) in STUDENT_ROLES
            and str(row.get("course_status")) == "active"
        )

        body = '<h2>Mis cursos</h2><p class="muted">Las funciones dependen del rol asignado por el administrador.</p>'
        if user.get("_auth_source") == "admin":
            body += '<p class="notice"><strong>Administrador e instructor:</strong> está utilizando su sesión administrativa. Solo verá herramientas docentes en los cursos donde su correo tenga el rol de instructor.</p>'
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

        body = f'''
        <p><a href="{PREFIX}/modules/{module_id}">&larr; Volver al módulo</a></p>
        <h2>Google Hub sencillo</h2>
        <p class="notice">Puede vincular un recurso compartido sin conectar Google. La selección de Drive usa la ruta pública de Google del sistema y nunca bloquea el inicio de NUVEDRA.</p>
        <div class="grid">
          <section class="card">
            <h3>Opción 1: pegar enlace compartido</h3>
            <form method="post" action="{PREFIX}/modules/{module_id}/google-link">
              <label>Tipo<select name="kind"><option value="document">Google Docs</option><option value="presentation">Google Slides</option><option value="spreadsheet">Google Sheets</option><option value="assessment">Google Forms</option><option value="video">Google Meet o video</option></select></label>
              <label>Título<input name="title" required></label>
              <label>Enlace compartido<input type="url" name="url" required></label>
              <button>Vincular al módulo</button>
            </form>
          </section>
          <section class="card">
            <h3>Opción 2: Google Drive</h3>
            <p><a class="button" href="/portal/google-connect?next={PREFIX}/modules/{module_id}/drive">Conectar Google</a></p>
            <button type="button" id="load-drive-files" class="button secondary">Cargar archivos de Drive</button>
            <p class="muted">Si Google no está configurado o la sesión expiró, puede continuar con la opción de enlace compartido.</p>
          </section>
        </div>
        <section class="card" aria-live="polite">
          <h3>Archivos disponibles</h3>
          <div id="drive-status" class="notice">Presione “Cargar archivos de Drive” para consultar sus archivos.</div>
          <div id="drive-files" class="grid"></div>
        </section>
        <script>
        (() => {{
          const button = document.getElementById('load-drive-files');
          const status = document.getElementById('drive-status');
          const container = document.getElementById('drive-files');
          const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
          button?.addEventListener('click', async () => {{
            button.disabled = true;
            status.className = 'notice';
            status.textContent = 'Consultando Google Drive…';
            container.innerHTML = '';
            try {{
              const response = await fetch('/api/google/drive/files', {{headers: {{'Accept':'application/json'}}}});
              if (!response.ok) throw new Error(response.status === 401 ? 'Conecte Google y vuelva a intentarlo.' : 'Google Drive no está disponible en este momento.');
              const payload = await response.json();
              const files = Array.isArray(payload.files) ? payload.files : [];
              status.textContent = files.length ? `Se encontraron ${{files.length}} archivos.` : 'Google Drive no devolvió archivos.';
              container.innerHTML = files.map(file => `
                <article class="card">
                  <h3>${{escapeHtml(file.name || 'Archivo')}}</h3>
                  <p>${{escapeHtml(file.mimeType || '')}}</p>
                  <form method="post" action="{PREFIX}/modules/{module_id}/google-link">
                    <input type="hidden" name="kind" value="document">
                    <input type="hidden" name="title" value="${{escapeHtml(file.name || 'Archivo')}}">
                    <input type="hidden" name="url" value="${{escapeHtml(file.webViewLink || '')}}">
                    <button ${{file.webViewLink ? '' : 'disabled'}}>Vincular</button>
                  </form>
                </article>`).join('');
            }} catch (error) {{
              status.className = 'error';
              status.textContent = error.message || 'No se pudo consultar Google Drive. Use el enlace compartido.';
            }} finally {{
              button.disabled = false;
            }}
          }});
        }})();
        </script>
        '''
        return portal_page("Google Drive", body, admin)

    @app.post(f"{PREFIX}/modules/{{module_id}}/google-link", response_model=None)
    async def add_google_link(
        module_id: int,
        request: Request,
        kind: str = Form(...),
        title: str = Form(...),
        url: str = Form(...),
    ):
        admin = require_admin(request, {"course_admin"})
        if kind not in {"document", "presentation", "spreadsheet", "assessment", "video"}:
            raise HTTPException(400, "Tipo de recurso inválido.")
        clean_title = title.strip()
        clean_url = url.strip()
        if not clean_title or not clean_url.startswith(("https://", "http://")):
            raise HTTPException(400, "Título y enlace válido son obligatorios.")
        with db() as conn:
            _module(conn, module_id)
            _insert_item(
                conn,
                module_id,
                kind,
                clean_title,
                external_url=clean_url,
                metadata={"source": "google_link", "linked_by": admin["email"]},
            )
            audit(
                conn,
                admin["email"],
                "google_link_added",
                "module",
                str(module_id),
                kind,
                request.client.host if request.client else "",
            )
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)
