from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import bleach
import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.admin_console import audit, db, database_url, execute, page, require_admin, rows, utcnow
from app.google_api import google_post

CONTENT_TYPES = (
    "page", "document", "presentation", "spreadsheet", "link", "video", "audio",
    "image", "pdf", "embed", "diagram", "math", "interactive", "ar", "vr",
    "assignment", "discussion", "assessment", "rubric", "announcement",
)
STATES = {"draft", "published", "scheduled", "hidden"}
GOOGLE_KINDS = {"docs", "slides", "sheets", "forms", "quiz", "meet"}
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6",
    "br", "hr", "ul", "ol", "li", "blockquote", "pre", "code",
    "img", "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTES = {
    "*": ["class", "title", "aria-label"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "th": ["scope", "colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}


def _pk() -> str:
    return "INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY" if database_url().startswith("postgres") else "INTEGER PRIMARY KEY AUTOINCREMENT"


def ensure_schema() -> None:
    pk = _pk()
    statements = [
        f"""CREATE TABLE IF NOT EXISTS nexus_modules (
            id {pk}, course_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT,
            learning_outcomes TEXT, estimated_minutes INTEGER NOT NULL DEFAULT 60,
            position INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS nexus_content_items (
            id {pk}, module_id INTEGER NOT NULL, item_type TEXT NOT NULL, title TEXT NOT NULL,
            body_html TEXT, external_url TEXT, embed_url TEXT, metadata_json TEXT,
            points REAL, due_at TEXT, position INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS nexus_forum_posts (
            id {pk}, item_id INTEGER NOT NULL, author_email TEXT NOT NULL,
            body TEXT NOT NULL, created_at TEXT NOT NULL
        )""",
    ]
    with db() as conn:
        for statement in statements:
            execute(conn, statement)
        for column_sql in (
            "ALTER TABLE nexus_modules ADD COLUMN learning_outcomes TEXT",
            "ALTER TABLE nexus_modules ADD COLUMN estimated_minutes INTEGER NOT NULL DEFAULT 60",
        ):
            try:
                execute(conn, column_sql)
            except Exception:
                pass


def one(conn: Any, sql: str, params: tuple[Any, ...], message: str) -> dict[str, Any]:
    result = rows(execute(conn, sql, params))
    if not result:
        raise HTTPException(404, message)
    return result[0]


def safe_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "La dirección debe utilizar http o https.")
    return value


def sanitize_html(value: str) -> str:
    return bleach.clean(
        value,
        tags=sorted(ALLOWED_TAGS),
        attributes=ALLOWED_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def tools_html() -> str:
    tools = [
        ("Google Docs", "https://docs.new"),
        ("Google Slides", "https://slides.new"),
        ("Google Sheets", "https://sheets.new"),
        ("Google Forms", "https://forms.new"),
        ("Google Meet", "https://meet.google.com/new"),
        ("Lumi H5P", "https://lumi.education"),
        ("JupyterLite", "https://jupyter.org/try-jupyter/lab/"),
        ("PhET", "https://phet.colorado.edu/"),
        ("GeoGebra", "https://www.geogebra.org/classic"),
        ("diagrams.net", "https://app.diagrams.net"),
        ("Excalidraw", "https://excalidraw.com"),
        ("Mermaid", "https://mermaid.live"),
        ("Twine", "https://twinery.org/"),
        ("Scratch", "https://scratch.mit.edu/projects/editor/"),
        ("A-Frame", "https://aframe.io/"),
        ("Blender", "https://www.blender.org/"),
    ]
    return "".join(
        f'<a class="button" href="{url}" target="_blank" rel="noopener">{html.escape(name)}</a> '
        for name, url in tools
    )


def editor_script() -> str:
    return """
<script>
function command(name,value=null){document.execCommand(name,false,value);syncContent();}
function syncContent(){const e=document.getElementById('editor');const f=document.getElementById('body_html');if(e&&f){f.value=e.innerHTML;}}
function insertLink(){const u=prompt('URL https://');if(u){command('createLink',u);}}
function insertImage(){const u=prompt('URL de la imagen');if(u){command('insertImage',u);}}
document.addEventListener('DOMContentLoaded',()=>{const form=document.getElementById('content-form');if(form){form.addEventListener('submit',syncContent);}});
</script>
"""


def _course(conn: Any, course_id: int) -> dict[str, Any]:
    return one(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,), "Curso no encontrado")


def _module(conn: Any, module_id: int) -> dict[str, Any]:
    return one(conn, "SELECT * FROM nexus_modules WHERE id=?", (module_id,), "Módulo no encontrado")


def _item(conn: Any, item_id: int) -> dict[str, Any]:
    return one(conn, "SELECT * FROM nexus_content_items WHERE id=?", (item_id,), "Contenido no encontrado")


def _template_modules(template: str, title: str) -> list[tuple[str, str, str]]:
    templates: dict[str, list[tuple[str, str, str]]] = {
        "5e": [
            ("1. Conectar", "Activación de conocimientos previos y situación auténtica.", "Relacionar experiencias previas con el problema central."),
            ("2. Explorar", "Investigación guiada, simulación o actividad interactiva.", "Observar, formular preguntas y recopilar evidencia."),
            ("3. Explicar", "Construcción conceptual mediante recursos multimedia.", "Explicar conceptos con evidencia y vocabulario disciplinar."),
            ("4. Elaborar", "Aplicación mediante proyecto, caso, AR o VR.", "Transferir el aprendizaje a un contexto nuevo."),
            ("5. Evaluar", "Evaluación formativa y sumativa con rúbrica.", "Demostrar dominio y reflexionar sobre el aprendizaje."),
        ],
        "backward": [
            ("1. Resultados esperados", "Resultados, competencias y criterios de éxito.", "Definir evidencias observables de aprendizaje."),
            ("2. Evidencias", "Tareas auténticas, rúbricas y examen.", "Diseñar evidencias válidas y confiables."),
            ("3. Plan de aprendizaje", "Secuencia de contenidos, práctica y retroalimentación.", "Alinear actividades con resultados y evaluación."),
        ],
        "project": [
            ("1. Reto", "Pregunta guía, contexto y producto final.", "Comprender el reto y los criterios de calidad."),
            ("2. Investigación", "Fuentes, datos y exploración colaborativa.", "Investigar y documentar evidencia."),
            ("3. Prototipo", "Diseño, prueba y mejora del producto.", "Crear y revisar un prototipo."),
            ("4. Presentación", "Entrega pública y reflexión.", "Comunicar resultados y justificar decisiones."),
        ],
        "immersive": [
            ("1. Preparación", "Objetivos, seguridad digital y navegación.", "Prepararse para una experiencia inmersiva."),
            ("2. Exploración 3D", "Modelo 3D, AR o escenario VR.", "Observar e interactuar con el entorno."),
            ("3. Misión", "Reto contextualizado dentro de la experiencia.", "Aplicar conceptos para resolver una misión."),
            ("4. Evidencia", "Informe, presentación o reflexión evaluada.", "Documentar decisiones y aprendizaje."),
        ],
    }
    return templates.get(template, [
        ("1. Introducción", f"Bienvenida y panorama de {title}.", "Reconocer los conceptos y expectativas principales."),
        ("2. Contenido esencial", "Recursos, ejemplos y práctica guiada.", "Aplicar los conceptos fundamentales."),
        ("3. Aplicación", "Actividad auténtica o proyecto.", "Transferir el aprendizaje a una situación real."),
        ("4. Evaluación", "Evidencia de dominio y retroalimentación.", "Demostrar el logro de los resultados."),
    ])


async def _external_ai_plan(course: dict[str, Any], objectives: str, template: str) -> list[dict[str, str]] | None:
    base_url = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("AI_MODEL", "llama3.2").strip()
    style = os.getenv("AI_API_STYLE", "openai").strip().lower()
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not base_url:
        return None
    prompt = (
        "Diseña módulos de un curso universitario en español. Devuelve exclusivamente JSON "
        "como una lista de objetos con title, description y outcomes. "
        f"Curso: {course['title']}. Plantilla: {template}. Objetivos: {objectives}"
    )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=45) as client:
        if style == "ollama":
            response = await client.post(
                f"{base_url}/api/generate",
                headers=headers,
                json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            text = response.json().get("response", "")
        else:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        parsed = parsed.get("modules", [])
    if not isinstance(parsed, list):
        return None
    clean: list[dict[str, str]] = []
    for entry in parsed[:12]:
        if isinstance(entry, dict) and str(entry.get("title", "")).strip():
            clean.append({
                "title": str(entry["title"]).strip(),
                "description": str(entry.get("description", "")).strip(),
                "outcomes": str(entry.get("outcomes", "")).strip(),
            })
    return clean or None


def _google_link(kind: str, payload: dict[str, Any]) -> tuple[str, str]:
    if kind == "docs":
        file_id = str(payload.get("id", ""))
        return f"https://docs.google.com/document/d/{file_id}/edit", "document"
    if kind == "slides":
        file_id = str(payload.get("id", ""))
        return f"https://docs.google.com/presentation/d/{file_id}/edit", "presentation"
    if kind == "sheets":
        file_id = str(payload.get("id", ""))
        return f"https://docs.google.com/spreadsheets/d/{file_id}/edit", "spreadsheet"
    if kind in {"forms", "quiz"}:
        form_id = str(payload.get("formId", ""))
        return str(payload.get("responderUri") or f"https://docs.google.com/forms/d/{form_id}/edit"), "assessment"
    if kind == "meet":
        return str(payload.get("hangoutLink") or payload.get("htmlLink") or ""), "video"
    return "", "link"


async def _create_google_resource(request: Request, kind: str, title: str) -> tuple[str, str]:
    if kind in {"docs", "slides", "sheets"}:
        mime_types = {
            "docs": "application/vnd.google-apps.document",
            "slides": "application/vnd.google-apps.presentation",
            "sheets": "application/vnd.google-apps.spreadsheet",
        }
        payload = await google_post(
            request,
            "https://www.googleapis.com/drive/v3/files",
            {"name": title, "mimeType": mime_types[kind]},
            params={"fields": "id,name,webViewLink"},
        )
        return _google_link(kind, payload)
    if kind in {"forms", "quiz"}:
        payload = await google_post(
            request,
            "https://forms.googleapis.com/v1/forms",
            {"info": {"title": title, "documentTitle": title}},
        )
        form_id = payload.get("formId")
        if kind == "quiz" and form_id:
            await google_post(
                request,
                f"https://forms.googleapis.com/v1/forms/{form_id}:batchUpdate",
                {"requests": [{"updateSettings": {"settings": {"quizSettings": {"isQuiz": True}}, "updateMask": "quizSettings.isQuiz"}}]},
            )
        return _google_link(kind, payload)
    if kind == "meet":
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        payload = await google_post(
            request,
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            {
                "summary": title,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
                "conferenceData": {"createRequest": {"requestId": f"nexus-{int(start.timestamp())}"}},
            },
            params={"conferenceDataVersion": 1},
        )
        return _google_link(kind, payload)
    raise HTTPException(400, "Tipo de recurso de Google inválido.")


def _odf_response(kind: str, course: dict[str, Any], module: dict[str, Any]) -> StreamingResponse:
    from odf.opendocument import OpenDocumentPresentation, OpenDocumentSpreadsheet, OpenDocumentText
    from odf import draw, table, text

    title = f"{course['course_code']} - {module['title']}"
    if kind == "odt":
        doc = OpenDocumentText()
        doc.text.addElement(text.H(outlinelevel=1, text=title))
        doc.text.addElement(text.P(text=str(module.get("description") or "")))
        doc.text.addElement(text.H(outlinelevel=2, text="Resultados de aprendizaje"))
        doc.text.addElement(text.P(text=str(module.get("learning_outcomes") or "")))
        ext = "odt"
        media = "application/vnd.oasis.opendocument.text"
    elif kind == "odp":
        doc = OpenDocumentPresentation()
        page1 = draw.Page(masterpagename="Default", name="Portada")
        frame = draw.Frame(width="24cm", height="4cm", x="1cm", y="2cm")
        box = draw.TextBox()
        box.addElement(text.P(text=title))
        frame.addElement(box)
        page1.addElement(frame)
        doc.presentation.addElement(page1)
        page2 = draw.Page(masterpagename="Default", name="Resultados")
        frame2 = draw.Frame(width="24cm", height="12cm", x="1cm", y="2cm")
        box2 = draw.TextBox()
        box2.addElement(text.P(text=str(module.get("learning_outcomes") or "")))
        frame2.addElement(box2)
        page2.addElement(frame2)
        doc.presentation.addElement(page2)
        ext = "odp"
        media = "application/vnd.oasis.opendocument.presentation"
    elif kind == "ods":
        doc = OpenDocumentSpreadsheet()
        sheet = table.Table(name="Plan del módulo")
        for values in (
            ("Campo", "Contenido"),
            ("Curso", str(course["title"])),
            ("Módulo", str(module["title"])),
            ("Descripción", str(module.get("description") or "")),
            ("Resultados", str(module.get("learning_outcomes") or "")),
            ("Duración (min)", str(module.get("estimated_minutes") or 60)),
        ):
            row = table.TableRow()
            for value in values:
                cell = table.TableCell(valuetype="string")
                cell.addElement(text.P(text=value))
                row.addElement(cell)
            sheet.addElement(row)
        doc.spreadsheet.addElement(sheet)
        ext = "ods"
        media = "application/vnd.oasis.opendocument.spreadsheet"
    else:
        raise HTTPException(404, "Formato OpenDocument no reconocido.")
    stream = BytesIO()
    doc.save(stream)
    stream.seek(0)
    filename = f"{course['course_code']}-modulo-{module['id']}.{ext}".replace(" ", "-")
    return StreamingResponse(stream, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def register_authoring_v6(app: FastAPI) -> None:
    ensure_schema()
    prefix = "/admin/authoring"
    app.router.routes = [
        route for route in app.router.routes
        if not str(getattr(route, "path", "")).startswith(prefix)
    ]
    app.openapi_schema = None

    @app.get(prefix, response_class=HTMLResponse)
    async def authoring_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC,id DESC"))
        cards = "".join(
            f'<section class="card"><h3>{html.escape(str(c["course_code"]))}: {html.escape(str(c["title"]))}</h3>'
            f'<p>{html.escape(str(c.get("description") or ""))}</p>'
            f'<a class="button" href="{prefix}/courses/{c["id"]}">Diseñar curso</a></section>'
            for c in courses
        ) or '<p class="notice">No hay cursos. Cree el primero.</p>'
        body = f"""
<h2>NEXUS Course Studio V6</h2>
<p>Diseñador integral con Google Workspace, OpenDocument, IA, contenido interactivo, AR y VR.</p>
<div class="grid">
<section class="card">
<h3>Crear curso</h3>
<form method="post" action="{prefix}/courses">
<label>Código<input name="course_code" required maxlength="40"></label>
<label>Título<input name="title" required maxlength="180"></label>
<label>Descripción<textarea name="description"></textarea></label>
<label>Periodo<input name="term" placeholder="Agosto-Diciembre 2026"></label>
<label>Profesor<input type="email" name="instructor_email"></label>
<label>Plantilla<select name="template">
<option value="blank">Curso en blanco</option>
<option value="5e">Modelo 5E</option>
<option value="backward">Diseño inverso</option>
<option value="project">Aprendizaje basado en proyectos</option>
<option value="immersive">Aprendizaje inmersivo AR/VR</option>
</select></label>
<button>Crear curso</button>
</form>
</section>
<section class="card"><h3>Tecnologías gratuitas</h3>{tools_html()}</section>
</div>
<h2>Cursos</h2><div class="grid">{cards}</div>
"""
        return page("Course Studio V6", body, user)

    @app.post(f"{prefix}/courses")
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
                    "INSERT INTO nexus_admin_courses (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?) RETURNING id",
                    (code, title, description.strip(), term.strip(), "draft", instructor_email.strip().lower(), user["email"], utcnow(), utcnow()),
                ).fetchone()
                course_id = int(row[0])
            else:
                cursor = execute(
                    conn,
                    "INSERT INTO nexus_admin_courses (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (code, title, description.strip(), term.strip(), "draft", instructor_email.strip().lower(), user["email"], utcnow(), utcnow()),
                )
                course_id = int(cursor.lastrowid)
            if template != "blank":
                for position, (mod_title, mod_desc, outcomes) in enumerate(_template_modules(template, title), start=1):
                    execute(
                        conn,
                        "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (course_id, mod_title, mod_desc, outcomes, 60, position, "draft", utcnow(), utcnow()),
                    )
            audit(conn, user["email"], "course_created_v6", "course", str(course_id), f"{code}:{template}", request.client.host if request.client else "")
        return RedirectResponse(f"{prefix}/courses/{course_id}", status_code=303)

    @app.get(f"{prefix}/courses/{{course_id}}", response_class=HTMLResponse)
    async def course_page(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                module["items"] = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module["id"],)))
        module_cards = []
        for module in modules:
            item_list = "".join(
                f'<li><strong>{html.escape(str(item["title"]))}</strong> · {html.escape(str(item["item_type"]))} '
                f'<a href="{prefix}/items/{item["id"]}/preview" target="_blank">Vista previa</a>'
                + (f' · <a href="{prefix}/items/{item["id"]}/forum">Foro</a>' if item["item_type"] == "discussion" else "")
                + '</li>'
                for item in module["items"]
            ) or "<li>Sin contenido.</li>"
            module_cards.append(f"""
<section class="card">
<h3>Módulo {module['position']}: {html.escape(str(module['title']))}</h3>
<p>{html.escape(str(module.get('description') or ''))}</p>
<p><b>Resultados:</b> {html.escape(str(module.get('learning_outcomes') or ''))}</p>
<a class="button" href="{prefix}/modules/{module['id']}/items/new">Añadir contenido</a>
<a class="button" href="{prefix}/modules/{module['id']}/odf/odt">ODT</a>
<a class="button" href="{prefix}/modules/{module['id']}/odf/odp">ODP</a>
<a class="button" href="{prefix}/modules/{module['id']}/odf/ods">ODS</a>
<details><summary>Crear con Google</summary>
<form method="post" action="{prefix}/modules/{module['id']}/google">
<label>Tipo<select name="kind"><option>docs</option><option>slides</option><option>sheets</option><option>forms</option><option>quiz</option><option>meet</option></select></label>
<label>Título<input name="title" required value="{html.escape(str(module['title']), quote=True)}"></label>
<button>Crear y vincular</button>
</form></details>
<ul>{item_list}</ul>
</section>
""")
        modules_html = "".join(module_cards) or '<p class="notice">Cree el primer módulo.</p>'
        body = f"""
<p><a href="{prefix}">&larr; Cursos</a></p>
<h2>{html.escape(str(course['course_code']))}: {html.escape(str(course['title']))}</h2>
<div class="grid">
<section class="card">
<h3>Crear módulo</h3>
<form method="post" action="{prefix}/courses/{course_id}/modules">
<label>Título<input name="title" required></label>
<label>Descripción<textarea name="description"></textarea></label>
<label>Resultados de aprendizaje<textarea name="learning_outcomes"></textarea></label>
<label>Duración estimada en minutos<input type="number" name="estimated_minutes" min="1" value="60"></label>
<label>Posición<input type="number" name="position" min="1" value="{len(modules)+1}"></label>
<button>Crear módulo</button>
</form>
</section>
<section class="card">
<h3>Diseñador con IA</h3>
<form method="post" action="{prefix}/courses/{course_id}/ai-plan">
<label>Objetivos o competencias<textarea name="objectives"></textarea></label>
<label>Modelo<select name="template"><option value="5e">5E</option><option value="backward">Diseño inverso</option><option value="project">Proyectos</option><option value="immersive">AR/VR</option></select></label>
<button>Generar módulos</button>
</form>
</section>
</div>
<h2>Módulos</h2>{modules_html}
"""
        return page("Diseñar curso", body, user)

    @app.post(f"{prefix}/courses/{{course_id}}/modules")
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
                "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (course_id, title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), max(1, position), "draft", utcnow(), utcnow()),
            )
            audit(conn, user["email"], "module_created_v6", "course", str(course_id), title.strip(), request.client.host if request.client else "")
        return RedirectResponse(f"{prefix}/courses/{course_id}", status_code=303)

    @app.post(f"{prefix}/courses/{{course_id}}/ai-plan")
    async def ai_plan(
        course_id: int,
        request: Request,
        objectives: str = Form(""),
        template: str = Form("5e"),
    ):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
        generated: list[dict[str, str]] | None = None
        try:
            generated = await _external_ai_plan(course, objectives, template)
        except Exception:
            generated = None
        if generated is None:
            generated = [
                {"title": title, "description": description, "outcomes": outcomes}
                for title, description, outcomes in _template_modules(template, str(course["title"]))
            ]
        with db() as conn:
            existing = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE course_id=?", (course_id,)))
            start_position = int(existing[0]["total"]) + 1 if existing else 1
            for offset, module in enumerate(generated):
                execute(
                    conn,
                    "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (course_id, module["title"], module.get("description", ""), module.get("outcomes", ""), 60, start_position + offset, "draft", utcnow(), utcnow()),
                )
            audit(conn, user["email"], "ai_plan_generated", "course", str(course_id), template, request.client.host if request.client else "")
        return RedirectResponse(f"{prefix}/courses/{course_id}", status_code=303)

    @app.get(f"{prefix}/modules/{{module_id}}/items/new", response_class=HTMLResponse)
    async def new_item(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, int(module["course_id"]))
            result = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module_id,)))
        next_position = int(result[0]["total"]) + 1 if result else 1
        options = "".join(f'<option value="{kind}">{html.escape(kind.replace("_", " ").title())}</option>' for kind in CONTENT_TYPES)
        body = f"""
<p><a href="{prefix}/courses/{course['id']}">&larr; Volver al curso</a></p>
<h2>Añadir contenido a {html.escape(str(module['title']))}</h2>
<section class="card"><form id="content-form" method="post" action="{prefix}/modules/{module_id}/items">
<label>Tipo<select name="item_type" required>{options}</select></label>
<label>Título<input name="title" required maxlength="250"></label>
<label>Contenido</label>
<div class="toolbar"><button type="button" onclick="command('bold')">Negrita</button><button type="button" onclick="command('italic')">Cursiva</button><button type="button" onclick="command('insertUnorderedList')">Lista</button><button type="button" onclick="command('formatBlock','h2')">Encabezado</button><button type="button" onclick="insertLink()">Enlace</button><button type="button" onclick="insertImage()">Imagen</button></div>
<div id="editor" class="rich-editor" contenteditable="true"><p>Escriba aquí el contenido instruccional.</p></div>
<textarea id="body_html" name="body_html" hidden></textarea>
<label>Enlace externo<input type="url" name="external_url" placeholder="https://..."></label>
<label>URL para incrustar<input type="url" name="embed_url" placeholder="https://..."></label>
<div class="grid"><label>Puntos<input type="number" min="0" step="0.01" name="points"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label>Posición<input type="number" min="1" name="position" value="{next_position}"></label><label>Estado<select name="status"><option value="draft">Borrador</option><option value="published">Publicado</option><option value="hidden">Oculto</option></select></label></div>
<label>Configuración JSON opcional<textarea name="metadata_json" placeholder='{{"attempts": 2, "xr_mode": "ar"}}'></textarea></label>
<button>Guardar contenido</button></form></section>
<section class="card"><h3>Herramientas gratuitas</h3>{tools_html()}</section>
<style>.toolbar{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}}.toolbar button{{margin:0}}.rich-editor{{min-height:300px;background:white;border:1px solid #8093a7;border-radius:8px;padding:16px}}</style>
{editor_script()}
"""
        return page("Añadir contenido", body, user)

    @app.post(f"{prefix}/modules/{{module_id}}/items")
    async def create_item(
        module_id: int,
        request: Request,
        item_type: str = Form(...),
        title: str = Form(...),
        body_html: str = Form(""),
        external_url: str = Form(""),
        embed_url: str = Form(""),
        metadata_json: str = Form(""),
        points: str = Form(""),
        due_at: str = Form(""),
        position: int = Form(1),
        status: str = Form("draft"),
    ):
        user = require_admin(request, {"course_admin"})
        if item_type not in CONTENT_TYPES or status not in STATES:
            raise HTTPException(400, "Tipo o estado inválido.")
        metadata: dict[str, Any] = {}
        if metadata_json.strip():
            try:
                parsed = json.loads(metadata_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, "La configuración JSON no es válida.") from exc
            if not isinstance(parsed, dict):
                raise HTTPException(400, "La configuración debe ser un objeto JSON.")
            metadata = parsed
        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Puntuación inválida.") from exc
        with db() as conn:
            module = _module(conn, module_id)
            execute(
                conn,
                "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (module_id, item_type, title.strip(), sanitize_html(body_html), safe_url(external_url) or None, safe_url(embed_url) or None, json.dumps(metadata, ensure_ascii=False), points_value, due_at.strip() or None, max(1, position), status, utcnow(), utcnow()),
            )
            audit(conn, user["email"], "content_created_v6", "module", str(module_id), f"{item_type}:{title}", request.client.host if request.client else "")
        return RedirectResponse(f"{prefix}/courses/{module['course_id']}", status_code=303)

    @app.post(f"{prefix}/modules/{{module_id}}/google")
    async def create_google(module_id: int, request: Request, kind: str = Form(...), title: str = Form(...)):
        user = require_admin(request, {"course_admin"})
        if kind not in GOOGLE_KINDS:
            raise HTTPException(400, "Tipo de recurso Google inválido.")
        with db() as conn:
            module = _module(conn, module_id)
        url, item_type = await _create_google_resource(request, kind, title.strip())
        with db() as conn:
            result = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?", (module_id,)))
            position = int(result[0]["total"]) + 1 if result else 1
            execute(
                conn,
                "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (module_id, item_type, title.strip(), "", url, None, json.dumps({"google_kind": kind}, ensure_ascii=False), None, None, position, "draft", utcnow(), utcnow()),
            )
            audit(conn, user["email"], "google_resource_created", "module", str(module_id), kind, request.client.host if request.client else "")
        return RedirectResponse(f"{prefix}/courses/{module['course_id']}", status_code=303)

    @app.get(f"{prefix}/modules/{{module_id}}/odf/{{kind}}")
    async def odf_download(module_id: int, kind: str, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, int(module["course_id"]))
        return _odf_response(kind, course, module)

    @app.get(f"{prefix}/items/{{item_id}}/forum", response_class=HTMLResponse)
    async def forum(item_id: int, request: Request):
        user = require_admin(request, {"course_admin", "support"})
        with db() as conn:
            item = _item(conn, item_id)
            posts = rows(execute(conn, "SELECT * FROM nexus_forum_posts WHERE item_id=? ORDER BY id", (item_id,)))
        rendered = "".join(
            f'<article class="card"><b>{html.escape(str(post["author_email"]))}</b><p>{html.escape(str(post["body"]))}</p><small>{html.escape(str(post["created_at"]))}</small></article>'
            for post in posts
        ) or '<p class="notice">No hay aportaciones.</p>'
        body = f"""
<p><a href="{prefix}/items/{item_id}/preview">&larr; Vista previa</a></p>
<h2>Foro: {html.escape(str(item['title']))}</h2>
<section class="card"><form method="post"><label>Aportación<textarea name="body" required maxlength="5000"></textarea></label><button>Publicar</button></form></section>
{rendered}
"""
        return page("Foro", body, user)

    @app.post(f"{prefix}/items/{{item_id}}/forum")
    async def forum_post(item_id: int, request: Request, body: str = Form(...)):
        user = require_admin(request, {"course_admin", "support"})
        clean = body.strip()
        if not clean:
            raise HTTPException(400, "La aportación está vacía.")
        with db() as conn:
            _item(conn, item_id)
            execute(conn, "INSERT INTO nexus_forum_posts (item_id,author_email,body,created_at) VALUES (?,?,?,?)", (item_id, user["email"], clean, utcnow()))
            audit(conn, user["email"], "forum_post_created", "item", str(item_id), "", request.client.host if request.client else "")
        return RedirectResponse(f"{prefix}/items/{item_id}/forum", status_code=303)

    @app.get(f"{prefix}/items/{{item_id}}/preview", response_class=HTMLResponse)
    async def preview_item(item_id: int, request: Request):
        require_admin(request, {"course_admin", "support", "auditor"})
        with db() as conn:
            item = _item(conn, item_id)
        title = html.escape(str(item.get("title") or "Contenido"))
        link = ""
        if item.get("external_url"):
            url = html.escape(str(item["external_url"]), quote=True)
            link = f'<p><a href="{url}" target="_blank" rel="noopener">Abrir recurso externo</a></p>'
        embed = ""
        if item.get("embed_url"):
            url = html.escape(str(item["embed_url"]), quote=True)
            if item.get("item_type") == "ar":
                embed = f'<model-viewer src="{url}" camera-controls ar ar-modes="webxr scene-viewer quick-look" style="width:100%;height:600px"></model-viewer><script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>'
            elif item.get("item_type") == "vr":
                embed = f'<iframe src="{url}" title="Experiencia de realidad virtual" allow="xr-spatial-tracking; fullscreen" style="width:100%;min-height:650px;border:0"></iframe>'
            else:
                embed = f'<iframe src="{url}" title="Recurso" style="width:100%;min-height:600px;border:0"></iframe>'
        forum_link = f'<p><a href="{prefix}/items/{item_id}/forum">Abrir foro</a></p>' if item.get("item_type") == "discussion" else ""
        return HTMLResponse(
            f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>'
            f'<body style="font:18px/1.6 system-ui;max-width:1100px;margin:auto;padding:30px"><h1>{title}</h1>{item.get("body_html") or ""}{link}{embed}{forum_link}</body></html>'
        )
