from __future__ import annotations

import html
import json
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.admin_console as admin_console
from app.admin_authoring_v6 import GOOGLE_KINDS, _create_google_resource, safe_url, sanitize_html
from app.admin_console import audit, db, execute, require_admin, rows, utcnow
from app.unified_authoring import (
    ACTIVITY_TYPES,
    CONTENT_TYPES,
    PREFIX,
    TOOL_PRESETS,
    _course,
    _insert_item,
    _item,
    _module,
)

COURSE_STATES = {"draft", "active", "archived"}
MODULE_STATES = {"draft", "published", "hidden"}
ITEM_STATES = {"draft", "published", "scheduled", "hidden"}
EMERGING_TYPES = {
    "interactive": "Experiencia interactiva",
    "h5p": "H5P / Lumi",
    "simulation": "Simulación",
    "ar": "Realidad aumentada",
    "vr": "Realidad virtual / WebXR",
    "360": "Video o recorrido 360°",
}
ALL_ITEM_TYPES = {**CONTENT_TYPES, **ACTIVITY_TYPES}


def _escape(value: Any, *, quote: bool = False) -> str:
    return html.escape(str(value or ""), quote=quote)


def _selected(current: Any, candidate: str) -> str:
    return " selected" if str(current or "") == candidate else ""


def _remove_get_route(app: FastAPI, path: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and "GET" in set(getattr(route, "methods", set()) or set())
        )
    ]


def _page(title: str, body: str, user: dict[str, Any]) -> HTMLResponse:
    return admin_console.page(title, body, user)


def _counts(conn: Any, course_id: int) -> tuple[int, int]:
    modules = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE course_id=?", (course_id,)))
    items = rows(
        execute(
            conn,
            """SELECT COUNT(*) AS total
               FROM nexus_content_items i
               JOIN nexus_modules m ON m.id=i.module_id
               WHERE m.course_id=?""",
            (course_id,),
        )
    )
    return (
        int(modules[0].get("total") or 0) if modules else 0,
        int(items[0].get("total") or 0) if items else 0,
    )


def _metadata(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _course_cards(courses: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for course in courses:
        course_id = int(course["id"])
        cards.append(
            f"""
            <section class="card">
              <p><span class="badge">{_escape(course.get('status') or 'draft')}</span></p>
              <h3>{_escape(course['course_code'])}: {_escape(course['title'])}</h3>
              <p>{_escape(course.get('description') or 'Sin descripción.')}</p>
              <p><strong>{int(course.get('module_total') or 0)}</strong> módulos ·
                 <strong>{int(course.get('item_total') or 0)}</strong> contenidos y actividades</p>
              <a class="button" href="{PREFIX}/courses/{course_id}">Administrar y editar</a>
              <a class="button secondary" href="{PREFIX}/courses/{course_id}/google-hub">Google Hub</a>
              <a class="button secondary" href="{PREFIX}/courses/{course_id}/emerging">Tecnologías emergentes</a>
            </section>
            """
        )
    return "".join(cards) or '<p class="notice">Todavía no hay cursos. Cree el primero.</p>'


def _item_type_options(current: str) -> str:
    return "".join(
        f'<option value="{key}"{_selected(current, key)}>{_escape(label)}</option>'
        for key, label in ALL_ITEM_TYPES.items()
    )


def register_course_workspace(app: FastAPI) -> None:
    """Add complete editing, Google Hub and emerging-technology workflows."""

    _remove_get_route(app, PREFIX)
    _remove_get_route(app, f"{PREFIX}/courses/{{course_id}}")

    @app.get(PREFIX, response_class=HTMLResponse, response_model=None)
    async def course_workspace(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(
                execute(
                    conn,
                    """SELECT c.*,
                       (SELECT COUNT(*) FROM nexus_modules m WHERE m.course_id=c.id) AS module_total,
                       (SELECT COUNT(*) FROM nexus_content_items i
                          JOIN nexus_modules m2 ON m2.id=i.module_id
                         WHERE m2.course_id=c.id) AS item_total
                       FROM nexus_admin_courses c
                       ORDER BY c.updated_at DESC,c.id DESC"""
                )
            )
        body = f"""
        <h2>NUVEDRA Course Workspace</h2>
        <p>Cree cursos, edite los existentes y organice contenido, Google Workspace y tecnologías emergentes desde un solo lugar.</p>
        <div class="grid">
          <section class="card">
            <h3>Crear curso</h3>
            <form method="post" action="{PREFIX}/courses">
              <label>Código<input name="course_code" maxlength="40" required></label>
              <label>Título<input name="title" maxlength="180" required></label>
              <label>Descripción<textarea name="description"></textarea></label>
              <label>Periodo<input name="term" placeholder="Agosto-Diciembre 2026"></label>
              <label>Profesor<input type="email" name="instructor_email"></label>
              <label>Plantilla
                <select name="template">
                  <option value="blank">Curso en blanco</option>
                  <option value="5e">Modelo 5E</option>
                  <option value="backward">Diseño inverso</option>
                  <option value="project">Aprendizaje por proyectos</option>
                  <option value="immersive">Aprendizaje inmersivo AR/VR</option>
                </select>
              </label>
              <button>Crear y comenzar a editar</button>
            </form>
          </section>
          <section class="card">
            <h3>Flujo integrado</h3>
            <ol>
              <li>Configure la información general del curso.</li>
              <li>Cree o edite módulos y resultados de aprendizaje.</li>
              <li>Incorpore Docs, Slides, Sheets, Forms, Quiz, Meet y archivos de Drive.</li>
              <li>Añada H5P, simulaciones, RA, RV, WebXR y recorridos 360°.</li>
              <li>Revise la calidad y publique desde Innovación IA/XR.</li>
            </ol>
          </section>
        </div>
        <h2>Cursos existentes</h2>
        <div class="grid">{_course_cards(courses)}</div>
        """
        return _page("Diseño y edición de cursos", body, user)

    @app.get(f"{PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def edit_course_page(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(
                execute(
                    conn,
                    """SELECT m.*,
                       (SELECT COUNT(*) FROM nexus_content_items i WHERE i.module_id=m.id) AS item_total
                       FROM nexus_modules m
                       WHERE m.course_id=?
                       ORDER BY m.position,m.id""",
                    (course_id,),
                )
            )
            module_total, item_total = _counts(conn, course_id)

        module_rows = "".join(
            f"""
            <tr>
              <td><strong>{int(module.get('position') or 1)}. {_escape(module['title'])}</strong><br>
                  <small>{_escape(module.get('description') or '')}</small></td>
              <td>{_escape(module.get('status') or 'draft')}</td>
              <td>{int(module.get('item_total') or 0)}</td>
              <td>
                <a href="{PREFIX}/modules/{module['id']}">Studio</a> ·
                <a href="{PREFIX}/modules/{module['id']}/edit">Editar</a> ·
                <a href="{PREFIX}/courses/{course_id}/google-hub#module-{module['id']}">Google</a> ·
                <a href="{PREFIX}/courses/{course_id}/emerging#module-{module['id']}">Emergente</a>
              </td>
            </tr>
            """
            for module in modules
        ) or '<tr><td colspan="4">No hay módulos creados.</td></tr>'

        body = f"""
        <p><a href="{PREFIX}">&larr; Todos los cursos</a></p>
        <h2>{_escape(course['course_code'])}: {_escape(course['title'])}</h2>
        <div class="grid">
          <div class="card metric"><strong>{module_total}</strong>Módulos</div>
          <div class="card metric"><strong>{item_total}</strong>Contenidos y actividades</div>
          <div class="card"><h3>Integraciones</h3>
            <a class="button" href="{PREFIX}/courses/{course_id}/google-hub">Google Hub</a>
            <a class="button secondary" href="{PREFIX}/courses/{course_id}/emerging">Tecnologías emergentes</a>
            <a class="button secondary" href="{PREFIX}/innovation/courses/{course_id}">Innovación y calidad</a>
          </div>
        </div>
        <div class="grid">
          <section class="card">
            <h3>Editar información del curso</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/update">
              <label>Código<input name="course_code" maxlength="40" required value="{_escape(course['course_code'], quote=True)}"></label>
              <label>Título<input name="title" maxlength="180" required value="{_escape(course['title'], quote=True)}"></label>
              <label>Descripción<textarea name="description">{_escape(course.get('description') or '')}</textarea></label>
              <label>Periodo<input name="term" value="{_escape(course.get('term') or '', quote=True)}"></label>
              <label>Profesor<input type="email" name="instructor_email" value="{_escape(course.get('instructor_email') or '', quote=True)}"></label>
              <div class="grid">
                <label>Inicio<input type="date" name="start_date" value="{_escape(course.get('start_date') or '', quote=True)}"></label>
                <label>Fin<input type="date" name="end_date" value="{_escape(course.get('end_date') or '', quote=True)}"></label>
              </div>
              <label>Estado
                <select name="status">
                  <option value="draft"{_selected(course.get('status'), 'draft')}>Borrador</option>
                  <option value="active"{_selected(course.get('status'), 'active')}>Activo</option>
                  <option value="archived"{_selected(course.get('status'), 'archived')}>Archivado</option>
                </select>
              </label>
              <button>Guardar cambios del curso</button>
            </form>
          </section>
          <section class="card">
            <h3>Crear módulo</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/modules">
              <label>Título<input name="title" required></label>
              <label>Descripción<textarea name="description"></textarea></label>
              <label>Resultados de aprendizaje<textarea name="learning_outcomes"></textarea></label>
              <div class="grid">
                <label>Duración estimada<input type="number" name="estimated_minutes" min="1" value="60"></label>
                <label>Posición<input type="number" name="position" min="1" value="{len(modules) + 1}"></label>
              </div>
              <button>Crear módulo</button>
            </form>
            <hr>
            <h3>Generar estructura con IA</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/ai-plan">
              <label>Objetivos o competencias<textarea name="objectives"></textarea></label>
              <label>Modelo
                <select name="template">
                  <option value="5e">5E</option>
                  <option value="backward">Diseño inverso</option>
                  <option value="project">Proyectos</option>
                  <option value="immersive">AR/VR</option>
                </select>
              </label>
              <button>Generar módulos</button>
            </form>
          </section>
        </div>
        <h2>Módulos del curso</h2>
        <section class="card"><table>
          <thead><tr><th>Módulo</th><th>Estado</th><th>Elementos</th><th>Acciones</th></tr></thead>
          <tbody>{module_rows}</tbody>
        </table></section>
        """
        return _page("Editar curso", body, user)

    @app.post(f"{PREFIX}/courses/{{course_id}}/update", response_model=None)
    async def update_course(
        course_id: int,
        request: Request,
        course_code: str = Form(...),
        title: str = Form(...),
        description: str = Form(""),
        term: str = Form(""),
        instructor_email: str = Form(""),
        start_date: str = Form(""),
        end_date: str = Form(""),
        status: str = Form("draft"),
    ):
        user = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        clean_title = title.strip()
        if not code or not clean_title:
            raise HTTPException(400, "Código y título son obligatorios.")
        if status not in COURSE_STATES:
            raise HTTPException(400, "Estado del curso inválido.")
        if start_date and end_date and start_date > end_date:
            raise HTTPException(400, "La fecha final no puede ser anterior a la fecha inicial.")
        with db() as conn:
            _course(conn, course_id)
            duplicate = rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE course_code=? AND id<>?", (code, course_id)))
            if duplicate:
                raise HTTPException(409, "Ya existe otro curso con ese código.")
            execute(
                conn,
                """UPDATE nexus_admin_courses
                   SET course_code=?,title=?,description=?,term=?,status=?,
                       instructor_email=?,start_date=?,end_date=?,updated_at=?
                   WHERE id=?""",
                (code, clean_title, description.strip(), term.strip(), status,
                 instructor_email.strip().lower() or None, start_date.strip() or None,
                 end_date.strip() or None, utcnow(), course_id),
            )
            audit(conn, user["email"], "course_updated", "course", str(course_id), f"{code}:{status}", request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{PREFIX}/modules/{{module_id}}/edit", response_class=HTMLResponse, response_model=None)
    async def edit_module_page(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            module = _module(conn, module_id)
            course = _course(conn, int(module["course_id"]))
            items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
        item_rows = "".join(
            f"""
            <tr>
              <td>{int(item.get('position') or 1)}</td>
              <td><strong>{_escape(item['title'])}</strong><br><small>{_escape(item.get('item_type'))}</small></td>
              <td>{_escape(item.get('status') or 'draft')}</td>
              <td><a href="{PREFIX}/items/{item['id']}/edit">Editar</a> ·
                  <a href="{PREFIX}/items/{item['id']}/preview" target="_blank">Vista previa</a></td>
            </tr>
            """
            for item in items
        ) or '<tr><td colspan="4">No hay contenidos ni actividades.</td></tr>'
        body = f"""
        <p><a href="{PREFIX}/courses/{course['id']}">&larr; Volver al curso</a></p>
        <h2>Editar módulo: {_escape(module['title'])}</h2>
        <div class="grid">
          <section class="card">
            <form method="post" action="{PREFIX}/modules/{module_id}/edit">
              <label>Título<input name="title" required value="{_escape(module['title'], quote=True)}"></label>
              <label>Descripción<textarea name="description">{_escape(module.get('description') or '')}</textarea></label>
              <label>Resultados de aprendizaje<textarea name="learning_outcomes">{_escape(module.get('learning_outcomes') or '')}</textarea></label>
              <div class="grid">
                <label>Duración<input type="number" min="1" name="estimated_minutes" value="{int(module.get('estimated_minutes') or 60)}"></label>
                <label>Posición<input type="number" min="1" name="position" value="{int(module.get('position') or 1)}"></label>
              </div>
              <label>Estado<select name="status">
                <option value="draft"{_selected(module.get('status'), 'draft')}>Borrador</option>
                <option value="published"{_selected(module.get('status'), 'published')}>Publicado</option>
                <option value="hidden"{_selected(module.get('status'), 'hidden')}>Oculto</option>
              </select></label>
              <button>Guardar módulo</button>
            </form>
          </section>
          <section class="card">
            <h3>Herramientas del módulo</h3>
            <a class="button" href="{PREFIX}/modules/{module_id}">Abrir Studio de contenido</a>
            <a class="button secondary" href="{PREFIX}/courses/{course['id']}/google-hub#module-{module_id}">Google Hub</a>
            <a class="button secondary" href="{PREFIX}/courses/{course['id']}/emerging#module-{module_id}">Tecnologías emergentes</a>
          </section>
        </div>
        <h2>Contenido y actividades</h2>
        <section class="card"><table>
          <thead><tr><th>Orden</th><th>Elemento</th><th>Estado</th><th>Acciones</th></tr></thead>
          <tbody>{item_rows}</tbody>
        </table></section>
        """
        return _page("Editar módulo", body, user)

    @app.post(f"{PREFIX}/modules/{{module_id}}/edit", response_model=None)
    async def update_module(
        module_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
        position: int = Form(1),
        status: str = Form("draft"),
    ):
        user = require_admin(request, {"course_admin"})
        if status not in MODULE_STATES:
            raise HTTPException(400, "Estado del módulo inválido.")
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "El título del módulo es obligatorio.")
        with db() as conn:
            module = _module(conn, module_id)
            execute(
                conn,
                """UPDATE nexus_modules
                   SET title=?,description=?,learning_outcomes=?,estimated_minutes=?,position=?,status=?,updated_at=?
                   WHERE id=?""",
                (clean_title, description.strip(), learning_outcomes.strip(), max(1, estimated_minutes),
                 max(1, position), status, utcnow(), module_id),
            )
            audit(conn, user["email"], "module_updated", "module", str(module_id), status, request.client.host if request.client else "")
            course_id = int(module["course_id"])
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{PREFIX}/items/{{item_id}}/edit", response_class=HTMLResponse, response_model=None)
    async def edit_item_page(item_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            item = _item(conn, item_id)
            module = _module(conn, int(item["module_id"]))
            course = _course(conn, int(module["course_id"]))
        metadata_text = json.dumps(_metadata(item.get("metadata_json")), ensure_ascii=False, indent=2)
        body = f"""
        <p><a href="{PREFIX}/modules/{module['id']}/edit">&larr; Volver al módulo</a></p>
        <h2>Editar contenido o actividad</h2>
        <section class="card">
          <form method="post" action="{PREFIX}/items/{item_id}/edit">
            <label>Tipo<select name="item_type">{_item_type_options(str(item.get('item_type') or 'page'))}</select></label>
            <label>Título<input name="title" required value="{_escape(item['title'], quote=True)}"></label>
            <label>Contenido HTML<textarea name="body_html" style="min-height:260px">{_escape(item.get('body_html') or '')}</textarea></label>
            <label>Enlace externo<input type="url" name="external_url" value="{_escape(item.get('external_url') or '', quote=True)}"></label>
            <label>URL incrustada / iframe<input type="url" name="embed_url" value="{_escape(item.get('embed_url') or '', quote=True)}"></label>
            <label>Configuración JSON<textarea name="metadata_json" style="min-height:180px">{_escape(metadata_text)}</textarea></label>
            <div class="grid">
              <label>Puntos<input type="number" min="0" step="0.01" name="points" value="{_escape(item.get('points') if item.get('points') is not None else '', quote=True)}"></label>
              <label>Fecha límite<input type="datetime-local" name="due_at" value="{_escape(item.get('due_at') or '', quote=True)}"></label>
              <label>Posición<input type="number" min="1" name="position" value="{int(item.get('position') or 1)}"></label>
            </div>
            <label>Estado<select name="status">
              <option value="draft"{_selected(item.get('status'), 'draft')}>Borrador</option>
              <option value="published"{_selected(item.get('status'), 'published')}>Publicado</option>
              <option value="scheduled"{_selected(item.get('status'), 'scheduled')}>Programado</option>
              <option value="hidden"{_selected(item.get('status'), 'hidden')}>Oculto</option>
            </select></label>
            <button>Guardar elemento</button>
            <a class="button secondary" href="{PREFIX}/items/{item_id}/preview" target="_blank">Vista previa</a>
          </form>
        </section>
        <p><small>Curso: {_escape(course['course_code'])} · Módulo: {_escape(module['title'])}</small></p>
        """
        return _page("Editar contenido", body, user)

    @app.post(f"{PREFIX}/items/{{item_id}}/edit", response_model=None)
    async def update_item(
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
        user = require_admin(request, {"course_admin"})
        if item_type not in ALL_ITEM_TYPES:
            raise HTTPException(400, "Tipo de contenido o actividad inválido.")
        if status not in ITEM_STATES:
            raise HTTPException(400, "Estado del elemento inválido.")
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "El título es obligatorio.")
        try:
            metadata = json.loads(metadata_json or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "La configuración JSON no es válida.") from exc
        if not isinstance(metadata, dict):
            raise HTTPException(400, "La configuración JSON debe ser un objeto.")
        points_value: float | None = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "La puntuación no es válida.") from exc
        external = safe_url(external_url) or None
        embed = safe_url(embed_url) or None
        with db() as conn:
            item = _item(conn, item_id)
            execute(
                conn,
                """UPDATE nexus_content_items
                   SET item_type=?,title=?,body_html=?,external_url=?,embed_url=?,metadata_json=?,
                       points=?,due_at=?,position=?,status=?,updated_at=? WHERE id=?""",
                (item_type, clean_title, sanitize_html(body_html), external, embed,
                 json.dumps(metadata, ensure_ascii=False), points_value, due_at.strip() or None,
                 max(1, position), status, utcnow(), item_id),
            )
            audit(conn, user["email"], "content_item_updated", "item", str(item_id), f"{item_type}:{status}", request.client.host if request.client else "")
            module_id = int(item["module_id"])
        return RedirectResponse(f"{PREFIX}/modules/{module_id}/edit", status_code=303)

    @app.get(f"{PREFIX}/courses/{{course_id}}/google-hub", response_class=HTMLResponse, response_model=None)
    async def google_hub(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            google_items = rows(
                execute(
                    conn,
                    """SELECT i.*,m.title AS module_title
                       FROM nexus_content_items i
                       JOIN nexus_modules m ON m.id=i.module_id
                       WHERE m.course_id=?
                         AND (i.metadata_json LIKE '%google_%' OR i.metadata_json LIKE '%google_kind%'
                              OR i.external_url LIKE '%google.com%')
                       ORDER BY m.position,i.position,i.id""",
                    (course_id,),
                )
            )
        module_options = "".join(
            f'<option value="{module["id"]}">{int(module.get("position") or 1)}. {_escape(module["title"])}</option>'
            for module in modules
        )
        resource_rows = "".join(
            f'<tr><td>{_escape(item.get("module_title"))}</td><td>{_escape(item.get("title"))}</td>'
            f'<td>{_escape(_metadata(item.get("metadata_json")).get("google_kind") or item.get("item_type"))}</td>'
            f'<td><a href="{_escape(item.get("external_url") or "#", quote=True)}" target="_blank" rel="noopener">Abrir</a> · '
            f'<a href="{PREFIX}/items/{item["id"]}/edit">Editar vínculo</a></td></tr>'
            for item in google_items
        ) or '<tr><td colspan="4">Todavía no hay recursos Google vinculados.</td></tr>'
        body = f"""
        <p><a href="{PREFIX}/courses/{course_id}">&larr; Volver al curso</a></p>
        <h2>Google Hub · {_escape(course['course_code'])}</h2>
        <p>Centralice recursos de Google Workspace dentro de los módulos del curso.</p>
        <div class="grid">
          <section class="card">
            <h3>Crear recurso Google</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/google-hub/create">
              <label>Módulo<select name="module_id" required>{module_options}</select></label>
              <label>Tipo<select name="kind">
                <option value="docs">Google Docs</option>
                <option value="slides">Google Slides</option>
                <option value="sheets">Google Sheets</option>
                <option value="forms">Google Forms</option>
                <option value="quiz">Quiz en Google Forms</option>
                <option value="meet">Google Meet y Calendar</option>
              </select></label>
              <label>Título<input name="title" required value="{_escape(course['title'], quote=True)}"></label>
              <button>Crear y vincular al módulo</button>
            </form>
          </section>
          <section class="card">
            <h3>Servicios rápidos</h3>
            <a class="button" href="https://drive.google.com" target="_blank" rel="noopener">Google Drive</a>
            <a class="button" href="https://classroom.google.com" target="_blank" rel="noopener">Google Classroom</a>
            <a class="button" href="https://calendar.google.com" target="_blank" rel="noopener">Google Calendar</a>
            <a class="button" href="https://forms.google.com" target="_blank" rel="noopener">Google Forms</a>
            <p>Para vincular un archivo existente, abra el Studio del módulo y seleccione <strong>Google Workspace → Seleccionar desde Google Drive</strong>.</p>
          </section>
        </div>
        <h2>Recursos Google del curso</h2>
        <section class="card"><table>
          <thead><tr><th>Módulo</th><th>Recurso</th><th>Tipo</th><th>Acciones</th></tr></thead>
          <tbody>{resource_rows}</tbody>
        </table></section>
        """
        return _page("Google Hub", body, user)

    @app.post(f"{PREFIX}/courses/{{course_id}}/google-hub/create", response_model=None)
    async def create_google_hub_resource(course_id: int, request: Request, module_id: int = Form(...), kind: str = Form(...), title: str = Form(...)):
        user = require_admin(request, {"course_admin"})
        if kind not in GOOGLE_KINDS:
            raise HTTPException(400, "Tipo de recurso Google inválido.")
        with db() as conn:
            _course(conn, course_id)
            module = _module(conn, module_id)
            if int(module["course_id"]) != course_id:
                raise HTTPException(400, "El módulo no pertenece a este curso.")
        url, item_type = await _create_google_resource(request, kind, title.strip())
        with db() as conn:
            _insert_item(conn, module_id, item_type, title, external_url=url, metadata={"google_kind": kind, "source": "google_hub"})
            audit(conn, user["email"], "google_hub_resource_created", "course", str(course_id), f"{module_id}:{kind}", request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}/google-hub", status_code=303)

    @app.get(f"{PREFIX}/courses/{{course_id}}/emerging", response_class=HTMLResponse, response_model=None)
    async def emerging_hub(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            items = rows(
                execute(
                    conn,
                    """SELECT i.*,m.title AS module_title
                       FROM nexus_content_items i
                       JOIN nexus_modules m ON m.id=i.module_id
                       WHERE m.course_id=? AND i.item_type IN ('interactive','h5p','simulation','ar','vr','360')
                       ORDER BY m.position,i.position,i.id""",
                    (course_id,),
                )
            )
        module_options = "".join(
            f'<option value="{module["id"]}">{int(module.get("position") or 1)}. {_escape(module["title"])}</option>'
            for module in modules
        )
        type_options = "".join(f'<option value="{key}">{_escape(label)}</option>' for key, label in EMERGING_TYPES.items())
        preset_options = "".join(
            f'<option value="{key}" data-url="{_escape(url, quote=True)}">{_escape(label)}</option>'
            for key, (label, url) in TOOL_PRESETS.items() if url
        )
        item_rows = "".join(
            f'<tr><td>{_escape(item.get("module_title"))}</td><td>{_escape(item.get("title"))}</td>'
            f'<td>{_escape(EMERGING_TYPES.get(str(item.get("item_type")), str(item.get("item_type"))))}</td>'
            f'<td><a href="{PREFIX}/items/{item["id"]}/preview" target="_blank">Abrir</a> · '
            f'<a href="{PREFIX}/items/{item["id"]}/edit">Editar</a></td></tr>'
            for item in items
        ) or '<tr><td colspan="4">Todavía no hay experiencias emergentes.</td></tr>'
        body = f"""
        <p><a href="{PREFIX}/courses/{course_id}">&larr; Volver al curso</a></p>
        <h2>Tecnologías emergentes · {_escape(course['course_code'])}</h2>
        <div class="grid">
          <section class="card">
            <h3>Añadir experiencia</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/emerging/add">
              <label>Módulo<select name="module_id" required>{module_options}</select></label>
              <label>Tipo<select name="item_type">{type_options}</select></label>
              <label>Título<input name="title" required></label>
              <label>Instrucciones pedagógicas<textarea name="instructions"></textarea></label>
              <label>Herramienta sugerida<select id="emerging-preset" name="tool_name"><option value="">Seleccionar...</option>{preset_options}</select></label>
              <label>Enlace externo<input id="emerging-external" type="url" name="external_url"></label>
              <label>URL para iframe, WebXR, modelo o video 360°<input type="url" name="embed_url"></label>
              <label>Alternativa accesible<textarea name="accessible_alternative" placeholder="Descripción textual, transcripción o actividad equivalente."></textarea></label>
              <button>Añadir al curso</button>
            </form>
          </section>
          <section class="card">
            <h3>Opciones recomendadas</h3>
            <ul>
              <li><strong>H5P/Lumi:</strong> actividades interactivas reutilizables.</li>
              <li><strong>PhET y GeoGebra:</strong> simulaciones y manipulación visual.</li>
              <li><strong>JupyterLite:</strong> laboratorios de Python en el navegador.</li>
              <li><strong>A-Frame/WebXR:</strong> escenas de realidad virtual.</li>
              <li><strong>model-viewer:</strong> modelos GLB/glTF con realidad aumentada.</li>
              <li><strong>Video 360°:</strong> recorridos inmersivos con evidencia evaluable.</li>
            </ul>
          </section>
        </div>
        <h2>Experiencias incorporadas</h2>
        <section class="card"><table><thead><tr><th>Módulo</th><th>Experiencia</th><th>Tecnología</th><th>Acciones</th></tr></thead><tbody>{item_rows}</tbody></table></section>
        <script>
        (() => {{
          const preset=document.getElementById('emerging-preset');
          const external=document.getElementById('emerging-external');
          preset?.addEventListener('change',()=>{{
            const option=preset.options[preset.selectedIndex];
            if(option?.dataset?.url && !external.value) external.value=option.dataset.url;
          }});
        }})();
        </script>
        """
        return _page("Tecnologías emergentes", body, user)

    @app.post(f"{PREFIX}/courses/{{course_id}}/emerging/add", response_model=None)
    async def add_emerging_resource(
        course_id: int,
        request: Request,
        module_id: int = Form(...),
        item_type: str = Form(...),
        title: str = Form(...),
        instructions: str = Form(""),
        tool_name: str = Form(""),
        external_url: str = Form(""),
        embed_url: str = Form(""),
        accessible_alternative: str = Form(""),
    ):
        user = require_admin(request, {"course_admin"})
        if item_type not in EMERGING_TYPES:
            raise HTTPException(400, "Tecnología emergente inválida.")
        with db() as conn:
            _course(conn, course_id)
            module = _module(conn, module_id)
            if int(module["course_id"]) != course_id:
                raise HTTPException(400, "El módulo no pertenece a este curso.")
            body_html = (
                f"<h2>Instrucciones</h2><p>{html.escape(instructions.strip())}</p>"
                f"<h3>Alternativa accesible</h3><p>{html.escape(accessible_alternative.strip())}</p>"
            )
            _insert_item(
                conn,
                module_id,
                item_type,
                title,
                body_html=body_html,
                external_url=external_url,
                embed_url=embed_url,
                metadata={"emerging_technology": item_type, "tool": tool_name, "accessible_alternative": accessible_alternative.strip()},
            )
            audit(conn, user["email"], "emerging_resource_created", "course", str(course_id), f"{module_id}:{item_type}:{tool_name}", request.client.host if request.client else "")
        return RedirectResponse(f"{PREFIX}/courses/{course_id}/emerging", status_code=303)
