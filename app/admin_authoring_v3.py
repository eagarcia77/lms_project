from __future__ import annotations

import html
import json
from html.parser import HTMLParser
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.admin_console import audit, db, database_url, execute, page, require_admin, rows, utcnow

CONTENT_TYPES = {
    "page", "document", "presentation", "spreadsheet", "link", "video", "audio",
    "image", "pdf", "embed", "diagram", "math", "interactive", "ar", "vr",
    "assignment", "discussion", "assessment", "rubric", "announcement",
}
PUBLISH_STATES = {"draft", "published", "scheduled", "hidden"}


class SafeHTML(HTMLParser):
    allowed_tags = {
        "p", "br", "strong", "em", "u", "s", "h1", "h2", "h3", "h4",
        "ul", "ol", "li", "blockquote", "pre", "code", "table", "thead",
        "tbody", "tr", "th", "td", "a", "img", "hr", "div", "span",
    }
    allowed_attrs = {
        "a": {"href", "title", "target", "rel"},
        "img": {"src", "alt", "title", "width", "height"},
        "div": {"class"}, "span": {"class"}, "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in self.allowed_tags:
            return
        clean: list[str] = []
        for key, value in attrs:
            key = key.lower()
            if value is None or key not in self.allowed_attrs.get(tag, set()):
                continue
            if key in {"href", "src"} and not value.lower().startswith(("https://", "http://", "mailto:", "/")):
                continue
            clean.append(f'{key}="{html.escape(value, quote=True)}"')
        suffix = " " + " ".join(clean) if clean else ""
        self.output.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.allowed_tags and tag not in {"br", "hr", "img"}:
            self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.output.append(html.escape(data))


def sanitize_html(value: str) -> str:
    parser = SafeHTML()
    parser.feed(value or "")
    return "".join(parser.output)


def _ensure_schema() -> None:
    identity = "INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY"
    if not database_url().startswith("postgres"):
        identity = "INTEGER PRIMARY KEY AUTOINCREMENT"

    statements = [
        f"""CREATE TABLE IF NOT EXISTS nexus_modules (
            id {identity}, course_id INTEGER NOT NULL, title TEXT NOT NULL,
            description TEXT, position INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft', available_from TEXT,
            available_until TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS nexus_content_items (
            id {identity}, module_id INTEGER NOT NULL, item_type TEXT NOT NULL,
            title TEXT NOT NULL, body_html TEXT, external_url TEXT, embed_url TEXT,
            metadata_json TEXT, points REAL, due_at TEXT,
            position INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
    ]
    with db() as conn:
        for statement in statements:
            execute(conn, statement)

        # Non-destructive migration for tables created by earlier versions.
        module_columns = {
            "description": "TEXT", "position": "INTEGER DEFAULT 1", "status": "TEXT DEFAULT 'draft'",
            "available_from": "TEXT", "available_until": "TEXT", "created_at": "TEXT", "updated_at": "TEXT",
        }
        item_columns = {
            "item_type": "TEXT", "title": "TEXT", "body_html": "TEXT", "external_url": "TEXT",
            "embed_url": "TEXT", "metadata_json": "TEXT", "points": "REAL", "due_at": "TEXT",
            "position": "INTEGER DEFAULT 1", "status": "TEXT DEFAULT 'draft'", "created_at": "TEXT", "updated_at": "TEXT",
        }
        for name, definition in module_columns.items():
            try:
                execute(conn, f"ALTER TABLE nexus_modules ADD COLUMN {name} {definition}")
            except Exception:
                conn.rollback()
        for name, definition in item_columns.items():
            try:
                execute(conn, f"ALTER TABLE nexus_content_items ADD COLUMN {name} {definition}")
            except Exception:
                conn.rollback()


def _course(conn: Any, course_id: int) -> dict[str, Any]:
    found = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,)))
    if not found:
        raise HTTPException(404, "Curso no encontrado")
    return found[0]


def _module(conn: Any, module_id: int) -> dict[str, Any]:
    found = rows(execute(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,)))
    if not found:
        raise HTTPException(404, "Módulo no encontrado")
    return found[0]


def _tools() -> str:
    tools = [
        ("Google Docs", "https://docs.new"), ("Google Slides", "https://slides.new"),
        ("Google Sheets", "https://sheets.new"), ("Google Forms", "https://forms.new"),
        ("Google Drive", "https://drive.google.com"), ("diagrams.net", "https://app.diagrams.net"),
        ("Excalidraw", "https://excalidraw.com"), ("GeoGebra", "https://www.geogebra.org/classic"),
        ("Mermaid", "https://mermaid.live"), ("Lumi H5P", "https://lumi.education"),
    ]
    return "".join(
        f'<a class="button" target="_blank" rel="noopener" href="{url}">{html.escape(name)}</a> '
        for name, url in tools
    )


def _editor_js() -> str:
    return """
<script>
function cmd(name, value=null){document.execCommand(name,false,value);syncEditor();}
function syncEditor(){const editor=document.getElementById('editor');const field=document.getElementById('body_html');if(editor&&field){field.value=editor.innerHTML;}}
function addLink(){const url=prompt('Dirección https://');if(url){cmd('createLink',url);}}
function addImage(){const url=prompt('Dirección https:// de la imagen');if(url){cmd('insertImage',url);}}
document.addEventListener('DOMContentLoaded',()=>{const form=document.getElementById('content-form');if(form){form.addEventListener('submit',syncEditor);}});
</script>
"""


def register_authoring_v3(app: FastAPI) -> None:
    _ensure_schema()

    @app.get("/admin/authoring", response_class=HTMLResponse)
    async def authoring_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC, id DESC"))
        cards = "".join(
            f'<section class="card"><h3>{html.escape(str(c["course_code"]))}: {html.escape(str(c["title"]))}</h3>'
            f'<p>{html.escape(str(c.get("term") or "Sin periodo"))}</p>'
            f'<a class="button" href="/admin/authoring/courses/{c["id"]}">Abrir diseñador</a></section>'
            for c in courses
        ) or '<p class="notice">No hay cursos. Créelo primero desde Cursos.</p>'
        return page("Diseñador académico", f'<h2>NEXUS Course Studio V3</h2><div class="grid">{cards}</div>', user)

    @app.get("/admin/authoring/courses/{course_id}", response_class=HTMLResponse)
    async def course_studio(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                module["items"] = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module["id"],)))
        module_cards = ""
        for module in modules:
            items = "".join(
                f'<li><strong>{html.escape(str(item.get("title") or "Contenido"))}</strong> '
                f'({html.escape(str(item.get("item_type") or "page"))}) '
                f'<a href="/admin/authoring/items/{item["id"]}/preview" target="_blank">Vista previa</a></li>'
                for item in module["items"]
            ) or "<li>Sin contenido.</li>"
            module_cards += (
                f'<section class="card"><h3>{html.escape(str(module.get("title") or "Módulo"))}</h3>'
                f'<p>{html.escape(str(module.get("description") or ""))}</p>'
                f'<a class="button" href="/admin/authoring/modules/{module["id"]}/items/new">Añadir contenido</a>'
                f'<ul>{items}</ul></section>'
            )
        body = (
            f'<p><a href="/admin/authoring">&larr; Cursos</a></p>'
            f'<h2>{html.escape(str(course["course_code"]))}: {html.escape(str(course["title"]))}</h2>'
            f'<section class="card"><h3>Crear módulo</h3><form method="post" action="/admin/authoring/courses/{course_id}/modules">'
            '<label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label>'
            f'<label>Posición<input type="number" min="1" name="position" value="{len(modules)+1}"></label>'
            '<label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label>'
            '<button>Crear módulo</button></form></section>'
            f'<h2>Módulos</h2>{module_cards or "<p class=\"notice\">Cree el primer módulo.</p>"}'
        )
        return page("Diseñar curso", body, user)

    @app.post("/admin/authoring/courses/{course_id}/modules")
    async def create_module(course_id: int, request: Request, title: str = Form(...), description: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if status not in PUBLISH_STATES:
            raise HTTPException(400, "Estado inválido")
        with db() as conn:
            _course(conn, course_id)
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (course_id, title.strip(), description.strip(), max(position, 1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "module_created", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{course_id}", status_code=303)

    @app.get("/admin/authoring/modules/{module_id}/items/new", response_class=HTMLResponse)
    async def new_item(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, int(module["course_id"]))
            count_result = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module_id,)))
        next_position = int(count_result[0].get("total") or 0) + 1 if count_result else 1
        options = "".join(f'<option value="{kind}">{html.escape(kind.replace("_", " ").title())}</option>' for kind in sorted(CONTENT_TYPES))
        body = f"""
<p><a href="/admin/authoring/courses/{course['id']}">&larr; Volver al curso</a></p>
<h2>Añadir contenido a {html.escape(str(module.get('title') or 'Módulo'))}</h2>
<section class="card">
<form id="content-form" method="post" action="/admin/authoring/modules/{module_id}/items">
<label>Tipo<select name="item_type" required>{options}</select></label>
<label>Título<input name="title" maxlength="250" required></label>
<label>Contenido</label>
<div class="toolbar"><button type="button" onclick="cmd('bold')">Negrita</button><button type="button" onclick="cmd('italic')">Cursiva</button><button type="button" onclick="cmd('insertUnorderedList')">Lista</button><button type="button" onclick="cmd('formatBlock','h2')">Encabezado</button><button type="button" onclick="addLink()">Enlace</button><button type="button" onclick="addImage()">Imagen</button></div>
<div id="editor" class="rich-editor" contenteditable="true" role="textbox" aria-multiline="true"><p>Escriba aquí el contenido instruccional.</p></div>
<textarea id="body_html" name="body_html" hidden></textarea>
<label>Enlace externo<input type="url" name="external_url" placeholder="https://..."></label>
<label>URL para incrustar<input type="url" name="embed_url" placeholder="https://..."></label>
<div class="grid"><label>Puntos<input type="number" min="0" step="0.01" name="points"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label>Posición<input type="number" min="1" name="position" value="{next_position}"></label><label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label></div>
<label>Configuración JSON opcional<textarea name="metadata_json" placeholder='{{"attempts": 2}}'></textarea></label>
<button type="submit">Guardar contenido</button>
</form></section>
<section class="card"><h3>Herramientas gratuitas</h3>{_tools()}</section>
<style>.toolbar{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}}.toolbar button{{margin:0}}.rich-editor{{min-height:300px;background:white;border:1px solid #8093a7;border-radius:8px;padding:16px}}</style>
{_editor_js()}
"""
        return page("Añadir contenido", body, user)

    @app.post("/admin/authoring/modules/{module_id}/items")
    async def create_item(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form(""), points: str = Form(""), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if item_type not in CONTENT_TYPES or status not in PUBLISH_STATES:
            raise HTTPException(400, "Tipo o estado inválido")
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "El título es obligatorio")
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
            module = _module(conn, module_id)
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_id, item_type, clean_title, sanitize_html(body_html), external_url.strip() or None, embed_url.strip() or None, json.dumps(metadata, ensure_ascii=False), points_value, due_at.strip() or None, max(position, 1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "content_created", "module", str(module_id), f"{item_type}: {clean_title}", request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{module['course_id']}", status_code=303)

    @app.get("/admin/authoring/items/{item_id}/preview", response_class=HTMLResponse)
    async def preview_item(item_id: int, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            found = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE id=?", (item_id,)))
        if not found:
            raise HTTPException(404, "Contenido no encontrado")
        item = found[0]
        link = f'<p><a href="{html.escape(str(item.get("external_url")), quote=True)}" target="_blank" rel="noopener">Abrir recurso externo</a></p>' if item.get("external_url") else ""
        embed = f'<iframe src="{html.escape(str(item.get("embed_url")), quote=True)}" title="Recurso" style="width:100%;min-height:600px;border:0"></iframe>' if item.get("embed_url") else ""
        return HTMLResponse(f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(str(item.get("title") or "Contenido"))}</title></head><body style="font:18px/1.6 system-ui;max-width:1000px;margin:auto;padding:30px"><h1>{html.escape(str(item.get("title") or "Contenido"))}</h1>{item.get("body_html") or ""}{link}{embed}</body></html>')
