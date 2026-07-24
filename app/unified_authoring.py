from __future__ import annotations

import html
import json
import os
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.admin_authoring_v6 import (
    GOOGLE_KINDS,
    _create_google_resource,
    _odf_response,
    _template_modules,
    ensure_schema,
    safe_url,
    sanitize_html,
)
from app.admin_console import audit, db, database_url, execute, page, require_admin, rows, utcnow
from app.google_api import google_get

PREFIX = "/admin/authoring"
ACTIVITY_TYPES = {
    "assignment": "Asignación",
    "discussion": "Foro de discusión",
    "quiz": "Examen o prueba corta",
    "project": "Proyecto",
    "presentation": "Presentación evaluada",
    "rubric": "Rúbrica",
    "h5p": "Actividad H5P/Lumi",
    "simulation": "Simulación",
    "ar": "Realidad aumentada",
    "vr": "Realidad virtual",
    "360": "Video o recorrido 360",
    "portfolio": "Portafolio",
}
CONTENT_TYPES = {
    "page": "Página de contenido",
    "document": "Documento",
    "presentation": "Presentación",
    "spreadsheet": "Hoja de cálculo",
    "link": "Enlace",
    "video": "Video",
    "audio": "Audio",
    "image": "Imagen",
    "pdf": "PDF",
    "embed": "Contenido incrustado",
    "interactive": "Contenido interactivo",
    "diagram": "Diagrama",
    "math": "Actividad matemática",
}
TOOL_PRESETS = {
    "native": ("Editor NEXUS", ""),
    "google-docs": ("Google Docs", "https://docs.new"),
    "google-slides": ("Google Slides", "https://slides.new"),
    "google-sheets": ("Google Sheets", "https://sheets.new"),
    "google-forms": ("Google Forms", "https://forms.new"),
    "h5p": ("Lumi/H5P", "https://lumi.education"),
    "jupyterlite": ("JupyterLite", "https://jupyter.org/try-jupyter/lab/"),
    "phet": ("PhET", "https://phet.colorado.edu/"),
    "geogebra": ("GeoGebra", "https://www.geogebra.org/classic"),
    "scratch": ("Scratch", "https://scratch.mit.edu/projects/editor/"),
    "twine": ("Twine", "https://twinery.org/"),
    "mermaid": ("Mermaid", "https://mermaid.live"),
    "excalidraw": ("Excalidraw", "https://excalidraw.com"),
    "aframe": ("A-Frame", "https://aframe.io/"),
    "blender": ("Blender", "https://www.blender.org/"),
}


def _pk() -> str:
    return "INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY" if database_url().startswith("postgres") else "INTEGER PRIMARY KEY AUTOINCREMENT"


def ensure_unified_schema() -> None:
    ensure_schema()
    pk = _pk()
    with db() as conn:
        execute(
            conn,
            f"""CREATE TABLE IF NOT EXISTS nexus_module_drafts (
                id {pk}, module_id INTEGER UNIQUE NOT NULL, title TEXT NOT NULL,
                body_html TEXT NOT NULL DEFAULT '', updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
        )
        execute(
            conn,
            f"""CREATE TABLE IF NOT EXISTS nexus_assessment_questions (
                id {pk}, item_id INTEGER NOT NULL, question_type TEXT NOT NULL,
                prompt TEXT NOT NULL, options_json TEXT, answer_json TEXT,
                points REAL NOT NULL DEFAULT 1, position INTEGER NOT NULL DEFAULT 1
            )""",
        )


def _one(conn: Any, sql: str, params: tuple[Any, ...], message: str) -> dict[str, Any]:
    result = rows(execute(conn, sql, params))
    if not result:
        raise HTTPException(404, message)
    return result[0]


def _course(conn: Any, course_id: int) -> dict[str, Any]:
    return _one(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,), "Curso no encontrado")


def _module(conn: Any, module_id: int) -> dict[str, Any]:
    return _one(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,), "Módulo no encontrado")


def _item(conn: Any, item_id: int) -> dict[str, Any]:
    return _one(conn, "SELECT * FROM nexus_content_items WHERE id=?", (item_id,), "Actividad no encontrada")


def _next_position(conn: Any, module_id: int) -> int:
    result = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module_id,)))
    return int(result[0].get("total") or 0) + 1 if result else 1


def _insert_item(
    conn: Any,
    module_id: int,
    item_type: str,
    title: str,
    body_html: str = "",
    external_url: str = "",
    embed_url: str = "",
    metadata: dict[str, Any] | None = None,
    points: float | None = None,
    due_at: str = "",
    position: int | None = None,
    status: str = "draft",
) -> None:
    execute(
        conn,
        """INSERT INTO nexus_content_items
        (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,
         points,due_at,position,status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            module_id,
            item_type,
            title.strip(),
            sanitize_html(body_html),
            safe_url(external_url) or None,
            safe_url(embed_url) or None,
            json.dumps(metadata or {}, ensure_ascii=False),
            points,
            due_at.strip() or None,
            position or _next_position(conn, module_id),
            status,
            utcnow(),
            utcnow(),
        ),
    )


def _editor_script(module_id: int) -> str:
    return f"""
<script>
const editor = document.getElementById('module-editor');
const hidden = document.getElementById('module-body');
function syncEditor(){{if(editor && hidden) hidden.value = editor.innerHTML;}}
function command(name,value=null){{document.execCommand(name,false,value);syncEditor();}}
function insertLink(){{const url=prompt('Dirección https://');if(url) command('createLink',url);}}
function insertImage(){{const url=prompt('Dirección de la imagen');if(url) command('insertImage',url);}}
let timer=null;
if(editor){{
  editor.addEventListener('input',()=>{{
    syncEditor();
    clearTimeout(timer);
    timer=setTimeout(async()=>{{
      const payload=new FormData();
      payload.append('title',document.getElementById('module-content-title').value || 'Contenido del módulo');
      payload.append('body_html',hidden.value);
      const state=document.getElementById('autosave-state');
      state.textContent='Guardando…';
      try{{
        const response=await fetch('{PREFIX}/modules/{module_id}/autosave',{{method:'POST',body:payload}});
        state.textContent=response.ok?'Guardado automáticamente':'No se pudo guardar';
      }}catch(error){{state.textContent='Sin conexión';}}
    }},1200);
  }});
}}
document.getElementById('content-form')?.addEventListener('submit',syncEditor);
document.querySelectorAll('[data-tab]').forEach(button=>{{
  button.addEventListener('click',()=>{{
    document.querySelectorAll('.studio-panel').forEach(panel=>panel.hidden=true);
    document.getElementById(button.dataset.tab).hidden=false;
    document.querySelectorAll('[data-tab]').forEach(x=>x.setAttribute('aria-selected','false'));
    button.setAttribute('aria-selected','true');
  }});
}});
const preset=document.getElementById('tool-preset');
preset?.addEventListener('change',()=>{{
  const option=preset.options[preset.selectedIndex];
  document.getElementById('activity-tool-url').value=option.dataset.url || '';
}});
</script>
"""


def _studio_css() -> str:
    return """
<style>
.studio-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
.studio-tabs button{margin:0;background:#e7eef7;color:#102a43}
.studio-tabs button[aria-selected="true"]{background:#185adb;color:white}
.studio-panel[hidden]{display:none}.editor-toolbar{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.editor-toolbar button{margin:0;padding:8px 11px}.rich-editor{min-height:360px;background:white;border:1px solid #8093a7;border-radius:10px;padding:18px}
.module-layout{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.8fr);gap:18px}
.resource-list{list-style:none;padding:0}.resource-list li{padding:12px 0;border-bottom:1px solid #cbd6e2}
.badge{display:inline-block;border-radius:999px;background:#e7f1ff;padding:3px 9px;font-weight:700;font-size:.85rem}
iframe.preview-frame{width:100%;min-height:560px;border:1px solid #cbd6e2;border-radius:10px;background:white}
@media(max-width:850px){.module-layout{grid-template-columns:1fr}}
</style>
"""


def register_unified_authoring(app: FastAPI) -> None:
    ensure_unified_schema()
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")).startswith(PREFIX)
            or str(getattr(route, "path", "")).startswith("/course-studio")
            or str(getattr(route, "path", "")).startswith("/course-builder")
        )
    ]
    app.openapi_schema = None

    @app.get("/course-studio", response_model=None)
    async def legacy_course_studio():
        return RedirectResponse(PREFIX, status_code=303)

    @app.get(PREFIX, response_class=HTMLResponse, response_model=None)
    async def authoring_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC,id DESC"))
        cards = "".join(
            f'<section class="card"><h3>{html.escape(str(c["course_code"]))}: {html.escape(str(c["title"]))}</h3>'
            f'<p>{html.escape(str(c.get("description") or ""))}</p>'
            f'<a class="button" href="{PREFIX}/courses/{c["id"]}">Abrir curso</a></section>'
            for c in courses
        ) or '<p class="notice">No hay cursos. Cree el primero.</p>'
        body = f"""
<h2>NEXUS Unified Course Studio</h2>
<p>Todo el diseño académico se administra desde el curso y sus módulos.</p>
<div class="grid">
<section class="card"><h3>Crear curso</h3>
<form method="post" action="{PREFIX}/courses">
<label>Código<input name="course_code" required maxlength="40"></label>
<label>Título<input name="title" required maxlength="180"></label>
<label>Descripción<textarea name="description"></textarea></label>
<label>Periodo<input name="term" placeholder="Agosto-Diciembre 2026"></label>
<label>Profesor<input type="email" name="instructor_email"></label>
<label>Plantilla<select name="template">
<option value="blank">Curso en blanco</option><option value="5e">Modelo 5E</option>
<option value="backward">Diseño inverso</option><option value="project">Aprendizaje por proyectos</option>
<option value="immersive">Aprendizaje inmersivo AR/VR</option></select></label>
<button>Crear curso</button></form></section>
<section class="card"><h3>Modelo recomendado</h3>
<p>Editor nativo con guardado en PostgreSQL, recursos Google vinculados, exportación OpenDocument y actividades interactivas embebibles.</p></section>
</div>
<h2>Cursos</h2><div class="grid">{cards}</div>
"""
        return page("Unified Course Studio", body, user)

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
        user = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        title = title.strip()
        if not code or not title:
            raise HTTPException(400, "Código y título son obligatorios.")
        with db() as conn:
            if database_url().startswith("postgres"):
                row = execute(
                    conn,
                    """INSERT INTO nexus_admin_courses
                    (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (code, title, description.strip(), term.strip(), "draft", instructor_email.strip().lower(), user["email"], utcnow(), utcnow()),
                ).fetchone()
                course_id = int(row[0])
            else:
                cursor = execute(
                    conn,
                    """INSERT INTO nexus_admin_courses
                    (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (code, title, description.strip(), term.strip(), "draft", instructor_email.strip().lower(), user["email"], utcnow(), utcnow()),
                )
                course_id = int(cursor.lastrowid)
            if template != "blank":
                for position, (mod_title, mod_desc, outcomes) in enumerate(_template_modules(template, title), 1):
                    execute(
                        conn,
                        """INSERT INTO nexus_modules
                        (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (course_id, mod_title, mod_desc, outcomes, 60, position, "draft", utcnow(), utcnow()),
                    )
            audit(conn, user["email"], "unified_course_created", "course", str(course_id), template, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def course_page(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                totals = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module["id"],)))
                module["total"] = int(totals[0].get("total") or 0) if totals else 0
        module_cards = "".join(
            f'<section class="card"><h3>Módulo {m["position"]}: {html.escape(str(m["title"]))}</h3>'
            f'<p>{html.escape(str(m.get("description") or ""))}</p>'
            f'<p><span class="badge">{m["total"]} recursos o actividades</span></p>'
            f'<a class="button" href="{PREFIX}/modules/{m["id"]}">Abrir Studio del módulo</a></section>'
            for m in modules
        ) or '<p class="notice">Cree el primer módulo.</p>'
        body = f"""
<p><a href="{PREFIX}">&larr; Cursos</a></p>
<h2>{html.escape(str(course["course_code"]))}: {html.escape(str(course["title"]))}</h2>
<div class="grid">
<section class="card"><h3>Crear módulo</h3>
<form method="post" action="{PREFIX}/courses/{course_id}/modules">
<label>Título<input name="title" required></label>
<label>Descripción<textarea name="description"></textarea></label>
<label>Resultados de aprendizaje<textarea name="learning_outcomes"></textarea></label>
<label>Duración estimada<input type="number" name="estimated_minutes" min="1" value="60"></label>
<label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label>
<button>Crear módulo</button></form></section>
<section class="card"><h3>Diseño con IA</h3>
<form method="post" action="{PREFIX}/courses/{course_id}/ai-plan">
<label>Objetivos o competencias<textarea name="objectives"></textarea></label>
<label>Modelo<select name="template"><option value="5e">5E</option><option value="backward">Diseño inverso</option><option value="project">Proyectos</option><option value="immersive">AR/VR</option></select></label>
<button>Generar módulos</button></form></section>
</div>
<h2>Módulos</h2><div class="grid">{module_cards}</div>
{_studio_css()}
"""
        return page("Curso", body, user)

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
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            _course(conn, course_id)
            execute(
                conn,
                """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (course_id, title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), "draft", utcnow(), utcnow()),
            )
            audit(conn, user["email"], "unified_module_created", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.post(f"{PREFIX}/courses/{{course_id}}/ai-plan", response_model=None)
    async def ai_plan(
        course_id: int,
        request: Request,
        objectives: str = Form(""),
        template: str = Form("5e"),
    ):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            count = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE course_id=?", (course_id,)))
            start = int(count[0].get("total") or 0) + 1 if count else 1
            for offset, (title, description, outcomes) in enumerate(_template_modules(template, str(course["title"]))):
                extra = f" Objetivos institucionales: {objectives.strip()}" if objectives.strip() else ""
                execute(
                    conn,
                    """INSERT INTO nexus_modules
                    (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (course_id, title, description + extra, outcomes, 60, start + offset, "draft", utcnow(), utcnow()),
                )
            audit(conn, user["email"], "unified_ai_plan", "course", str(course_id), template, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{PREFIX}/modules/{{module_id}}", response_class=HTMLResponse, response_model=None)
    async def module_studio(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, int(module["course_id"]))
            drafts = rows(execute(conn, "SELECT * FROM nexus_module_drafts WHERE module_id=?", (module_id,)))
            items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
        draft = drafts[0] if drafts else {"title": f"Contenido de {module['title']}", "body_html": "<h2>Introducción</h2><p>Escriba el contenido del módulo.</p>"}
        content_items = [x for x in items if x["item_type"] in CONTENT_TYPES]
        activity_items = [x for x in items if x["item_type"] in ACTIVITY_TYPES]
        resources = "".join(
            f'<li><span class="badge">{html.escape(str(x["item_type"]))}</span> <strong>{html.escape(str(x["title"]))}</strong> '
            f'<a href="{PREFIX}/items/{x["id"]}/preview" target="_blank">Vista previa</a></li>'
            for x in content_items
        ) or "<li>Sin recursos adicionales.</li>"
        activities = "".join(
            f'<li><span class="badge">{html.escape(ACTIVITY_TYPES.get(str(x["item_type"]), str(x["item_type"])))}</span> '
            f'<strong>{html.escape(str(x["title"]))}</strong> '
            f'<a href="{PREFIX}/items/{x["id"]}/preview" target="_blank">Abrir</a>'
            + (f' · <a href="{PREFIX}/items/{x["id"]}/forum">Foro</a>' if x["item_type"] == "discussion" else "")
            + "</li>"
            for x in activity_items
        ) or "<li>Sin actividades de evaluación.</li>"
        content_options = "".join(f'<option value="{key}">{label}</option>' for key, label in CONTENT_TYPES.items())
        activity_options = "".join(f'<option value="{key}">{label}</option>' for key, label in ACTIVITY_TYPES.items())
        tool_options = "".join(
            f'<option value="{key}" data-url="{html.escape(url, quote=True)}">{html.escape(label)}</option>'
            for key, (label, url) in TOOL_PRESETS.items()
        )
        google_options = "".join(f'<option value="{kind}">{kind.title()}</option>' for kind in sorted(GOOGLE_KINDS))
        collabora = os.getenv("COLLABORA_BASE_URL", "").strip()
        office_note = (
            '<p class="notice">Collabora Online está configurado como editor OpenDocument externo.</p>'
            if collabora
            else '<p>La plataforma genera ODT, ODP y ODS. La edición embebida con Collabora puede activarse en un servicio separado.</p>'
        )
        body = f"""
<p><a href="{PREFIX}/courses/{course['id']}">&larr; Volver al curso</a></p>
<h2>{html.escape(str(course['course_code']))} · {html.escape(str(module['title']))}</h2>
<p>{html.escape(str(module.get('description') or ''))}</p>
<div class="studio-tabs" role="tablist">
<button type="button" data-tab="panel-content" aria-selected="true">Contenido</button>
<button type="button" data-tab="panel-assessment" aria-selected="false">Evaluación</button>
<button type="button" data-tab="panel-google" aria-selected="false">Google Workspace</button>
<button type="button" data-tab="panel-emerging" aria-selected="false">Tecnologías emergentes</button>
<button type="button" data-tab="panel-office" aria-selected="false">OpenDocument</button>
</div>
<section id="panel-content" class="studio-panel">
<div class="module-layout">
<section class="card"><h3>Editor del contenido principal</h3>
<form id="content-form" method="post" action="{PREFIX}/modules/{module_id}/content">
<label>Título<input id="module-content-title" name="title" value="{html.escape(str(draft['title']), quote=True)}" required></label>
<div class="editor-toolbar">
<button type="button" onclick="command('bold')">Negrita</button><button type="button" onclick="command('italic')">Cursiva</button>
<button type="button" onclick="command('insertUnorderedList')">Lista</button><button type="button" onclick="command('formatBlock','h2')">Encabezado</button>
<button type="button" onclick="insertLink()">Enlace</button><button type="button" onclick="insertImage()">Imagen</button>
</div>
<div id="module-editor" class="rich-editor" contenteditable="true">{draft['body_html']}</div>
<textarea id="module-body" name="body_html" hidden></textarea>
<p id="autosave-state" class="status">Guardado en NEXUS</p>
<button>Guardar versión</button></form></section>
<aside class="card"><h3>Recursos del módulo</h3><ul class="resource-list">{resources}</ul>
<details><summary>Añadir recurso adicional</summary>
<form method="post" action="{PREFIX}/modules/{module_id}/resources">
<label>Tipo<select name="item_type">{content_options}</select></label>
<label>Título<input name="title" required></label>
<label>Enlace externo<input type="url" name="external_url"></label>
<label>URL para iframe<input type="url" name="embed_url"></label>
<button>Añadir recurso</button></form></details></aside>
</div></section>
<section id="panel-assessment" class="studio-panel" hidden>
<div class="module-layout"><section class="card"><h3>Crear actividad de evaluación</h3>
<form method="post" action="{PREFIX}/modules/{module_id}/activities">
<label>Tipo<select name="item_type">{activity_options}</select></label>
<label>Título<input name="title" required></label>
<label>Instrucciones<textarea name="instructions"></textarea></label>
<div class="grid"><label>Puntos<input name="points" type="number" min="0" step="0.01"></label>
<label>Fecha límite<input name="due_at" type="datetime-local"></label></div>
<label>Herramienta<select id="tool-preset" name="tool_name">{tool_options}</select></label>
<label>Dirección de la herramienta o evidencia<input id="activity-tool-url" type="url" name="external_url"></label>
<label>Dirección para iframe, H5P, simulación, AR o VR<input type="url" name="embed_url"></label>
<label>Configuración de preguntas o rúbrica en JSON<textarea name="configuration_json" placeholder='{"questions":[{"prompt":"...","type":"multiple_choice","points":2}]}'></textarea></label>
<button>Crear actividad</button></form></section>
<aside class="card"><h3>Actividades del módulo</h3><ul class="resource-list">{activities}</ul></aside></div>
</section>
<section id="panel-google" class="studio-panel" hidden>
<div class="grid"><section class="card"><h3>Crear y vincular recurso Google</h3>
<p>El archivo se guarda en el Drive del usuario conectado y su enlace permanece dentro del módulo.</p>
<form method="post" action="{PREFIX}/modules/{module_id}/google">
<label>Tipo<select name="kind">{google_options}</select></label>
<label>Título<input name="title" required value="{html.escape(str(module['title']), quote=True)}"></label>
<button>Crear recurso</button></form></section>
<section class="card"><h3>Seleccionar archivo existente</h3>
<p>Seleccione archivos existentes de Drive sin salir de NEXUS.</p>
<a class="button" href="{PREFIX}/modules/{module_id}/drive">Seleccionar desde Google Drive</a></section></div>
</section>
<section id="panel-emerging" class="studio-panel" hidden>
<div class="grid"><section class="card"><h3>Herramientas gratuitas</h3>
<ul>{''.join(f'<li><a href="{url}" target="_blank" rel="noopener">{html.escape(label)}</a></li>' for label,url in TOOL_PRESETS.values() if url)}</ul></section>
<section class="card"><h3>Experiencias inmersivas</h3>
<p>Use GLB o glTF para AR, una URL WebXR/A-Frame para VR, o una experiencia 360 como actividad evaluada.</p>
<p>Las experiencias se añaden desde la pestaña Evaluación y se muestran mediante model-viewer o iframe WebXR.</p></section></div>
</section>
<section id="panel-office" class="studio-panel" hidden>
<div class="grid"><section class="card"><h3>OpenDocument</h3>{office_note}
<a class="button" href="{PREFIX}/modules/{module_id}/odf/odt">Descargar ODT</a>
<a class="button" href="{PREFIX}/modules/{module_id}/odf/odp">Descargar ODP</a>
<a class="button" href="{PREFIX}/modules/{module_id}/odf/ods">Descargar ODS</a></section>
<section class="card"><h3>Flujo recomendado</h3><p>Edite y guarde el contenido en NEXUS; exporte una copia compatible con LibreOffice/OpenOffice cuando la necesite.</p></section></div>
</section>
{_studio_css()}
{_editor_script(module_id)}
"""
        return page("Studio del módulo", body, user)

    @app.post(f"{PREFIX}/modules/{{module_id}}/autosave", response_class=JSONResponse, response_model=None)
    async def autosave(module_id: int, request: Request, title: str = Form(...), body_html: str = Form("")):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            _module(conn, module_id)
            found = rows(execute(conn, "SELECT id FROM nexus_module_drafts WHERE module_id=?", (module_id,)))
            if found:
                execute(conn, "UPDATE nexus_module_drafts SET title=?,body_html=?,updated_by=?,updated_at=? WHERE module_id=?",
                        (title.strip(), sanitize_html(body_html), user["email"], utcnow(), module_id))
            else:
                execute(conn, "INSERT INTO nexus_module_drafts (module_id,title,body_html,updated_by,updated_at) VALUES (?,?,?,?,?)",
                        (module_id, title.strip(), sanitize_html(body_html), user["email"], utcnow()))
        return JSONResponse({"ok": True, "saved_at": utcnow()})

    @app.post(f"{PREFIX}/modules/{{module_id}}/content", response_model=None)
    async def save_content(module_id: int, request: Request, title: str = Form(...), body_html: str = Form("")):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            _module(conn, module_id)
            found = rows(execute(conn, "SELECT id FROM nexus_module_drafts WHERE module_id=?", (module_id,)))
            if found:
                execute(conn, "UPDATE nexus_module_drafts SET title=?,body_html=?,updated_by=?,updated_at=? WHERE module_id=?",
                        (title.strip(), sanitize_html(body_html), user["email"], utcnow(), module_id))
            else:
                execute(conn, "INSERT INTO nexus_module_drafts (module_id,title,body_html,updated_by,updated_at) VALUES (?,?,?,?,?)",
                        (module_id, title.strip(), sanitize_html(body_html), user["email"], utcnow()))
            audit(conn, user["email"], "module_content_saved", "module", str(module_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{PREFIX}/modules/{{module_id}}/resources", response_model=None)
    async def create_resource(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), external_url: str = Form(""), embed_url: str = Form("")):
        user = require_admin(request, {"course_admin"})
        if item_type not in CONTENT_TYPES:
            raise HTTPException(400, "Tipo de contenido inválido.")
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, item_type, title, external_url=external_url, embed_url=embed_url)
            audit(conn, user["email"], "module_resource_created", "module", str(module_id), item_type, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{PREFIX}/modules/{{module_id}}/activities", response_model=None)
    async def create_activity(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), instructions: str = Form(""), points: str = Form(""), due_at: str = Form(""), tool_name: str = Form("native"), external_url: str = Form(""), embed_url: str = Form(""), configuration_json: str = Form("")):
        user = require_admin(request, {"course_admin"})
        if item_type not in ACTIVITY_TYPES:
            raise HTTPException(400, "Tipo de evaluación inválido.")
        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Puntuación inválida.") from exc
        configuration: dict[str, Any] = {"tool": tool_name}
        if configuration_json.strip():
            try:
                parsed = json.loads(configuration_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, "La configuración JSON no es válida.") from exc
            if not isinstance(parsed, dict):
                raise HTTPException(400, "La configuración debe ser un objeto JSON.")
            configuration.update(parsed)
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, item_type, title, body_html=f"<h2>Instrucciones</h2><p>{html.escape(instructions.strip())}</p>", external_url=external_url, embed_url=embed_url, metadata=configuration, points=points_value, due_at=due_at)
            audit(conn, user["email"], "assessment_created", "module", str(module_id), f"{item_type}:{tool_name}", request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{PREFIX}/modules/{{module_id}}/google", response_model=None)
    async def create_google(module_id: int, request: Request, kind: str = Form(...), title: str = Form(...)):
        user = require_admin(request, {"course_admin"})
        if kind not in GOOGLE_KINDS:
            raise HTTPException(400, "Tipo de recurso Google inválido.")
        with db() as conn:
            _module(conn, module_id)
        url, item_type = await _create_google_resource(request, kind, title.strip())
        with db() as conn:
            _insert_item(conn, module_id, item_type, title, external_url=url, metadata={"google_kind": kind})
            audit(conn, user["email"], "google_resource_created", "module", str(module_id), kind, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)

    @app.get(f"{PREFIX}/modules/{{module_id}}/drive", response_class=HTMLResponse, response_model=None)
    async def drive_selector(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            _module(conn, module_id)
        payload = await google_get(request, "https://www.googleapis.com/drive/v3/files", params={"q": "trashed=false", "pageSize": 30, "orderBy": "modifiedTime desc", "fields": "files(id,name,mimeType,webViewLink,modifiedTime)"})
        cards = []
        for file in payload.get("files", []):
            file_id = html.escape(str(file.get("id", "")), quote=True)
            name = html.escape(str(file.get("name", "Archivo")), quote=True)
            mime = html.escape(str(file.get("mimeType", "")), quote=True)
            link = html.escape(str(file.get("webViewLink", "")), quote=True)
            cards.append(f'<section class="card"><h3>{name}</h3><p>{mime}</p><form method="post" action="{PREFIX}/modules/{module_id}/drive-link"><input type="hidden" name="file_id" value="{file_id}"><input type="hidden" name="title" value="{name}"><input type="hidden" name="mime_type" value="{mime}"><input type="hidden" name="web_view_link" value="{link}"><button>Vincular al módulo</button></form></section>')
        body = f'<p><a href="{PREFIX}/modules/{module_id}">&larr; Volver al módulo</a></p><h2>Seleccionar archivo de Google Drive</h2><div class="grid">{"".join(cards) or "<p class=notice>No se encontraron archivos.</p>"}</div>'
        return page("Google Drive", body, user)

    @app.post(f"{PREFIX}/modules/{{module_id}}/drive-link", response_model=None)
    async def link_drive_file(module_id: int, request: Request, file_id: str = Form(...), title: str = Form(...), mime_type: str = Form(""), web_view_link: str = Form(...)):
        user = require_admin(request, {"course_admin"})
        item_type = "document"
        if "presentation" in mime_type:
            item_type = "presentation"
        elif "spreadsheet" in mime_type:
            item_type = "spreadsheet"
        elif "form" in mime_type:
            item_type = "assessment"
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, item_type, title, external_url=web_view_link, metadata={"google_drive_file_id": file_id, "mime_type": mime_type})
            audit(conn, user["email"], "drive_file_linked", "module", str(module_id), file_id, request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/modules/{module_id}", status_code=303)

    @app.get(f"{PREFIX}/modules/{{module_id}}/odf/{{kind}}", response_model=None)
    async def odf_download(module_id: int, kind: str, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, int(module["course_id"]))
        return _odf_response(kind, course, module)

    @app.get(f"{PREFIX}/items/{{item_id}}/forum", response_class=HTMLResponse, response_model=None)
    async def discussion_forum(item_id: int, request: Request):
        user = require_admin(request, {"course_admin", "support"})
        with db() as conn:
            item = _item(conn, item_id)
            if item.get("item_type") != "discussion":
                raise HTTPException(400, "Esta actividad no es un foro.")
            posts = rows(execute(conn, "SELECT * FROM nexus_forum_posts WHERE item_id=? ORDER BY id", (item_id,)))
        rendered = "".join(f'<article class="card"><b>{html.escape(str(post["author_email"]))}</b><p>{html.escape(str(post["body"]))}</p><small>{html.escape(str(post["created_at"]))}</small></article>' for post in posts) or '<p class="notice">No hay aportaciones.</p>'
        body = f'<p><a href="{PREFIX}/items/{item_id}/preview">&larr; Vista previa</a></p><h2>Foro: {html.escape(str(item["title"]))}</h2><section class="card"><form method="post"><label>Aportación<textarea name="body" required maxlength="5000"></textarea></label><button>Publicar</button></form></section>{rendered}'
        return page("Foro de discusión", body, user)

    @app.post(f"{PREFIX}/items/{{item_id}}/forum", response_model=None)
    async def discussion_forum_post(item_id: int, request: Request, body: str = Form(...)):
        user = require_admin(request, {"course_admin", "support"})
        clean = body.strip()
        if not clean:
            raise HTTPException(400, "La aportación está vacía.")
        with db() as conn:
            item = _item(conn, item_id)
            if item.get("item_type") != "discussion":
                raise HTTPException(400, "Esta actividad no es un foro.")
            execute(conn, "INSERT INTO nexus_forum_posts (item_id,author_email,body,created_at) VALUES (?,?,?,?)", (item_id, user["email"], clean, utcnow()))
            audit(conn, user["email"], "discussion_post_created", "item", str(item_id), "", request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/items/{item_id}/forum", status_code=303)

    @app.get(f"{PREFIX}/items/{{item_id}}/preview", response_class=HTMLResponse, response_model=None)
    async def preview_item(item_id: int, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            item = _item(conn, item_id)
        title = html.escape(str(item.get("title") or "Contenido"))
        external = ""
        if item.get("external_url"):
            url = html.escape(str(item["external_url"]), quote=True)
            external = f'<p><a href="{url}" target="_blank" rel="noopener">Abrir recurso o editor</a></p>'
        embed = ""
        if item.get("embed_url"):
            url = html.escape(str(item["embed_url"]), quote=True)
            if item.get("item_type") == "ar":
                embed = f'<model-viewer src="{url}" camera-controls ar ar-modes="webxr scene-viewer quick-look" style="width:100%;height:620px"></model-viewer><script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>'
            else:
                embed = f'<iframe class="preview-frame" src="{url}" title="{title}" allow="fullscreen; xr-spatial-tracking"></iframe>'
        return HTMLResponse(f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{_studio_css()}</head><body style="font:17px/1.6 system-ui;max-width:1100px;margin:auto;padding:28px"><h1>{title}</h1>{item.get("body_html") or ""}{external}{embed}</body></html>')
