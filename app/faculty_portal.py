from __future__ import annotations

import json

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.academic_access import AUTHOR_ROLES, esc, google_user, item_bundle, login_redirect, module_course_id, portal_page, require_course_role
from app.admin_authoring_v6 import safe_url, sanitize_html
from app.admin_console import audit, db, execute, rows, utcnow
from app.unified_authoring import ACTIVITY_TYPES, CONTENT_TYPES, PREFIX, _course, _insert_item, _module

ITEM_TYPES = {**CONTENT_TYPES, **ACTIVITY_TYPES, "assessment": "Evaluación"}


def item_options(selected: str = "page") -> str:
    return "".join(
        f'<option value="{key}"{" selected" if key == selected else ""}>{esc(label)}</option>'
        for key, label in ITEM_TYPES.items()
    )


def register_faculty_portal(app: FastAPI) -> None:
    @app.get("/faculty/courses/{course_id}", response_class=HTMLResponse, response_model=None)
    async def faculty_course(course_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/courses/{course_id}")
        with db() as conn:
            access = require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                result = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module["id"],)))
                module["item_total"] = int(result[0].get("total") or 0) if result else 0
        cards = "".join(
            f'<section class="card module"><span class="badge">{esc(module.get("status") or "draft")}</span><h3>{int(module.get("position") or 1)}. {esc(module["title"])}</h3><p>{esc(module.get("description"))}</p><p>{int(module.get("item_total") or 0)} elementos</p><a class="button" href="/faculty/modules/{module["id"]}">Editar módulo</a></section>'
            for module in modules
        ) or '<p class="notice">Todavía no hay módulos. Cree el primero.</p>'
        body = f'''<p><a href="/portal">&larr; Mis cursos</a></p><h2>{esc(access["course_code"])}: {esc(access["title"])}</h2><p>El administrador creó y asignó el curso. Como profesor, puede desarrollar módulos, contenido y evaluaciones.</p><section class="card"><h3>Crear módulo</h3><form method="post" action="/faculty/courses/{course_id}/modules"><label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label><label>Resultados de aprendizaje<textarea name="learning_outcomes"></textarea></label><div class="grid"><label>Duración estimada<input type="number" name="estimated_minutes" min="1" value="60"></label><label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label></div><button>Crear módulo</button></form></section><h2>Módulos</h2><div class="grid">{cards}</div>'''
        return portal_page("Curso del profesor", body, user)

    @app.post("/faculty/courses/{course_id}/modules", response_model=None)
    async def create_module(course_id: int, request: Request, title: str = Form(...), description: str = Form(""), learning_outcomes: str = Form(""), estimated_minutes: int = Form(60), position: int = Form(1)):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/courses/{course_id}")
        if not title.strip():
            raise HTTPException(400, "El título es obligatorio.")
        with db() as conn:
            require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            now = utcnow()
            execute(conn, """INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), "draft", now, now))
            audit(conn, user["email"], "faculty_module_created", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/courses/{course_id}", status_code=303)

    @app.get("/faculty/modules/{module_id}", response_class=HTMLResponse, response_model=None)
    async def faculty_module(module_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/modules/{module_id}")
        with db() as conn:
            module = _module(conn, module_id)
            course_id = int(module["course_id"])
            course = _course(conn, course_id)
            require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
        item_rows = "".join(
            f'<tr><td>{int(item.get("position") or 1)}</td><td><strong>{esc(item["title"])}</strong><br><small>{esc(item.get("item_type"))}</small></td><td>{esc(item.get("status") or "draft")}</td><td><a href="/faculty/items/{item["id"]}/edit">Editar</a> · <a href="{PREFIX}/items/{item["id"]}/preview" target="_blank">Vista previa</a></td></tr>'
            for item in items
        ) or '<tr><td colspan="4">No hay contenido.</td></tr>'
        body = f'''<p><a href="/faculty/courses/{course_id}">&larr; Volver al curso</a></p><h2>{esc(course["course_code"])} · {esc(module["title"])}</h2><div class="grid"><section class="card"><h3>Información del módulo</h3><form method="post" action="/faculty/modules/{module_id}/update"><label>Título<input name="title" required value="{esc(module["title"], attr=True)}"></label><label>Descripción<textarea name="description">{esc(module.get("description"))}</textarea></label><label>Resultados de aprendizaje<textarea name="learning_outcomes">{esc(module.get("learning_outcomes"))}</textarea></label><div class="grid"><label>Duración<input type="number" name="estimated_minutes" min="1" value="{int(module.get("estimated_minutes") or 60)}"></label><label>Posición<input type="number" name="position" min="1" value="{int(module.get("position") or 1)}"></label></div><label>Estado<select name="status"><option value="draft"{" selected" if module.get("status")=="draft" else ""}>Borrador</option><option value="published"{" selected" if module.get("status")=="published" else ""}>Publicado</option><option value="hidden"{" selected" if module.get("status")=="hidden" else ""}>Oculto</option></select></label><button>Guardar módulo</button></form></section><section class="card"><h3>Añadir contenido o evaluación</h3><form method="post" action="/faculty/modules/{module_id}/items"><label>Tipo<select name="item_type">{item_options()}</select></label><label>Título<input name="title" required></label><label>Contenido, instrucciones o pregunta<textarea name="body_html"></textarea></label><label>Enlace externo o de Google<input type="url" name="external_url" placeholder="https://docs.google.com/..."></label><label>URL para incrustar, WebXR o multimedia<input type="url" name="embed_url"></label><div class="grid"><label>Puntos<input type="number" name="points" min="0" step="0.01"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label></div><label>Alternativa accesible<textarea name="accessible_alternative" placeholder="Descripción, transcripción o actividad equivalente."></textarea></label><button>Añadir al módulo</button></form><p class="notice"><strong>Google Hub sencillo:</strong> cree el recurso en <a href="https://docs.new" target="_blank" rel="noopener">Docs</a>, <a href="https://slides.new" target="_blank" rel="noopener">Slides</a>, <a href="https://sheets.new" target="_blank" rel="noopener">Sheets</a> o <a href="https://forms.new" target="_blank" rel="noopener">Forms</a>; luego pegue el enlace compartido.</p></section></div><h2>Contenido del módulo</h2><section class="card"><table><thead><tr><th>Orden</th><th>Elemento</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{item_rows}</tbody></table></section>'''
        return portal_page("Editar módulo", body, user)

    @app.post("/faculty/modules/{module_id}/update", response_model=None)
    async def update_module(module_id: int, request: Request, title: str = Form(...), description: str = Form(""), learning_outcomes: str = Form(""), estimated_minutes: int = Form(60), position: int = Form(1), status: str = Form("draft")):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/modules/{module_id}")
        if status not in {"draft", "published", "hidden"}:
            raise HTTPException(400, "Estado inválido.")
        with db() as conn:
            course_id = module_course_id(conn, module_id)
            require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            execute(conn, "UPDATE nexus_modules SET title=?,description=?,learning_outcomes=?,estimated_minutes=?,position=?,status=?,updated_at=? WHERE id=?", (title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), status, utcnow(), module_id))
            audit(conn, user["email"], "faculty_module_updated", "module", str(module_id), status, request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/modules/{module_id}", status_code=303)

    @app.post("/faculty/modules/{module_id}/items", response_model=None)
    async def create_item(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), points: str = Form(""), due_at: str = Form(""), accessible_alternative: str = Form("")):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/modules/{module_id}")
        if item_type not in ITEM_TYPES:
            raise HTTPException(400, "Tipo inválido.")
        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Puntuación inválida.") from exc
        with db() as conn:
            course_id = module_course_id(conn, module_id)
            require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            accessible = accessible_alternative.strip()
            content = sanitize_html(body_html)
            if accessible:
                content += f'<h3>Alternativa accesible</h3><p>{esc(accessible)}</p>'
            _insert_item(conn, module_id, item_type, title.strip(), body_html=content, external_url=external_url, embed_url=embed_url, metadata={"accessible_alternative": accessible, "created_by": user["email"]}, points=points_value, due_at=due_at, status="draft")
            audit(conn, user["email"], "faculty_item_created", "module", str(module_id), item_type, request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/modules/{module_id}", status_code=303)

    @app.get("/faculty/items/{item_id}/edit", response_class=HTMLResponse, response_model=None)
    async def edit_item(item_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/items/{item_id}/edit")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
        try:
            metadata_value = json.loads(str(item.get("metadata_json") or "{}"))
        except json.JSONDecodeError:
            metadata_value = {}
        metadata = json.dumps(metadata_value, ensure_ascii=False, indent=2)
        body = f'''<p><a href="/faculty/modules/{module["id"]}">&larr; Volver al módulo</a></p><h2>Editar contenido o evaluación</h2><section class="card"><form method="post" action="/faculty/items/{item_id}/edit"><label>Tipo<select name="item_type">{item_options(str(item.get("item_type") or "page"))}</select></label><label>Título<input name="title" required value="{esc(item["title"], attr=True)}"></label><label>Contenido HTML<textarea name="body_html" style="min-height:260px">{esc(item.get("body_html"))}</textarea></label><label>Enlace externo o Google<input type="url" name="external_url" value="{esc(item.get("external_url"), attr=True)}"></label><label>URL incrustada<input type="url" name="embed_url" value="{esc(item.get("embed_url"), attr=True)}"></label><label>Configuración avanzada JSON<textarea name="metadata_json">{esc(metadata)}</textarea></label><div class="grid"><label>Puntos<input type="number" min="0" step="0.01" name="points" value="{esc(item.get("points"), attr=True)}"></label><label>Fecha límite<input type="datetime-local" name="due_at" value="{esc(item.get("due_at"), attr=True)}"></label><label>Orden<input type="number" min="1" name="position" value="{int(item.get("position") or 1)}"></label></div><label>Estado<select name="status"><option value="draft"{" selected" if item.get("status")=="draft" else ""}>Borrador</option><option value="published"{" selected" if item.get("status")=="published" else ""}>Publicado</option><option value="scheduled"{" selected" if item.get("status")=="scheduled" else ""}>Programado</option><option value="hidden"{" selected" if item.get("status")=="hidden" else ""}>Oculto</option></select></label><button>Guardar cambios</button></form></section>'''
        return portal_page("Editar contenido", body, user)

    @app.post("/faculty/items/{item_id}/edit", response_model=None)
    async def update_item(item_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form("{}"), points: str = Form(""), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = google_user(request)
        if not user:
            return login_redirect(f"/faculty/items/{item_id}/edit")
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
            course_id, old_item, module = item_bundle(conn, item_id)
            require_course_role(conn, course_id, user["email"], AUTHOR_ROLES)
            execute(conn, """UPDATE nexus_content_items SET item_type=?,title=?,body_html=?,external_url=?,embed_url=?,metadata_json=?,points=?,due_at=?,position=?,status=?,updated_at=? WHERE id=?""", (item_type, title.strip(), sanitize_html(body_html), safe_url(external_url) or None, safe_url(embed_url) or None, json.dumps(metadata, ensure_ascii=False), points_value, due_at.strip() or None, max(1, position), status, utcnow(), item_id))
            audit(conn, user["email"], "faculty_item_updated", "item", str(item_id), status, request.client.host if request.client else "")
        return RedirectResponse(f"/faculty/modules/{module['id']}", status_code=303)
