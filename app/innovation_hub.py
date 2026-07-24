from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from typing import Any

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.admin_console import audit, db, database_url, execute, page, require_admin, rows, utcnow
from app.unified_authoring import (
    ACTIVITY_TYPES,
    PREFIX,
    TOOL_PRESETS,
    _course,
    _insert_item,
    _module,
)

HUB_PREFIX = f"{PREFIX}/innovation"
XR_TYPES = {"ar", "vr", "360"}
PUBLISH_STATES = {"draft", "published"}


class _QualityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings = 0
        self.images = 0
        self.images_without_alt = 0
        self.links = 0
        self.empty_links = 0
        self._inside_link = False
        self._link_text: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs}
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings += 1
        elif tag == "img":
            self.images += 1
            if not (attr_map.get("alt") or "").strip():
                self.images_without_alt += 1
        elif tag == "a":
            self.links += 1
            self._inside_link = True
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._inside_link:
            if not "".join(self._link_text).strip():
                self.empty_links += 1
            self._inside_link = False
            self._link_text = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.text_parts.append(text)
            if self._inside_link:
                self._link_text.append(text)


def _insert_returning_id(conn: Any, sql: str, params: tuple[Any, ...]) -> int:
    if database_url().startswith("postgres"):
        row = execute(conn, sql + " RETURNING id", params).fetchone()
        return int(row[0])
    cursor = execute(conn, sql, params)
    return int(cursor.lastrowid)


def _module_bundle(conn: Any, module_id: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    module = _module(conn, module_id)
    course = _course(conn, int(module["course_id"]))
    drafts = rows(execute(conn, "SELECT * FROM nexus_module_drafts WHERE module_id=?", (module_id,)))
    draft = drafts[0] if drafts else {"title": f"Contenido de {module['title']}", "body_html": ""}
    items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
    return course, module, draft, items


def _quality_report(module: dict[str, Any], draft: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    parser = _QualityParser()
    parser.feed(str(draft.get("body_html") or ""))
    word_count = len(re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ'-]+\b", " ".join(parser.text_parts)))
    activities = [item for item in items if str(item.get("item_type")) in ACTIVITY_TYPES]
    xr_items = [item for item in items if str(item.get("item_type")) in XR_TYPES]
    total_points = sum(float(item.get("points") or 0) for item in activities)
    checks = [
        ("Resultados de aprendizaje", bool(str(module.get("learning_outcomes") or "").strip()), "Defina resultados observables y medibles."),
        ("Contenido suficiente", word_count >= 150, f"Se detectaron {word_count} palabras; se recomiendan al menos 150 para un módulo básico."),
        ("Estructura con encabezados", parser.headings >= 1, "Use encabezados H2/H3 para organizar el contenido."),
        ("Texto alternativo", parser.images_without_alt == 0, f"Imágenes sin texto alternativo: {parser.images_without_alt}."),
        ("Enlaces descriptivos", parser.empty_links == 0, f"Enlaces sin texto descriptivo: {parser.empty_links}."),
        ("Actividad de evaluación", len(activities) >= 1, "Incluya por lo menos una actividad de evaluación."),
        ("Puntuación definida", total_points > 0, f"Puntuación total configurada: {total_points:g}."),
        ("Experiencia emergente", len(xr_items) >= 1 or any(str(item.get("item_type")) in {"h5p", "simulation", "interactive"} for item in items), "Considere H5P, simulación, RA, VR o 360 cuando aporte valor pedagógico."),
    ]
    passed = sum(1 for _, ok, _ in checks if ok)
    return {
        "score": round((passed / len(checks)) * 100),
        "checks": checks,
        "word_count": word_count,
        "activity_count": len(activities),
        "total_points": total_points,
    }


def _local_ai_html(course: dict[str, Any], module: dict[str, Any], objective: str, audience: str, mode: str) -> str:
    objective = objective.strip() or str(module.get("learning_outcomes") or "Aplicar los conceptos esenciales del módulo.")
    audience = audience.strip() or "estudiantes universitarios"
    title = html.escape(str(module.get("title") or "Módulo"))
    course_title = html.escape(str(course.get("title") or "Curso"))
    objective_html = html.escape(objective)
    audience_html = html.escape(audience)
    if mode == "assessment":
        return (
            f"<h2>Actividad auténtica: {title}</h2>"
            f"<p><strong>Contexto:</strong> El estudiantado de {audience_html} resolverá una situación vinculada con {course_title}.</p>"
            f"<p><strong>Propósito:</strong> {objective_html}</p>"
            "<h3>Producto esperado</h3><p>Prepare una evidencia digital, explique sus decisiones y cite las fuentes utilizadas.</p>"
            "<h3>Criterios</h3><ul><li>Precisión conceptual</li><li>Aplicación al contexto</li><li>Calidad de la evidencia</li><li>Comunicación y accesibilidad</li></ul>"
        )
    if mode == "immersive":
        return (
            f"<h2>Experiencia inmersiva: {title}</h2>"
            f"<p><strong>Misión:</strong> {objective_html}</p>"
            "<ol><li>Orientación y normas de seguridad digital.</li><li>Exploración guiada del modelo o escenario.</li>"
            "<li>Registro de observaciones y evidencia.</li><li>Reflexión y transferencia a una situación real.</li></ol>"
            "<h3>Alternativa accesible</h3><p>Proporcione imágenes, transcripción, descripción textual y una actividad equivalente sin visor inmersivo.</p>"
        )
    return (
        f"<h2>Introducción a {title}</h2>"
        f"<p>Este módulo forma parte de <strong>{course_title}</strong> y está dirigido a {audience_html}. "
        f"La meta principal es: {objective_html}</p>"
        "<h3>Explorar</h3><p>Active conocimientos previos mediante una pregunta auténtica, un caso breve o una demostración interactiva.</p>"
        "<h3>Comprender</h3><p>Presente los conceptos esenciales con ejemplos, recursos multimedia accesibles y práctica guiada.</p>"
        "<h3>Aplicar</h3><p>Solicite una evidencia que permita transferir el aprendizaje a un contexto académico o profesional.</p>"
        "<h3>Comprobar</h3><p>Incluya retroalimentación formativa, criterios de éxito y una oportunidad de revisión.</p>"
    )


async def _external_ai_html(course: dict[str, Any], module: dict[str, Any], objective: str, audience: str, mode: str) -> str | None:
    base_url = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        return None
    model = os.getenv("AI_MODEL", "llama3.2").strip()
    api_style = os.getenv("AI_API_STYLE", "openai").strip().lower()
    api_key = os.getenv("AI_API_KEY", "").strip()
    prompt = (
        "Redacta contenido instruccional universitario en español de Puerto Rico, claro, inclusivo y accesible. "
        "Devuelve solo HTML seguro usando h2, h3, p, ul, ol y li. "
        f"Curso: {course.get('title')}. Módulo: {module.get('title')}. Objetivo: {objective}. "
        f"Audiencia: {audience}. Modalidad solicitada: {mode}. Incluye aplicación auténtica y evaluación formativa."
    )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            if api_style == "ollama":
                response = await client.post(
                    f"{base_url}/api/generate",
                    headers=headers,
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                return str(response.json().get("response") or "").strip() or None
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"]).strip() or None
    except Exception:
        return None


def _tool_item_type(tool_name: str, graded: bool) -> str:
    if graded:
        if tool_name == "h5p":
            return "h5p"
        if tool_name in {"phet", "geogebra", "jupyterlite"}:
            return "simulation"
        return "assignment"
    return "interactive"


def register_innovation_hub(app: FastAPI) -> None:
    @app.get(HUB_PREFIX, response_class=HTMLResponse, response_model=None)
    async def innovation_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC,id DESC"))
            course_total = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_admin_courses"))[0]["total"]
            module_total = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules"))[0]["total"]
            item_total = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items"))[0]["total"]
            xr_total = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_content_items WHERE item_type IN ('ar','vr','360')"))[0]["total"]
        cards = "".join(
            f'<section class="card"><h3>{html.escape(str(course["course_code"]))}: {html.escape(str(course["title"]))}</h3>'
            f'<p>Estado: <span class="badge">{html.escape(str(course.get("status") or "draft"))}</span></p>'
            f'<a class="button" href="{HUB_PREFIX}/courses/{course["id"]}">Innovación y calidad</a> '
            f'<a class="button" href="{PREFIX}/courses/{course["id"]}">Diseñar curso</a></section>'
            for course in courses
        ) or '<p class="notice">Cree un curso en Diseño de cursos para comenzar.</p>'
        body = f"""
<h2>Centro de Innovación, IA y Experiencias Inmersivas</h2>
<p>Este centro forma parte del mismo Course Studio y utiliza los mismos cursos, módulos, usuarios, permisos y base de datos.</p>
<div class="grid"><div class="card metric"><strong>{course_total}</strong>Cursos</div><div class="card metric"><strong>{module_total}</strong>Módulos</div><div class="card metric"><strong>{item_total}</strong>Recursos y actividades</div><div class="card metric"><strong>{xr_total}</strong>Experiencias RA/VR/360</div></div>
<section class="card"><h3>Capacidades integradas</h3><p>Asistente de IA con alternativa local, herramientas gratuitas, RA, VR, 360, control de calidad, accesibilidad, publicación, duplicación, exportación y analítica.</p></section>
<h2>Cursos</h2><div class="grid">{cards}</div>
"""
        return page("Innovación y calidad", body, user)

    @app.get(f"{HUB_PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def course_innovation(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            item_types: Counter[str] = Counter()
            total_points = 0.0
            for module in modules:
                items = rows(execute(conn, "SELECT item_type,points,status FROM nexus_content_items WHERE module_id=?", (module["id"],)))
                module["items"] = len(items)
                module["points"] = sum(float(item.get("points") or 0) for item in items)
                total_points += module["points"]
                item_types.update(str(item.get("item_type") or "unknown") for item in items)
        module_cards = "".join(
            f'<section class="card"><h3>Módulo {module["position"]}: {html.escape(str(module["title"]))}</h3>'
            f'<p>{module["items"]} recursos o actividades · {module["points"]:g} puntos</p>'
            f'<a class="button" href="{HUB_PREFIX}/modules/{module["id"]}">IA, RA/VR y calidad</a> '
            f'<a class="button" href="{PREFIX}/modules/{module["id"]}">Abrir Studio</a></section>'
            for module in modules
        ) or '<p class="notice">El curso todavía no tiene módulos.</p>'
        distribution = "".join(f"<li>{html.escape(kind)}: {count}</li>" for kind, count in item_types.most_common()) or "<li>Sin actividades todavía.</li>"
        body = f"""
<p><a href="{HUB_PREFIX}">&larr; Centro de innovación</a></p>
<h2>{html.escape(str(course['course_code']))}: {html.escape(str(course['title']))}</h2>
<div class="grid"><div class="card metric"><strong>{len(modules)}</strong>Módulos</div><div class="card metric"><strong>{total_points:g}</strong>Puntos configurados</div><section class="card"><h3>Distribución</h3><ul>{distribution}</ul></section></div>
<div class="grid">
<section class="card"><h3>Publicación institucional</h3><form method="post" action="{HUB_PREFIX}/courses/{course_id}/publish"><select name="state"><option value="published">Publicar curso y contenido</option><option value="draft">Volver a borrador</option></select><button>Aplicar estado</button></form></section>
<section class="card"><h3>Administración</h3><form method="post" action="{HUB_PREFIX}/courses/{course_id}/duplicate"><button>Duplicar curso completo</button></form><p><a class="button" href="{HUB_PREFIX}/courses/{course_id}/export">Exportar respaldo JSON</a></p></section>
</div>
<h2>Módulos</h2><div class="grid">{module_cards}</div>
"""
        return page("Innovación del curso", body, user)

    @app.get(f"{HUB_PREFIX}/modules/{{module_id}}", response_class=HTMLResponse, response_model=None)
    async def module_innovation(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course, module, draft, items = _module_bundle(conn, module_id)
        report = _quality_report(module, draft, items)
        quality_rows = "".join(
            f"<tr><td>{html.escape(name)}</td><td class='status'>{'Correcto' if ok else 'Atención'}</td><td>{html.escape(detail)}</td></tr>"
            for name, ok, detail in report["checks"]
        )
        tool_options = "".join(f'<option value="{key}">{html.escape(label)}</option>' for key, (label, _) in TOOL_PRESETS.items() if key != "native")
        body = f"""
<p><a href="{HUB_PREFIX}/courses/{course['id']}">&larr; Innovación del curso</a> · <a href="{PREFIX}/modules/{module_id}">Abrir Studio del módulo</a></p>
<h2>{html.escape(str(module['title']))}</h2>
<div class="grid"><div class="card metric"><strong>{report['score']}%</strong>Calidad y accesibilidad</div><div class="card metric"><strong>{report['activity_count']}</strong>Actividades</div><div class="card metric"><strong>{report['total_points']:g}</strong>Puntos</div><div class="card metric"><strong>{report['word_count']}</strong>Palabras</div></div>
<div class="grid">
<section class="card"><h3>Asistente de IA</h3><p>Utiliza un proveedor configurado; si no existe, genera una propuesta local gratuita.</p><form method="post" action="{HUB_PREFIX}/modules/{module_id}/ai"><label>Objetivo o competencia<textarea name="objective">{html.escape(str(module.get('learning_outcomes') or ''))}</textarea></label><label>Audiencia<input name="audience" value="estudiantes universitarios"></label><label>Tipo<select name="mode"><option value="content">Contenido instruccional</option><option value="assessment">Actividad auténtica</option><option value="immersive">Experiencia inmersiva</option></select></label><label>Acción<select name="action"><option value="replace">Reemplazar borrador</option><option value="append">Añadir al borrador</option><option value="activity">Crear como actividad</option></select></label><button>Generar con IA</button></form></section>
<section class="card"><h3>Crear RA, VR o 360</h3><form method="post" action="{HUB_PREFIX}/modules/{module_id}/xr"><label>Experiencia<select name="experience_type"><option value="ar">Realidad aumentada</option><option value="vr">Realidad virtual/WebXR</option><option value="360">Video o recorrido 360</option></select></label><label>Título<input name="title" required></label><label>URL del modelo o experiencia<input type="url" name="source_url" required></label><label>Instrucciones<textarea name="instructions"></textarea></label><label>Puntos<input type="number" name="points" min="0" step="0.01"></label><button>Crear experiencia</button></form></section>
<section class="card"><h3>Herramientas emergentes</h3><form method="post" action="{HUB_PREFIX}/modules/{module_id}/tool"><label>Herramienta<select name="tool_name">{tool_options}</select></label><label>Título<input name="title" required></label><label>URL específica<input type="url" name="resource_url"></label><label>Uso<select name="graded"><option value="false">Recurso de aprendizaje</option><option value="true">Actividad evaluada</option></select></label><label>Puntos<input type="number" name="points" min="0" step="0.01"></label><button>Vincular herramienta</button></form></section>
</div>
<section class="card"><h3>Auditoría pedagógica y de accesibilidad</h3><table><thead><tr><th>Criterio</th><th>Estado</th><th>Recomendación</th></tr></thead><tbody>{quality_rows}</tbody></table></section>
"""
        return page("Innovación del módulo", body, user)

    @app.post(f"{HUB_PREFIX}/modules/{{module_id}}/ai", response_model=None)
    async def module_ai(module_id: int, request: Request, objective: str = Form(""), audience: str = Form(""), mode: str = Form("content"), action: str = Form("append")):
        user = require_admin(request, {"course_admin"})
        if mode not in {"content", "assessment", "immersive"} or action not in {"replace", "append", "activity"}:
            raise HTTPException(400, "Configuración de IA inválida.")
        with db() as conn:
            course, module, draft, _items = _module_bundle(conn, module_id)
        generated = await _external_ai_html(course, module, objective, audience, mode)
        if not generated:
            generated = _local_ai_html(course, module, objective, audience, mode)
        from app.admin_authoring_v6 import sanitize_html
        clean = sanitize_html(generated)
        with db() as conn:
            if action == "activity":
                item_type = "assignment" if mode != "immersive" else "vr"
                _insert_item(conn, module_id, item_type, f"Propuesta IA: {module['title']}", body_html=clean, metadata={"generated_by": "ai", "mode": mode})
            else:
                current = str(draft.get("body_html") or "")
                body_html = clean if action == "replace" else current + clean
                found = rows(execute(conn, "SELECT id FROM nexus_module_drafts WHERE module_id=?", (module_id,)))
                if found:
                    execute(conn, "UPDATE nexus_module_drafts SET body_html=?,updated_by=?,updated_at=? WHERE module_id=?", (body_html, user["email"], utcnow(), module_id))
                else:
                    execute(conn, "INSERT INTO nexus_module_drafts (module_id,title,body_html,updated_by,updated_at) VALUES (?,?,?,?,?)", (module_id, f"Contenido de {module['title']}", body_html, user["email"], utcnow()))
            audit(conn, user["email"], "innovation_ai_generated", "module", str(module_id), f"{mode}:{action}", request.client.host if request.client else "")
        return RedirectResponse(f"{HUB_PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{HUB_PREFIX}/modules/{{module_id}}/xr", response_model=None)
    async def create_xr(module_id: int, request: Request, experience_type: str = Form(...), title: str = Form(...), source_url: str = Form(...), instructions: str = Form(""), points: str = Form("")):
        user = require_admin(request, {"course_admin"})
        if experience_type not in XR_TYPES:
            raise HTTPException(400, "Tipo de experiencia inválido.")
        point_value = float(points.replace(",", ".")) if points.strip() else None
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, experience_type, title, body_html=f"<h2>Instrucciones</h2><p>{html.escape(instructions.strip())}</p>", embed_url=source_url, metadata={"technology": experience_type, "accessible_alternative_required": True}, points=point_value)
            audit(conn, user["email"], "xr_experience_created", "module", str(module_id), experience_type, request.client.host if request.client else "")
        return RedirectResponse(f"{HUB_PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{HUB_PREFIX}/modules/{{module_id}}/tool", response_model=None)
    async def create_tool(module_id: int, request: Request, tool_name: str = Form(...), title: str = Form(...), resource_url: str = Form(""), graded: str = Form("false"), points: str = Form("")):
        user = require_admin(request, {"course_admin"})
        if tool_name not in TOOL_PRESETS or tool_name == "native":
            raise HTTPException(400, "Herramienta no disponible.")
        label, default_url = TOOL_PRESETS[tool_name]
        url = resource_url.strip() or default_url
        point_value = float(points.replace(",", ".")) if points.strip() else None
        is_graded = graded.lower() == "true"
        item_type = _tool_item_type(tool_name, is_graded)
        with db() as conn:
            _module(conn, module_id)
            _insert_item(conn, module_id, item_type, title, external_url=url, embed_url=resource_url if resource_url else "", metadata={"tool": tool_name, "label": label, "graded": is_graded}, points=point_value)
            audit(conn, user["email"], "emerging_tool_linked", "module", str(module_id), tool_name, request.client.host if request.client else "")
        return RedirectResponse(f"{HUB_PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{HUB_PREFIX}/courses/{{course_id}}/publish", response_model=None)
    async def publish_course(course_id: int, request: Request, state: str = Form("published")):
        user = require_admin(request, {"course_admin"})
        if state not in PUBLISH_STATES:
            raise HTTPException(400, "Estado inválido.")
        course_state = "active" if state == "published" else "draft"
        with db() as conn:
            _course(conn, course_id)
            execute(conn, "UPDATE nexus_admin_courses SET status=?,updated_at=? WHERE id=?", (course_state, utcnow(), course_id))
            execute(conn, "UPDATE nexus_modules SET status=?,updated_at=? WHERE course_id=?", (state, utcnow(), course_id))
            module_rows = rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))
            for row in module_rows:
                execute(conn, "UPDATE nexus_content_items SET status=?,updated_at=? WHERE module_id=?", (state, utcnow(), row["id"]))
            audit(conn, user["email"], "course_publication_changed", "course", str(course_id), state, request.client.host if request.client else "")
        return RedirectResponse(f"{HUB_PREFIX}/courses/{course_id}", status_code=303)

    @app.post(f"{HUB_PREFIX}/courses/{{course_id}}/duplicate", response_model=None)
    async def duplicate_course(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            suffix = utcnow().replace(":", "").replace("-", "").replace("T", "")[-8:]
            new_code = f"{str(course['course_code'])[:25]}-C{suffix}"
            new_id = _insert_returning_id(
                conn,
                """INSERT INTO nexus_admin_courses (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (new_code, f"Copia de {course['title']}", course.get("description") or "", course.get("term") or "", "draft", course.get("instructor_email") or "", user["email"], utcnow(), utcnow()),
            )
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                new_module_id = _insert_returning_id(
                    conn,
                    """INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (new_id, module["title"], module.get("description") or "", module.get("learning_outcomes") or "", module.get("estimated_minutes") or 60, module.get("position") or 1, "draft", utcnow(), utcnow()),
                )
                drafts = rows(execute(conn, "SELECT * FROM nexus_module_drafts WHERE module_id=?", (module["id"],)))
                if drafts:
                    execute(conn, "INSERT INTO nexus_module_drafts (module_id,title,body_html,updated_by,updated_at) VALUES (?,?,?,?,?)", (new_module_id, drafts[0]["title"], drafts[0].get("body_html") or "", user["email"], utcnow()))
                items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module["id"],)))
                for item in items:
                    execute(conn, """INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (new_module_id, item["item_type"], item["title"], item.get("body_html") or "", item.get("external_url"), item.get("embed_url"), item.get("metadata_json") or "{}", item.get("points"), item.get("due_at"), item.get("position") or 1, "draft", utcnow(), utcnow()))
            audit(conn, user["email"], "course_duplicated", "course", str(course_id), str(new_id), request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{new_id}", status_code=303)

    @app.get(f"{HUB_PREFIX}/courses/{{course_id}}/export", response_class=JSONResponse, response_model=None)
    async def export_course(course_id: int, request: Request):
        require_admin(request, {"course_admin", "auditor"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                drafts = rows(execute(conn, "SELECT * FROM nexus_module_drafts WHERE module_id=?", (module["id"],)))
                module["draft"] = drafts[0] if drafts else None
                module["items"] = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module["id"],)))
        payload = {"format": "NEXUS-COURSE-1.0", "exported_at": utcnow(), "course": course, "modules": modules}
        filename = re.sub(r"[^A-Za-z0-9_-]+", "-", str(course.get("course_code") or "course")) + ".json"
        return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
