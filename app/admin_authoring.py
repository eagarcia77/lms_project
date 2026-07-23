from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.admin_console import audit, db, database_url, execute, page, require_admin, rows, utcnow

CONTENT_TYPES = {
    "page", "document", "presentation", "spreadsheet", "link", "video", "audio",
    "image", "pdf", "embed", "diagram", "math", "interactive", "ar", "vr",
    "assignment", "discussion", "assessment", "rubric", "announcement"
}
PUBLISH_STATES = {"draft", "published", "scheduled", "hidden"}


class SafeHTML(HTMLParser):
    allowed_tags = {
        "p", "br", "strong", "em", "u", "s", "h1", "h2", "h3", "h4",
        "ul", "ol", "li", "blockquote", "pre", "code", "table", "thead",
        "tbody", "tr", "th", "td", "a", "img", "hr", "div", "span"
    }
    allowed_attrs = {
        "a": {"href", "title", "target", "rel"},
        "img": {"src", "alt", "title", "width", "height"},
        "div": {"class"}, "span": {"class"}, "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"}
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in self.allowed_tags:
            return
        clean: list[str] = []
        for key, value in attrs:
            key = key.lower()
            if key not in self.allowed_attrs.get(tag, set()) or value is None:
                continue
            if key in {"href", "src"} and not re.match(r"^(https?://|mailto:|/)", value, re.I):
                continue
            clean.append(f'{key}="{html.escape(value, quote=True)}"')
        suffix = (" " + " ".join(clean)) if clean else ""
        self.out.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.allowed_tags and tag not in {"br", "hr", "img"}:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.out.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        self.out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.out.append(f"&#{name};")


def sanitize_rich_html(value: str) -> str:
    parser = SafeHTML()
    parser.feed(value or "")
    return "".join(parser.out)


def init_authoring_schema() -> None:
    statements = [
        """CREATE TABLE IF NOT EXISTS nexus_modules (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            course_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT,
            position INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'draft',
            available_from TEXT, available_until TEXT, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_content_items (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            module_id INTEGER NOT NULL, item_type TEXT NOT NULL, title TEXT NOT NULL,
            body_html TEXT, external_url TEXT, embed_url TEXT, metadata_json TEXT,
            points REAL, due_at TEXT, position INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_question_bank (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            content_item_id INTEGER NOT NULL, question_type TEXT NOT NULL,
            prompt TEXT NOT NULL, options_json TEXT, answer_json TEXT,
            points REAL NOT NULL DEFAULT 1, feedback TEXT, position INTEGER NOT NULL DEFAULT 1
        )""",
    ]
    if not database_url().startswith("postgres"):
        statements = [s.replace("INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY", "INTEGER PRIMARY KEY AUTOINCREMENT") for s in statements]
    with db() as conn:
        for statement in statements:
            execute(conn, statement)


def _course(conn, course_id: int) -> dict[str, Any]:
    found = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,)))
    if not found:
        raise HTTPException(404, "Curso no encontrado")
    return found[0]


def _module(conn, module_id: int) -> dict[str, Any]:
    found = rows(execute(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,)))
    if not found:
        raise HTTPException(404, "Módulo no encontrado")
    return found[0]


def _tool_cards() -> str:
    tools = [
        ("Google Docs", "https://docs.new", "Documento colaborativo"),
        ("Google Slides", "https://slides.new", "Presentación"),
        ("Google Sheets", "https://sheets.new", "Hoja de cálculo"),
        ("Google Forms", "https://forms.new", "Formulario o prueba"),
        ("Google Drive", "https://drive.google.com", "Archivos y carpetas"),
        ("diagrams.net", "https://app.diagrams.net", "Mapas y diagramas"),
        ("Excalidraw", "https://excalidraw.com", "Pizarra y dibujos"),
        ("GeoGebra", "https://www.geogebra.org/classic", "Matemáticas interactivas"),
        ("Mermaid Live", "https://mermaid.live", "Diagramas desde texto"),
        ("Canva", "https://www.canva.com", "Diseño visual"),
        ("YouTube Studio", "https://studio.youtube.com", "Video educativo"),
        ("Lumi H5P", "https://lumi.education", "Actividades H5P gratuitas"),
    ]
    return "".join(
        f'<a class="card" target="_blank" rel="noopener" href="{url}"><strong>{html.escape(name)}</strong><span>{html.escape(desc)}</span></a>'
        for name, url, desc in tools
    )


def _editor_script() -> str:
    return r"""
<script>
function cmd(name, value=null){document.execCommand(name,false,value);document.getElementById('body_html').value=document.getElementById('editor').innerHTML;}
function syncEditor(){document.getElementById('body_html').value=document.getElementById('editor').innerHTML;}
function insertLink(){const u=prompt('URL segura (https://):');if(u)cmd('createLink',u);}
function insertImage(){const u=prompt('URL de la imagen (https://):');if(u)cmd('insertImage',u);}
function previewEmbed(){const u=document.getElementById('embed_url').value;const p=document.getElementById('embedPreview');p.innerHTML=u?'<iframe src="'+u.replace(/"/g,'&quot;')+'" title="Vista previa" loading="lazy"></iframe>':'';}
document.addEventListener('DOMContentLoaded',()=>{const f=document.querySelector('form[data-editor]');if(f)f.addEventListener('submit',syncEditor);});
</script>
"""


def register_authoring(app: FastAPI) -> None:
    init_authoring_schema()

    @app.get("/admin/authoring", response_class=HTMLResponse)
    async def authoring_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC, id DESC"))
        cards = "".join(
            f'''<article class="card"><h3>{html.escape(c['course_code'])}: {html.escape(c['title'])}</h3>
            <p>{html.escape(c.get('term') or 'Sin periodo')} · {html.escape(c.get('status') or 'draft')}</p>
            <a class="button" href="/admin/authoring/courses/{c['id']}">Abrir diseñador</a></article>'''
            for c in courses
        ) or '<p class="notice">No hay cursos administrativos. Cree uno en Cursos.</p>'
        return page("Diseñador académico", f'''<h2>NEXUS Course Studio</h2>
        <p>Cree módulos y contenidos instruccionales con herramientas nativas y servicios gratuitos.</p>
        <div class="grid">{cards}</div><h2>Herramientas gratuitas</h2><div class="grid">{_tool_cards()}</div>''', user)

    @app.get("/admin/authoring/courses/{course_id}", response_class=HTMLResponse)
    async def course_studio(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                module["items"] = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module["id"],)))
        module_html = ""
        for module in modules:
            item_html = "".join(
                f'''<li><strong>{html.escape(i['title'])}</strong> <span class="status">{html.escape(i['item_type'])} · {html.escape(i['status'])}</span>
                <a href="/admin/authoring/items/{i['id']}/edit">Editar</a> · <a href="/admin/authoring/items/{i['id']}/preview" target="_blank">Vista previa</a></li>'''
                for i in module["items"]
            ) or "<li>Sin contenido todavía.</li>"
            module_html += f'''<section class="card"><h3>{module['position']}. {html.escape(module['title'])}</h3>
            <p>{html.escape(module.get('description') or '')}</p><p class="status">{html.escape(module['status'])}</p>
            <a class="button" href="/admin/authoring/modules/{module['id']}/items/new">Añadir contenido</a>
            <ul>{item_html}</ul></section>'''
        return page("Diseñar curso", f'''<p><a href="/admin/authoring">← Todos los cursos</a></p>
        <h2>{html.escape(course['course_code'])}: {html.escape(course['title'])}</h2>
        <div class="grid"><section class="card"><h3>Crear módulo</h3><form method="post" action="/admin/authoring/courses/{course_id}/modules">
        <label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label>
        <label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label>
        <label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label>
        <button>Crear módulo</button></form></section><section class="card"><h3>Accesos de autoría</h3><div class="grid">{_tool_cards()}</div></section></div>
        <h2>Módulos</h2>{module_html or '<p class="notice">Cree el primer módulo para comenzar.</p>'}''', user)

    @app.post("/admin/authoring/courses/{course_id}/modules")
    async def create_module(course_id: int, request: Request, title: str = Form(...), description: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if status not in PUBLISH_STATES:
            raise HTTPException(400, "Estado inválido")
        with db() as conn:
            _course(conn, course_id)
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (course_id, title.strip(), description.strip(), max(position, 1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "module_created", "course", str(course_id), title, request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{course_id}", status_code=303)

    @app.get("/admin/authoring/modules/{module_id}/items/new", response_class=HTMLResponse)
    async def new_item(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, module["course_id"])
            count = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module_id,)))[0]["total"]
        options = "".join(f'<option value="{x}">{x.replace("_", " ").title()}</option>' for x in sorted(CONTENT_TYPES))
        return page("Añadir contenido", f'''<p><a href="/admin/authoring/courses/{course['id']}">← Volver al curso</a></p>
        <h2>Añadir contenido a {html.escape(module['title'])}</h2>
        <div class="grid"><section class="card" style="grid-column:span 2"><form method="post" action="/admin/authoring/modules/{module_id}/items" data-editor>
        <label>Tipo<select name="item_type">{options}</select></label><label>Título<input name="title" required></label>
        <label>Editor de contenido</label><div class="toolbar"><button type="button" onclick="cmd('bold')">Negrita</button><button type="button" onclick="cmd('italic')">Cursiva</button><button type="button" onclick="cmd('insertUnorderedList')">Lista</button><button type="button" onclick="cmd('formatBlock','h2')">Título</button><button type="button" onclick="insertLink()">Enlace</button><button type="button" onclick="insertImage()">Imagen</button></div>
        <div id="editor" contenteditable="true" role="textbox" aria-multiline="true" class="rich-editor"><p>Escriba aquí el contenido instruccional...</p></div><input type="hidden" id="body_html" name="body_html">
        <label>Enlace externo<input type="url" name="external_url" placeholder="Google Docs, PDF, video, H5P, SCORM, etc."></label>
        <label>URL para incrustar<input type="url" id="embed_url" name="embed_url" oninput="previewEmbed()" placeholder="URL que permita iframe"></label><div id="embedPreview" class="embed-preview"></div>
        <div class="grid"><label>Puntos<input type="number" step="0.01" name="points"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label>Posición<input type="number" name="position" min="1" value="{int(count)+1}"></label><label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label></div>
        <label>Configuración adicional (JSON opcional)<textarea name="metadata_json" placeholder='{{"attempts": 2, "time_limit": 60}}'></textarea></label>
        <button>Guardar contenido</button></form></section><section class="card"><h3>Crear con Google</h3><div class="grid">{_tool_cards()}</div><p>Después de crear el archivo, copie el enlace y péguelo en “Enlace externo”.</p></section></div>
        <style>.toolbar{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}}.toolbar button{{margin:0;padding:8px}}.rich-editor{{min-height:300px;background:#fff;border:1px solid #8093a7;border-radius:8px;padding:16px}}.embed-preview iframe{{width:100%;min-height:280px;border:1px solid #cbd6e2}}</style>{_editor_script()}''', user)

    @app.post("/admin/authoring/modules/{module_id}/items")
    async def create_item(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form(""), points: float | None = Form(None), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if item_type not in CONTENT_TYPES or status not in PUBLISH_STATES:
            raise HTTPException(400, "Tipo o estado inválido")
        metadata = {}
        if metadata_json.strip():
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, "La configuración adicional debe ser JSON válido") from exc
        with db() as conn:
            module = _module(conn, module_id)
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (module_id, item_type, title.strip(), sanitize_rich_html(body_html), external_url.strip(), embed_url.strip(), json.dumps(metadata, ensure_ascii=False), points, due_at or None, max(position,1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "content_created", "module", str(module_id), f"{item_type}: {title}", request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{module['course_id']}", status_code=303)

    @app.get("/admin/authoring/items/{item_id}/preview", response_class=HTMLResponse)
    async def preview_item(item_id: int, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            found = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE id=?", (item_id,)))
        if not found:
            raise HTTPException(404, "Contenido no encontrado")
        item = found[0]
        embed = f'<iframe src="{html.escape(item.get("embed_url") or "", quote=True)}" title="Contenido incrustado" style="width:100%;min-height:600px;border:0"></iframe>' if item.get("embed_url") else ""
        link = f'<p><a class="button" target="_blank" rel="noopener" href="{html.escape(item.get("external_url") or "", quote=True)}">Abrir recurso externo</a></p>' if item.get("external_url") else ""
        return HTMLResponse(f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(item['title'])}</title><style>body{{font:18px/1.65 system-ui;max-width:1000px;margin:auto;padding:30px}}img{{max-width:100%}}table{{border-collapse:collapse}}th,td{{border:1px solid #aaa;padding:8px}}a{{color:#174ea6}}</style></head><body><h1>{html.escape(item['title'])}</h1>{item.get('body_html') or ''}{link}{embed}</body></html>''')

    @app.get("/admin/authoring/items/{item_id}/edit", response_class=HTMLResponse)
    async def edit_item(item_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            found = rows(execute(conn, "SELECT i.*,m.course_id FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id WHERE i.id=?", (item_id,)))
        if not found:
            raise HTTPException(404, "Contenido no encontrado")
        i = found[0]
        options = "".join(f'<option value="{x}" {"selected" if x==i["item_type"] else ""}>{x.title()}</option>' for x in sorted(CONTENT_TYPES))
        states = "".join(f'<option value="{x}" {"selected" if x==i["status"] else ""}>{x.title()}</option>' for x in PUBLISH_STATES)
        return page("Editar contenido", f'''<p><a href="/admin/authoring/courses/{i['course_id']}">← Volver al curso</a></p><h2>Editar contenido</h2><section class="card"><form method="post" data-editor>
        <label>Tipo<select name="item_type">{options}</select></label><label>Título<input name="title" value="{html.escape(i['title'], quote=True)}" required></label>
        <div class="toolbar"><button type="button" onclick="cmd('bold')">Negrita</button><button type="button" onclick="cmd('italic')">Cursiva</button><button type="button" onclick="cmd('insertUnorderedList')">Lista</button><button type="button" onclick="insertLink()">Enlace</button><button type="button" onclick="insertImage()">Imagen</button></div>
        <div id="editor" contenteditable="true" class="rich-editor">{i.get('body_html') or ''}</div><input type="hidden" id="body_html" name="body_html" value="{html.escape(i.get('body_html') or '', quote=True)}">
        <label>Enlace externo<input type="url" name="external_url" value="{html.escape(i.get('external_url') or '', quote=True)}"></label><label>URL incrustada<input type="url" id="embed_url" name="embed_url" value="{html.escape(i.get('embed_url') or '', quote=True)}"></label>
        <label>Configuración JSON<textarea name="metadata_json">{html.escape(i.get('metadata_json') or '{}')}</textarea></label><div class="grid"><label>Puntos<input type="number" step="0.01" name="points" value="{i.get('points') or ''}"></label><label>Fecha límite<input type="datetime-local" name="due_at" value="{html.escape(i.get('due_at') or '', quote=True)}"></label><label>Posición<input type="number" min="1" name="position" value="{i.get('position') or 1}"></label><label>Estado<select name="status">{states}</select></label></div><button>Guardar cambios</button></form></section>
        <style>.toolbar{{display:flex;gap:6px;flex-wrap:wrap}}.toolbar button{{margin:0}}.rich-editor{{min-height:300px;background:#fff;border:1px solid #8093a7;border-radius:8px;padding:16px}}</style>{_editor_script()}''', user)

    @app.post("/admin/authoring/items/{item_id}/edit")
    async def update_item(item_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form("{}"), points: float | None = Form(None), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):
        user = require_admin(request, {"course_admin"})
        if item_type not in CONTENT_TYPES or status not in PUBLISH_STATES:
            raise HTTPException(400, "Tipo o estado inválido")
        try:
            metadata = json.loads(metadata_json or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "JSON inválido") from exc
        with db() as conn:
            found = rows(execute(conn, "SELECT i.module_id,m.course_id FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id WHERE i.id=?", (item_id,)))
            if not found:
                raise HTTPException(404, "Contenido no encontrado")
            execute(conn, "UPDATE nexus_content_items SET item_type=?,title=?,body_html=?,external_url=?,embed_url=?,metadata_json=?,points=?,due_at=?,position=?,status=?,updated_at=? WHERE id=?",
                    (item_type,title.strip(),sanitize_rich_html(body_html),external_url.strip(),embed_url.strip(),json.dumps(metadata,ensure_ascii=False),points,due_at or None,max(position,1),status,utcnow(),item_id))
            audit(conn,user["email"],"content_updated","content_item",str(item_id),title,request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{found[0]['course_id']}", status_code=303)
