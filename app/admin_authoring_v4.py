from __future__ import annotations

import html
import json
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.admin_console import audit, db, database_url, execute, page, require_admin, rows, utcnow

CONTENT_TYPES = ("page", "document", "presentation", "spreadsheet", "link", "video", "audio", "image", "pdf", "embed", "diagram", "math", "interactive", "ar", "vr", "assignment", "discussion", "assessment", "rubric", "announcement")
STATES = {"draft", "published", "scheduled", "hidden"}


def ensure_schema() -> None:
    pk = "INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY" if database_url().startswith("postgres") else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with db() as conn:
        execute(conn, f"""CREATE TABLE IF NOT EXISTS nexus_modules (
            id {pk}, course_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT,
            position INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        execute(conn, f"""CREATE TABLE IF NOT EXISTS nexus_content_items (
            id {pk}, module_id INTEGER NOT NULL, item_type TEXT NOT NULL, title TEXT NOT NULL,
            body_html TEXT, external_url TEXT, embed_url TEXT, metadata_json TEXT,
            points REAL, due_at TEXT, position INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")


def one(conn: Any, sql: str, params: tuple[Any, ...], message: str) -> dict[str, Any]:
    result = rows(execute(conn, sql, params))
    if not result:
        raise HTTPException(404, message)
    return result[0]


def tools_html() -> str:
    tools = [
        ("Google Docs", "https://docs.new"), ("Google Slides", "https://slides.new"),
        ("Google Sheets", "https://sheets.new"), ("Google Forms", "https://forms.new"),
        ("Google Drive", "https://drive.google.com"), ("diagrams.net", "https://app.diagrams.net"),
        ("Excalidraw", "https://excalidraw.com"), ("GeoGebra", "https://www.geogebra.org/classic"),
        ("Mermaid", "https://mermaid.live"), ("Lumi H5P", "https://lumi.education"),
    ]
    return "".join(f'<a class="button" href="{url}" target="_blank" rel="noopener">{html.escape(name)}</a> ' for name, url in tools)


def editor_script() -> str:
    return """
<script>
function command(name,value=null){document.execCommand(name,false,value);syncContent();}
function syncContent(){const e=document.getElementById('editor');const f=document.getElementById('body_html');if(e&&f){f.value=e.innerHTML;}}
function insertLink(){const u=prompt('URL https://');if(u){command('createLink',u);}}
function insertImage(){const u=prompt('URL de la imagen');if(u){command('insertImage',u);}}
document.addEventListener('DOMContentLoaded',function(){const form=document.getElementById('content-form');if(form){form.addEventListener('submit',syncContent);}});
</script>
"""


def register_authoring_v4(app: FastAPI) -> None:
    ensure_schema()

    @app.get("/admin/authoring", response_class=HTMLResponse)
    async def authoring_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC, id DESC"))
        cards = []
        for course in courses:
            cards.append(
                f'<section class="card"><h3>{html.escape(str(course["course_code"]))}: {html.escape(str(course["title"]))}</h3>'
                f'<a class="button" href="/admin/authoring/courses/{course["id"]}">Abrir diseñador</a></section>'
            )
        content = "".join(cards) or '<p class="notice">No hay cursos disponibles.</p>'
        return page("Diseñador académico", f'<h2>NEXUS Course Studio V4</h2><div class="grid">{content}</div>', user)

    @app.get("/admin/authoring/courses/{course_id}", response_class=HTMLResponse)
    async def course_page(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = one(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,), "Curso no encontrado")
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                module["items"] = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module["id"],)))
        module_cards: list[str] = []
        for module in modules:
            items = []
            for item in module["items"]:
                items.append(f'<li>{html.escape(str(item.get("title") or "Contenido"))} <a href="/admin/authoring/items/{item["id"]}/preview" target="_blank">Vista previa</a></li>')
            item_list = "".join(items) or "<li>Sin contenido.</li>"
            module_cards.append(
                f'<section class="card"><h3>{html.escape(str(module.get("title") or "Módulo"))}</h3>'
                f'<p>{html.escape(str(module.get("description") or ""))}</p>'
                f'<a class="button" href="/admin/authoring/modules/{module["id"]}/items/new">Añadir contenido</a><ul>{item_list}</ul></section>'
            )
        modules_html = "".join(module_cards) or '<p class="notice">Cree el primer módulo.</p>'
        body = (
            '<p><a href="/admin/authoring">&larr; Cursos</a></p>'
            f'<h2>{html.escape(str(course["course_code"]))}: {html.escape(str(course["title"]))}</h2>'
            f'<section class="card"><h3>Crear módulo</h3><form method="post" action="/admin/authoring/courses/{course_id}/modules">'
            '<label>Título<input name="title" required></label>'
            '<label>Descripción<textarea name="description"></textarea></label>'
            f'<label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label>'
            '<label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label>'
            '<button type="submit">Crear módulo</button></form></section>'
            f'<h2>Módulos</h2>{modules_html}'
        )
        return page("Diseñar curso", body, user)

    @app.post("/admin/authoring/courses/{course_id}/modules")
    async def create_module(course_id: int, request: Request, title: str = Form(...), description: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if status not in STATES:
            raise HTTPException(400, "Estado inválido")
        with db() as conn:
            one(conn, "SELECT id FROM nexus_admin_courses WHERE id=?", (course_id,), "Curso no encontrado")
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (course_id, title.strip(), description.strip(), max(position, 1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "module_created", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{course_id}", status_code=303)

    @app.get("/admin/authoring/modules/{module_id}/items/new", response_class=HTMLResponse)
    async def new_item(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            module = one(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,), "Módulo no encontrado")
            course = one(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (int(module["course_id"]),), "Curso no encontrado")
            result = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module_id,)))
        next_position = int(result[0].get("total") or 0) + 1 if result else 1
        options = "".join(f'<option value="{kind}">{html.escape(kind.replace("_", " ").title())}</option>' for kind in CONTENT_TYPES)
        body = f"""
<p><a href="/admin/authoring/courses/{course['id']}">&larr; Volver al curso</a></p>
<h2>Añadir contenido a {html.escape(str(module.get('title') or 'Módulo'))}</h2>
<section class="card"><form id="content-form" method="post" action="/admin/authoring/modules/{module_id}/items">
<label>Tipo<select name="item_type" required>{options}</select></label>
<label>Título<input name="title" required maxlength="250"></label>
<label>Contenido</label>
<div class="toolbar"><button type="button" onclick="command('bold')">Negrita</button><button type="button" onclick="command('italic')">Cursiva</button><button type="button" onclick="command('insertUnorderedList')">Lista</button><button type="button" onclick="command('formatBlock','h2')">Encabezado</button><button type="button" onclick="insertLink()">Enlace</button><button type="button" onclick="insertImage()">Imagen</button></div>
<div id="editor" class="rich-editor" contenteditable="true"><p>Escriba aquí el contenido instruccional.</p></div>
<textarea id="body_html" name="body_html" hidden></textarea>
<label>Enlace externo<input type="url" name="external_url" placeholder="https://..."></label>
<label>URL para incrustar<input type="url" name="embed_url" placeholder="https://..."></label>
<div class="grid"><label>Puntos<input type="number" min="0" step="0.01" name="points"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label>Posición<input type="number" min="1" name="position" value="{next_position}"></label><label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label></div>
<label>Configuración JSON opcional<textarea name="metadata_json" placeholder='{{"attempts": 2}}'></textarea></label>
<button type="submit">Guardar contenido</button></form></section>
<section class="card"><h3>Herramientas gratuitas</h3>{tools_html()}</section>
<style>.toolbar{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}}.toolbar button{{margin:0}}.rich-editor{{min-height:300px;background:white;border:1px solid #8093a7;border-radius:8px;padding:16px}}</style>
{editor_script()}
"""
        return page("Añadir contenido", body, user)

    @app.post("/admin/authoring/modules/{module_id}/items")
    async def create_item(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form(""), points: str = Form(""), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if item_type not in CONTENT_TYPES or status not in STATES:
            raise HTTPException(400, "Tipo o estado inválido")
        metadata: dict[str, Any] = {}
        if metadata_json.strip():
            try:
                parsed = json.loads(metadata_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, "JSON inválido") from exc
            if not isinstance(parsed, dict):
                raise HTTPException(400, "La configuración debe ser un objeto JSON")
            metadata = parsed
        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Puntuación inválida") from exc
        with db() as conn:
            module = one(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,), "Módulo no encontrado")
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_id, item_type, title.strip(), body_html.strip(), external_url.strip() or None, embed_url.strip() or None, json.dumps(metadata, ensure_ascii=False), points_value, due_at.strip() or None, max(position, 1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "content_created", "module", str(module_id), f"{item_type}: {title.strip()}", request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{module['course_id']}", status_code=303)

    @app.get("/admin/authoring/items/{item_id}/preview", response_class=HTMLResponse)
    async def preview_item(item_id: int, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            item = one(conn, "SELECT * FROM nexus_content_items WHERE id=?", (item_id,), "Contenido no encontrado")
        link = f'<p><a href="{html.escape(str(item.get("external_url")), quote=True)}" target="_blank" rel="noopener">Abrir recurso externo</a></p>' if item.get("external_url") else ""
        embed = f'<iframe src="{html.escape(str(item.get("embed_url")), quote=True)}" title="Recurso" style="width:100%;min-height:600px;border:0"></iframe>' if item.get("embed_url") else ""
        return HTMLResponse(f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(str(item.get("title") or "Contenido"))}</title></head><body style="font:18px/1.6 system-ui;max-width:1000px;margin:auto;padding:30px"><h1>{html.escape(str(item.get("title") or "Contenido"))}</h1>{item.get("body_html") or ""}{link}{embed}</body></html>')
