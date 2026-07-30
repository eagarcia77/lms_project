from __future__ import annotations

import html
import json
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.academic_access as academic_access
import app.admin_console as admin_console
from app.admin_authoring_v6 import safe_url, sanitize_html
from app.admin_console import audit, db, execute, rows, session_user, utcnow
from app.unified_authoring import ACTIVITY_TYPES, CONTENT_TYPES, _course, _insert_item, _module

STUDIO_PREFIX = "/faculty/studio"
MODULE_STATES = {"draft", "published", "hidden"}
ITEM_STATES = {"draft", "published", "scheduled", "hidden"}

ITEM_TYPES = {
    **CONTENT_TYPES,
    **ACTIVITY_TYPES,
    "assessment": "Assessment",
    "google": "Google Workspace",
    "h5p": "H5P / Lumi",
    "simulation": "Simulation",
    "ar": "Augmented reality",
    "vr": "Virtual reality / WebXR",
    "360": "360° experience",
}

TYPE_CARDS = [
    ("page", "Page", "Página", "Create formatted instructional content."),
    ("document", "Document", "Documento", "Add a file, reading, or downloadable resource."),
    ("video", "Video", "Video", "Embed or link a video with an accessible alternative."),
    ("link", "Link", "Enlace", "Connect an external website or learning resource."),
    ("assignment", "Assignment", "Asignación", "Collect work with points and a due date."),
    ("assessment", "Assessment", "Evaluación", "Create an assessment with response settings."),
    ("discussion", "Discussion", "Discusión", "Add a prompt for academic interaction."),
    ("google", "Google", "Google", "Link Docs, Slides, Sheets, Forms, or Drive."),
    ("h5p", "H5P", "H5P", "Embed an interactive H5P or Lumi activity."),
    ("simulation", "Simulation", "Simulación", "Add PhET, GeoGebra, or another simulation."),
    ("ar", "AR", "RA", "Add an augmented-reality learning object."),
    ("vr", "VR / WebXR", "RV / WebXR", "Add an immersive virtual experience."),
    ("360", "360°", "360°", "Add a 360-degree video or virtual tour."),
]

STUDIO_ASSETS = """
<link rel="stylesheet" href="/static/course-studio.css">
<script src="/static/course-studio.js" defer></script>
"""


def _esc(value: Any, *, attr: bool = False) -> str:
    return html.escape(str(value or ""), quote=attr)


def _selected(current: Any, candidate: str) -> str:
    return " selected" if str(current or "") == candidate else ""


def _remove_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def _author(request: Request, return_to: str) -> dict[str, Any] | RedirectResponse:
    user = academic_access.google_user(request)
    if not user:
        return academic_access.login_redirect(return_to)
    return user


def _course_access(conn: Any, course_id: int, user: dict[str, Any]) -> dict[str, Any]:
    return academic_access.require_course_role(conn, course_id, user["email"], academic_access.AUTHOR_ROLES)


def _studio_page(title: str, body: str, user: dict[str, Any]) -> HTMLResponse:
    return academic_access.portal_page(title, f"{STUDIO_ASSETS}{body}", user)


def _type_options(current: str = "page") -> str:
    return "".join(
        f'<option value="{_esc(key, attr=True)}"{_selected(current, key)}>{_esc(label)}</option>'
        for key, label in ITEM_TYPES.items()
    )


def _status_options(current: str, values: tuple[tuple[str, str, str], ...]) -> str:
    return "".join(
        f'<option value="{value}"{_selected(current, value)} data-i18n-en="{_esc(en, attr=True)}" data-i18n-es="{_esc(es, attr=True)}">{_esc(en)}</option>'
        for value, en, es in values
    )


def _metadata(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_positions(conn: Any, table: str, parent_column: str, parent_id: int) -> list[dict[str, Any]]:
    if table not in {"nexus_modules", "nexus_content_items"} or parent_column not in {"course_id", "module_id"}:
        raise ValueError("Unsupported position table")
    data = rows(execute(conn, f"SELECT id,position FROM {table} WHERE {parent_column}=? ORDER BY position,id", (parent_id,)))
    for position, row in enumerate(data, 1):
        if int(row.get("position") or 0) != position:
            execute(conn, f"UPDATE {table} SET position=?,updated_at=? WHERE id=?", (position, utcnow(), int(row["id"])))
        row["position"] = position
    return data


def _move_row(conn: Any, table: str, parent_column: str, parent_id: int, row_id: int, direction: str) -> None:
    data = _normalize_positions(conn, table, parent_column, parent_id)
    index = next((idx for idx, row in enumerate(data) if int(row["id"]) == row_id), None)
    if index is None:
        raise HTTPException(404, "The requested item was not found.")
    target_index = index - 1 if direction == "up" else index + 1
    if target_index < 0 or target_index >= len(data):
        return
    current = data[index]
    target = data[target_index]
    execute(conn, f"UPDATE {table} SET position=?,updated_at=? WHERE id=?", (int(target["position"]), utcnow(), int(current["id"])))
    execute(conn, f"UPDATE {table} SET position=?,updated_at=? WHERE id=?", (int(current["position"]), utcnow(), int(target["id"])))


def _admin_link(request: Request, course_id: int) -> str:
    return (
        f'<a class="studio-button studio-button--quiet" href="/admin/authoring/courses/{course_id}" '
        'data-i18n-en="Administration" data-i18n-es="Administración">Administration</a>'
        if session_user(request)
        else ""
    )


def _module_cards(modules: list[dict[str, Any]]) -> str:
    if not modules:
        return """
        <section class="studio-empty" data-testid="empty-course">
          <h3 data-i18n-en="Start with the first module" data-i18n-es="Comience con el primer módulo">Start with the first module</h3>
          <p data-i18n-en="Use the form above to organize the course into clear learning units." data-i18n-es="Utilice el formulario superior para organizar el curso en unidades de aprendizaje claras.">Use the form above to organize the course into clear learning units.</p>
        </section>
        """
    cards: list[str] = []
    for module in modules:
        module_id = int(module["id"])
        cards.append(
            f"""
            <article class="studio-module-card" data-testid="module-card">
              <div class="studio-module-card__top">
                <span class="studio-order">{int(module.get('position') or 1)}</span>
                <span class="studio-status studio-status--{_esc(module.get('status') or 'draft', attr=True)}">{_esc(module.get('status') or 'draft')}</span>
              </div>
              <h3>{_esc(module['title'])}</h3>
              <p>{_esc(module.get('description') or 'No description yet.')}</p>
              <p class="studio-meta"><strong>{int(module.get('item_total') or 0)}</strong> <span data-i18n-en="items" data-i18n-es="elementos">items</span> · <strong>{int(module.get('published_total') or 0)}</strong> <span data-i18n-en="published" data-i18n-es="publicados">published</span></p>
              <div class="studio-actions">
                <a class="studio-button" href="{STUDIO_PREFIX}/modules/{module_id}" data-i18n-en="Open module" data-i18n-es="Abrir módulo">Open module</a>
                <form method="post" action="{STUDIO_PREFIX}/modules/{module_id}/move"><input type="hidden" name="direction" value="up"><button class="studio-icon-button" title="Move up" data-title-en="Move up" data-title-es="Mover arriba" aria-label="Move up">↑</button></form>
                <form method="post" action="{STUDIO_PREFIX}/modules/{module_id}/move"><input type="hidden" name="direction" value="down"><button class="studio-icon-button" title="Move down" data-title-en="Move down" data-title-es="Mover abajo" aria-label="Move down">↓</button></form>
                <form method="post" action="{STUDIO_PREFIX}/modules/{module_id}/duplicate"><button class="studio-icon-button" title="Duplicate" data-title-en="Duplicate" data-title-es="Duplicar" aria-label="Duplicate">⧉</button></form>
              </div>
            </article>
            """
        )
    return "".join(cards)


def _item_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return """
        <section class="studio-empty" data-testid="empty-module">
          <h3 data-i18n-en="Add the first learning item" data-i18n-es="Añada el primer elemento de aprendizaje">Add the first learning item</h3>
          <p data-i18n-en="Choose a content type below. Everything starts as a draft." data-i18n-es="Seleccione un tipo de contenido abajo. Todo comienza como borrador.">Choose a content type below. Everything starts as a draft.</p>
        </section>
        """
    cards: list[str] = []
    for item in items:
        item_id = int(item["id"])
        state = str(item.get("status") or "draft")
        toggle_label_en = "Unpublish" if state == "published" else "Publish"
        toggle_label_es = "Retirar publicación" if state == "published" else "Publicar"
        cards.append(
            f"""
            <article class="studio-item-card" data-testid="content-item">
              <div class="studio-item-card__main">
                <span class="studio-order">{int(item.get('position') or 1)}</span>
                <div>
                  <p class="studio-kicker">{_esc(ITEM_TYPES.get(str(item.get('item_type')), str(item.get('item_type') or 'content')))}</p>
                  <h3>{_esc(item['title'])}</h3>
                  <p class="studio-meta"><span class="studio-status studio-status--{_esc(state, attr=True)}">{_esc(state)}</span>{' · ' + _esc(item.get('points')) + ' pts' if item.get('points') not in (None, '') else ''}{' · ' + _esc(item.get('due_at')) if item.get('due_at') else ''}</p>
                </div>
              </div>
              <div class="studio-actions">
                <a class="studio-button" href="{STUDIO_PREFIX}/items/{item_id}/edit" data-i18n-en="Edit" data-i18n-es="Editar">Edit</a>
                <a class="studio-button studio-button--quiet" href="/admin/authoring/items/{item_id}/preview" target="_blank" rel="noopener" data-i18n-en="Preview" data-i18n-es="Vista previa">Preview</a>
                <form method="post" action="{STUDIO_PREFIX}/items/{item_id}/toggle"><button class="studio-button studio-button--quiet" data-i18n-en="{toggle_label_en}" data-i18n-es="{toggle_label_es}">{toggle_label_en}</button></form>
                <form method="post" action="{STUDIO_PREFIX}/items/{item_id}/move"><input type="hidden" name="direction" value="up"><button class="studio-icon-button" title="Move up" data-title-en="Move up" data-title-es="Mover arriba" aria-label="Move up">↑</button></form>
                <form method="post" action="{STUDIO_PREFIX}/items/{item_id}/move"><input type="hidden" name="direction" value="down"><button class="studio-icon-button" title="Move down" data-title-en="Move down" data-title-es="Mover abajo" aria-label="Move down">↓</button></form>
                <form method="post" action="{STUDIO_PREFIX}/items/{item_id}/duplicate"><button class="studio-icon-button" title="Duplicate" data-title-en="Duplicate" data-title-es="Duplicar" aria-label="Duplicate">⧉</button></form>
              </div>
            </article>
            """
        )
    return "".join(cards)


def _quick_type_cards() -> str:
    cards: list[str] = []
    for key, en, es, description in TYPE_CARDS:
        if key not in ITEM_TYPES:
            continue
        cards.append(
            f"""
            <button type="button" class="studio-type-card" data-select-type="{_esc(key, attr=True)}">
              <strong data-i18n-en="{_esc(en, attr=True)}" data-i18n-es="{_esc(es, attr=True)}">{_esc(en)}</strong>
              <span>{_esc(description)}</span>
            </button>
            """
        )
    return "".join(cards)


def register_visual_course_studio(app: FastAPI) -> None:
    if getattr(app.state, "nuvedra_visual_course_studio", False):
        return
    app.state.nuvedra_visual_course_studio = True

    # The visual studio owns the instructor GET pages. Legacy POST routes remain
    # available for backwards compatibility and old bookmarks.
    for path in (
        "/faculty/courses/{course_id}",
        "/faculty/modules/{module_id}",
        "/faculty/items/{item_id}/edit",
    ):
        _remove_route(app, path, "GET")

    @app.get("/faculty/courses/{course_id}", include_in_schema=False, response_model=None)
    async def legacy_course_redirect(course_id: int, request: Request):
        user = _author(request, f"/faculty/courses/{course_id}")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            _course_access(conn, course_id, user)
        return RedirectResponse(f"{STUDIO_PREFIX}/courses/{course_id}", status_code=303)

    @app.get("/faculty/modules/{module_id}", include_in_schema=False, response_model=None)
    async def legacy_module_redirect(module_id: int, request: Request):
        user = _author(request, f"/faculty/modules/{module_id}")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            module = _module(conn, module_id)
            _course_access(conn, int(module["course_id"]), user)
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{module_id}", status_code=303)

    @app.get("/faculty/items/{item_id}/edit", include_in_schema=False, response_model=None)
    async def legacy_item_redirect(item_id: int, request: Request):
        user = _author(request, f"/faculty/items/{item_id}/edit")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course_id, _item, _module_data = academic_access.item_bundle(conn, item_id)
            _course_access(conn, course_id, user)
        return RedirectResponse(f"{STUDIO_PREFIX}/items/{item_id}/edit", status_code=303)

    @app.get(f"{STUDIO_PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def course_studio(course_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/courses/{course_id}")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course = _course_access(conn, course_id, user)
            modules = rows(
                execute(
                    conn,
                    """SELECT m.*,
                       (SELECT COUNT(*) FROM nexus_content_items i WHERE i.module_id=m.id) AS item_total,
                       (SELECT COUNT(*) FROM nexus_content_items i2 WHERE i2.module_id=m.id AND i2.status='published') AS published_total
                       FROM nexus_modules m WHERE m.course_id=? ORDER BY m.position,m.id""",
                    (course_id,),
                )
            )
            item_count = rows(
                execute(
                    conn,
                    """SELECT COUNT(*) AS total FROM nexus_content_items i
                       JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=?""",
                    (course_id,),
                )
            )
            published_count = rows(
                execute(
                    conn,
                    """SELECT COUNT(*) AS total FROM nexus_content_items i
                       JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=? AND i.status='published'""",
                    (course_id,),
                )
            )
        total_items = int(item_count[0].get("total") or 0) if item_count else 0
        total_published = int(published_count[0].get("total") or 0) if published_count else 0
        body = f"""
        <main class="studio-shell" data-testid="visual-course-studio" data-studio-root>
          <nav class="studio-breadcrumbs" aria-label="Breadcrumb">
            <a href="/portal" data-i18n-en="My courses" data-i18n-es="Mis cursos">My courses</a><span>/</span><strong>{_esc(course['course_code'])}</strong>
          </nav>
          <header class="studio-hero">
            <div>
              <p class="studio-eyebrow" data-i18n-en="Instructor workspace" data-i18n-es="Espacio del instructor">Instructor workspace</p>
              <h2>{_esc(course['course_code'])}: {_esc(course['title'])}</h2>
              <p>{_esc(course.get('description') or 'Build the course with modules, learning content, Google resources, emerging technologies, and assessments.')}</p>
            </div>
            <div class="studio-actions">
              <a class="studio-button studio-button--quiet" href="/learn/courses/{course_id}" target="_blank" rel="noopener" data-i18n-en="Preview as student" data-i18n-es="Vista como estudiante">Preview as student</a>
              {_admin_link(request, course_id)}
            </div>
          </header>

          <section class="studio-metrics" aria-label="Course summary">
            <div><strong>{len(modules)}</strong><span data-i18n-en="Modules" data-i18n-es="Módulos">Modules</span></div>
            <div><strong>{total_items}</strong><span data-i18n-en="Learning items" data-i18n-es="Elementos de aprendizaje">Learning items</span></div>
            <div><strong>{total_published}</strong><span data-i18n-en="Published" data-i18n-es="Publicados">Published</span></div>
            <div><strong>{_esc(course.get('status') or 'draft')}</strong><span data-i18n-en="Course status" data-i18n-es="Estado del curso">Course status</span></div>
          </section>

          <details class="studio-panel studio-panel--compact">
            <summary data-i18n-en="Add a module" data-i18n-es="Añadir un módulo">Add a module</summary>
            <form method="post" action="{STUDIO_PREFIX}/courses/{course_id}/modules" data-autosave-key="course-{course_id}-new-module">
              <div class="studio-form-grid">
                <label><span data-i18n-en="Module title" data-i18n-es="Título del módulo">Module title</span><input name="title" required maxlength="180"></label>
                <label><span data-i18n-en="Estimated minutes" data-i18n-es="Minutos estimados">Estimated minutes</span><input type="number" name="estimated_minutes" min="1" value="60"></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Description" data-i18n-es="Descripción">Description</span><textarea name="description"></textarea></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Learning outcomes" data-i18n-es="Resultados de aprendizaje">Learning outcomes</span><textarea name="learning_outcomes"></textarea></label>
              </div>
              <div class="studio-form-footer"><span class="studio-save-state" aria-live="polite"></span><button class="studio-button" data-i18n-en="Create module" data-i18n-es="Crear módulo">Create module</button></div>
            </form>
          </details>

          <section class="studio-section">
            <div class="studio-section__heading"><div><p class="studio-eyebrow" data-i18n-en="Course structure" data-i18n-es="Estructura del curso">Course structure</p><h2 data-i18n-en="Modules" data-i18n-es="Módulos">Modules</h2></div></div>
            <div class="studio-module-grid">{_module_cards(modules)}</div>
          </section>
        </main>
        """
        return _studio_page("Course Studio", body, user)

    @app.post(f"{STUDIO_PREFIX}/courses/{{course_id}}/modules", response_model=None)
    async def create_module(
        course_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
    ):
        user = _author(request, f"{STUDIO_PREFIX}/courses/{course_id}")
        if isinstance(user, RedirectResponse):
            return user
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "Module title is required.")
        with db() as conn:
            _course_access(conn, course_id, user)
            existing = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE course_id=?", (course_id,)))
            position = int(existing[0].get("total") or 0) + 1 if existing else 1
            now = utcnow()
            execute(
                conn,
                """INSERT INTO nexus_modules
                   (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (course_id, clean_title, description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), position, "draft", now, now),
            )
            audit(conn, user["email"], "visual_studio_module_created", "course", str(course_id), clean_title, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/courses/{course_id}", status_code=303)

    @app.get(f"{STUDIO_PREFIX}/modules/{{module_id}}", response_class=HTMLResponse, response_model=None)
    async def module_studio(module_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/modules/{module_id}")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            module = _module(conn, module_id)
            course_id = int(module["course_id"])
            course = _course_access(conn, course_id, user)
            items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
        body = f"""
        <main class="studio-shell" data-testid="visual-module-studio" data-studio-root>
          <nav class="studio-breadcrumbs" aria-label="Breadcrumb"><a href="{STUDIO_PREFIX}/courses/{course_id}">{_esc(course['course_code'])}</a><span>/</span><strong>{_esc(module['title'])}</strong></nav>
          <header class="studio-hero studio-hero--module">
            <div><p class="studio-eyebrow" data-i18n-en="Module editor" data-i18n-es="Editor del módulo">Module editor</p><h2>{_esc(module['title'])}</h2><p>{_esc(module.get('description') or 'Organize content and assessments in the order students will complete them.')}</p></div>
            <div class="studio-actions"><a class="studio-button studio-button--quiet" href="/learn/courses/{course_id}" target="_blank" rel="noopener" data-i18n-en="Preview course" data-i18n-es="Vista previa del curso">Preview course</a></div>
          </header>

          <details class="studio-panel studio-panel--compact">
            <summary data-i18n-en="Module settings" data-i18n-es="Configuración del módulo">Module settings</summary>
            <form method="post" action="{STUDIO_PREFIX}/modules/{module_id}/update" data-autosave-key="module-{module_id}-settings">
              <div class="studio-form-grid">
                <label><span data-i18n-en="Title" data-i18n-es="Título">Title</span><input name="title" required value="{_esc(module['title'], attr=True)}"></label>
                <label><span data-i18n-en="Status" data-i18n-es="Estado">Status</span><select name="status">{_status_options(str(module.get('status') or 'draft'), (("draft", "Draft", "Borrador"), ("published", "Published", "Publicado"), ("hidden", "Hidden", "Oculto")))}</select></label>
                <label><span data-i18n-en="Estimated minutes" data-i18n-es="Minutos estimados">Estimated minutes</span><input type="number" name="estimated_minutes" min="1" value="{int(module.get('estimated_minutes') or 60)}"></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Description" data-i18n-es="Descripción">Description</span><textarea name="description">{_esc(module.get('description'))}</textarea></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Learning outcomes" data-i18n-es="Resultados de aprendizaje">Learning outcomes</span><textarea name="learning_outcomes">{_esc(module.get('learning_outcomes'))}</textarea></label>
              </div>
              <div class="studio-form-footer"><span class="studio-save-state" aria-live="polite"></span><button class="studio-button" data-i18n-en="Save module" data-i18n-es="Guardar módulo">Save module</button></div>
            </form>
          </details>

          <section class="studio-section">
            <div class="studio-section__heading"><div><p class="studio-eyebrow" data-i18n-en="Build the learning experience" data-i18n-es="Construya la experiencia de aprendizaje">Build the learning experience</p><h2 data-i18n-en="Add content or an assessment" data-i18n-es="Añadir contenido o una evaluación">Add content or an assessment</h2></div></div>
            <div class="studio-type-grid">{_quick_type_cards()}</div>
            <form class="studio-panel" method="post" action="{STUDIO_PREFIX}/modules/{module_id}/items" data-item-form data-autosave-key="module-{module_id}-new-item">
              <div class="studio-form-grid">
                <label><span data-i18n-en="Type" data-i18n-es="Tipo">Type</span><select name="item_type" data-item-type>{_type_options()}</select></label>
                <label><span data-i18n-en="Title" data-i18n-es="Título">Title</span><input name="title" required maxlength="220"></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Content, instructions, or question" data-i18n-es="Contenido, instrucciones o pregunta">Content, instructions, or question</span><textarea name="body_html" rows="8"></textarea></label>
                <label><span data-i18n-en="External or Google link" data-i18n-es="Enlace externo o de Google">External or Google link</span><input type="url" name="external_url" placeholder="https://"></label>
                <label><span data-i18n-en="Embed, media, or WebXR URL" data-i18n-es="URL incrustada, multimedia o WebXR">Embed, media, or WebXR URL</span><input type="url" name="embed_url" placeholder="https://"></label>
                <label><span data-i18n-en="Points" data-i18n-es="Puntos">Points</span><input type="number" name="points" min="0" step="0.01"></label>
                <label><span data-i18n-en="Due date" data-i18n-es="Fecha límite">Due date</span><input type="datetime-local" name="due_at"></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Accessible alternative" data-i18n-es="Alternativa accesible">Accessible alternative</span><textarea name="accessible_alternative" data-placeholder-en="Description, transcript, or equivalent activity." data-placeholder-es="Descripción, transcripción o actividad equivalente." placeholder="Description, transcript, or equivalent activity."></textarea></label>
              </div>
              <fieldset class="studio-assessment-settings" data-assessment-settings hidden>
                <legend data-i18n-en="Assessment settings" data-i18n-es="Configuración de la evaluación">Assessment settings</legend>
                <div class="studio-form-grid">
                  <label><span data-i18n-en="Response type" data-i18n-es="Tipo de respuesta">Response type</span><select name="assessment_response_type"><option value="text" data-i18n-en="Written response" data-i18n-es="Respuesta escrita">Written response</option><option value="file" data-i18n-en="File or link" data-i18n-es="Archivo o enlace">File or link</option><option value="multiple_choice" data-i18n-en="Multiple choice" data-i18n-es="Selección múltiple">Multiple choice</option><option value="true_false" data-i18n-en="True or false" data-i18n-es="Cierto o falso">True or false</option></select></label>
                  <label><span data-i18n-en="Attempts" data-i18n-es="Intentos">Attempts</span><input type="number" name="attempts" min="1" value="1"></label>
                  <label><span data-i18n-en="Time limit in minutes" data-i18n-es="Límite de tiempo en minutos">Time limit in minutes</span><input type="number" name="time_limit" min="0" value="0"></label>
                  <label class="studio-form-grid__wide"><span data-i18n-en="Rubric or grading criteria" data-i18n-es="Rúbrica o criterios de evaluación">Rubric or grading criteria</span><textarea name="rubric"></textarea></label>
                </div>
              </fieldset>
              <div class="studio-google-shortcuts"><strong data-i18n-en="Create with Google:" data-i18n-es="Crear con Google:">Create with Google:</strong><a href="https://docs.new" target="_blank" rel="noopener">Docs</a><a href="https://slides.new" target="_blank" rel="noopener">Slides</a><a href="https://sheets.new" target="_blank" rel="noopener">Sheets</a><a href="https://forms.new" target="_blank" rel="noopener">Forms</a></div>
              <div class="studio-form-footer"><span class="studio-save-state" aria-live="polite"></span><button class="studio-button" data-i18n-en="Add to module" data-i18n-es="Añadir al módulo">Add to module</button></div>
            </form>
          </section>

          <section class="studio-section">
            <div class="studio-section__heading"><div><p class="studio-eyebrow" data-i18n-en="Student sequence" data-i18n-es="Secuencia del estudiante">Student sequence</p><h2 data-i18n-en="Module content" data-i18n-es="Contenido del módulo">Module content</h2></div></div>
            <div class="studio-item-list">{_item_cards(items)}</div>
          </section>
        </main>
        """
        return _studio_page("Module Studio", body, user)

    @app.post(f"{STUDIO_PREFIX}/modules/{{module_id}}/update", response_model=None)
    async def update_module(
        module_id: int,
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        learning_outcomes: str = Form(""),
        estimated_minutes: int = Form(60),
        status: str = Form("draft"),
    ):
        user = _author(request, f"{STUDIO_PREFIX}/modules/{module_id}")
        if isinstance(user, RedirectResponse):
            return user
        if status not in MODULE_STATES:
            raise HTTPException(400, "Invalid module status.")
        if not title.strip():
            raise HTTPException(400, "Module title is required.")
        with db() as conn:
            module = _module(conn, module_id)
            _course_access(conn, int(module["course_id"]), user)
            execute(
                conn,
                """UPDATE nexus_modules SET title=?,description=?,learning_outcomes=?,estimated_minutes=?,status=?,updated_at=? WHERE id=?""",
                (title.strip(), description.strip(), learning_outcomes.strip(), max(1, estimated_minutes), status, utcnow(), module_id),
            )
            audit(conn, user["email"], "visual_studio_module_updated", "module", str(module_id), status, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{module_id}", status_code=303)

    @app.post(f"{STUDIO_PREFIX}/modules/{{module_id}}/items", response_model=None)
    async def create_item(
        module_id: int,
        request: Request,
        item_type: str = Form(...),
        title: str = Form(...),
        body_html: str = Form(""),
        external_url: str = Form(""),
        embed_url: str = Form(""),
        points: str = Form(""),
        due_at: str = Form(""),
        accessible_alternative: str = Form(""),
        assessment_response_type: str = Form("text"),
        attempts: int = Form(1),
        time_limit: int = Form(0),
        rubric: str = Form(""),
    ):
        user = _author(request, f"{STUDIO_PREFIX}/modules/{module_id}")
        if isinstance(user, RedirectResponse):
            return user
        if item_type not in ITEM_TYPES:
            raise HTTPException(400, "Invalid content type.")
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "A title is required.")
        points_value: float | None = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Invalid points value.") from exc
        accessible = accessible_alternative.strip()
        content = sanitize_html(body_html)
        if accessible:
            content += f'<section class="accessible-alternative"><h3>Accessible alternative</h3><p>{_esc(accessible)}</p></section>'
        metadata = {
            "accessible_alternative": accessible,
            "created_by": user["email"],
            "assessment": {
                "response_type": assessment_response_type,
                "attempts": max(1, attempts),
                "time_limit": max(0, time_limit),
                "rubric": rubric.strip(),
            } if item_type == "assessment" else {},
        }
        with db() as conn:
            module = _module(conn, module_id)
            _course_access(conn, int(module["course_id"]), user)
            _insert_item(
                conn,
                module_id,
                item_type,
                clean_title,
                body_html=content,
                external_url=safe_url(external_url),
                embed_url=safe_url(embed_url),
                metadata=metadata,
                points=points_value,
                due_at=due_at.strip() or None,
                status="draft",
            )
            audit(conn, user["email"], "visual_studio_item_created", "module", str(module_id), item_type, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{module_id}", status_code=303)

    @app.get(f"{STUDIO_PREFIX}/items/{{item_id}}/edit", response_class=HTMLResponse, response_model=None)
    async def edit_item_page(item_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/items/{item_id}/edit")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course_id, item, module = academic_access.item_bundle(conn, item_id)
            course = _course_access(conn, course_id, user)
        metadata = _metadata(item.get("metadata_json"))
        assessment = metadata.get("assessment") if isinstance(metadata.get("assessment"), dict) else {}
        safe_body = sanitize_html(str(item.get("body_html") or ""))
        body = f"""
        <main class="studio-shell" data-testid="visual-item-editor" data-studio-root>
          <nav class="studio-breadcrumbs" aria-label="Breadcrumb"><a href="{STUDIO_PREFIX}/courses/{course_id}">{_esc(course['course_code'])}</a><span>/</span><a href="{STUDIO_PREFIX}/modules/{int(module['id'])}">{_esc(module['title'])}</a><span>/</span><strong>{_esc(item['title'])}</strong></nav>
          <header class="studio-hero studio-hero--module"><div><p class="studio-eyebrow" data-i18n-en="Content editor" data-i18n-es="Editor de contenido">Content editor</p><h2>{_esc(item['title'])}</h2><p data-i18n-en="Use the visual toolbar or edit the supporting fields. Changes are saved only when you press Save." data-i18n-es="Utilice la barra visual o edite los campos complementarios. Los cambios se guardan cuando presiona Guardar.">Use the visual toolbar or edit the supporting fields. Changes are saved only when you press Save.</p></div><div class="studio-actions"><a class="studio-button studio-button--quiet" href="/admin/authoring/items/{item_id}/preview" target="_blank" rel="noopener" data-i18n-en="Preview" data-i18n-es="Vista previa">Preview</a></div></header>
          <form class="studio-panel" method="post" action="{STUDIO_PREFIX}/items/{item_id}/edit" data-rich-form data-autosave-key="item-{item_id}-edit">
            <div class="studio-form-grid">
              <label><span data-i18n-en="Type" data-i18n-es="Tipo">Type</span><select name="item_type" data-item-type>{_type_options(str(item.get('item_type') or 'page'))}</select></label>
              <label><span data-i18n-en="Title" data-i18n-es="Título">Title</span><input name="title" required value="{_esc(item['title'], attr=True)}"></label>
              <div class="studio-form-grid__wide">
                <span class="studio-label" data-i18n-en="Content, instructions, or question" data-i18n-es="Contenido, instrucciones o pregunta">Content, instructions, or question</span>
                <div class="studio-toolbar" role="toolbar" aria-label="Formatting toolbar"><button type="button" data-command="bold"><strong>B</strong></button><button type="button" data-command="italic"><em>I</em></button><button type="button" data-command="underline"><u>U</u></button><button type="button" data-command="formatBlock" data-command-value="h2">H2</button><button type="button" data-command="insertUnorderedList">• List</button><button type="button" data-command="createLink">Link</button><button type="button" data-command="removeFormat">Clear</button></div>
                <div class="studio-rich-editor" contenteditable="true" data-rich-editor>{safe_body}</div>
                <textarea name="body_html" data-rich-input hidden>{_esc(item.get('body_html'))}</textarea>
              </div>
              <label><span data-i18n-en="External or Google link" data-i18n-es="Enlace externo o de Google">External or Google link</span><input type="url" name="external_url" value="{_esc(item.get('external_url'), attr=True)}"></label>
              <label><span data-i18n-en="Embed, media, or WebXR URL" data-i18n-es="URL incrustada, multimedia o WebXR">Embed, media, or WebXR URL</span><input type="url" name="embed_url" value="{_esc(item.get('embed_url'), attr=True)}"></label>
              <label><span data-i18n-en="Points" data-i18n-es="Puntos">Points</span><input type="number" name="points" min="0" step="0.01" value="{_esc(item.get('points'), attr=True)}"></label>
              <label><span data-i18n-en="Due date" data-i18n-es="Fecha límite">Due date</span><input type="datetime-local" name="due_at" value="{_esc(item.get('due_at'), attr=True)}"></label>
              <label><span data-i18n-en="Status" data-i18n-es="Estado">Status</span><select name="status">{_status_options(str(item.get('status') or 'draft'), (("draft", "Draft", "Borrador"), ("published", "Published", "Publicado"), ("scheduled", "Scheduled", "Programado"), ("hidden", "Hidden", "Oculto")))}</select></label>
              <label><span data-i18n-en="Order" data-i18n-es="Orden">Order</span><input type="number" name="position" min="1" value="{int(item.get('position') or 1)}"></label>
              <label class="studio-form-grid__wide"><span data-i18n-en="Accessible alternative" data-i18n-es="Alternativa accesible">Accessible alternative</span><textarea name="accessible_alternative">{_esc(metadata.get('accessible_alternative'))}</textarea></label>
            </div>
            <fieldset class="studio-assessment-settings" data-assessment-settings{' hidden' if str(item.get('item_type')) != 'assessment' else ''}>
              <legend data-i18n-en="Assessment settings" data-i18n-es="Configuración de la evaluación">Assessment settings</legend>
              <div class="studio-form-grid">
                <label><span data-i18n-en="Response type" data-i18n-es="Tipo de respuesta">Response type</span><select name="assessment_response_type"><option value="text"{_selected(assessment.get('response_type'), 'text')}>Written response</option><option value="file"{_selected(assessment.get('response_type'), 'file')}>File or link</option><option value="multiple_choice"{_selected(assessment.get('response_type'), 'multiple_choice')}>Multiple choice</option><option value="true_false"{_selected(assessment.get('response_type'), 'true_false')}>True or false</option></select></label>
                <label><span data-i18n-en="Attempts" data-i18n-es="Intentos">Attempts</span><input type="number" name="attempts" min="1" value="{int(assessment.get('attempts') or 1)}"></label>
                <label><span data-i18n-en="Time limit in minutes" data-i18n-es="Límite de tiempo en minutos">Time limit in minutes</span><input type="number" name="time_limit" min="0" value="{int(assessment.get('time_limit') or 0)}"></label>
                <label class="studio-form-grid__wide"><span data-i18n-en="Rubric or grading criteria" data-i18n-es="Rúbrica o criterios de evaluación">Rubric or grading criteria</span><textarea name="rubric">{_esc(assessment.get('rubric'))}</textarea></label>
              </div>
            </fieldset>
            <div class="studio-form-footer"><span class="studio-save-state" aria-live="polite"></span><button class="studio-button" data-i18n-en="Save changes" data-i18n-es="Guardar cambios">Save changes</button></div>
          </form>
        </main>
        """
        return _studio_page("Edit content", body, user)

    @app.post(f"{STUDIO_PREFIX}/items/{{item_id}}/edit", response_model=None)
    async def update_item(
        item_id: int,
        request: Request,
        item_type: str = Form(...),
        title: str = Form(...),
        body_html: str = Form(""),
        external_url: str = Form(""),
        embed_url: str = Form(""),
        points: str = Form(""),
        due_at: str = Form(""),
        position: int = Form(1),
        status: str = Form("draft"),
        accessible_alternative: str = Form(""),
        assessment_response_type: str = Form("text"),
        attempts: int = Form(1),
        time_limit: int = Form(0),
        rubric: str = Form(""),
    ):
        user = _author(request, f"{STUDIO_PREFIX}/items/{item_id}/edit")
        if isinstance(user, RedirectResponse):
            return user
        if item_type not in ITEM_TYPES or status not in ITEM_STATES:
            raise HTTPException(400, "Invalid content type or status.")
        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "A title is required.")
        points_value: float | None = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "Invalid points value.") from exc
        with db() as conn:
            course_id, item, module = academic_access.item_bundle(conn, item_id)
            _course_access(conn, course_id, user)
            metadata = _metadata(item.get("metadata_json"))
            metadata["accessible_alternative"] = accessible_alternative.strip()
            metadata["updated_by"] = user["email"]
            metadata["assessment"] = {
                "response_type": assessment_response_type,
                "attempts": max(1, attempts),
                "time_limit": max(0, time_limit),
                "rubric": rubric.strip(),
            } if item_type == "assessment" else {}
            content = sanitize_html(body_html)
            execute(
                conn,
                """UPDATE nexus_content_items SET item_type=?,title=?,body_html=?,external_url=?,embed_url=?,
                   metadata_json=?,points=?,due_at=?,position=?,status=?,updated_at=? WHERE id=?""",
                (
                    item_type,
                    clean_title,
                    content,
                    safe_url(external_url),
                    safe_url(embed_url),
                    json.dumps(metadata, ensure_ascii=False),
                    points_value,
                    due_at.strip() or None,
                    max(1, position),
                    status,
                    utcnow(),
                    item_id,
                ),
            )
            audit(conn, user["email"], "visual_studio_item_updated", "item", str(item_id), status, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{int(module['id'])}", status_code=303)

    @app.post(f"{STUDIO_PREFIX}/items/{{item_id}}/move", response_model=None)
    async def move_item(item_id: int, request: Request, direction: str = Form(...)):
        user = _author(request, f"{STUDIO_PREFIX}/items/{item_id}/edit")
        if isinstance(user, RedirectResponse):
            return user
        if direction not in {"up", "down"}:
            raise HTTPException(400, "Invalid direction.")
        with db() as conn:
            course_id, item, module = academic_access.item_bundle(conn, item_id)
            _course_access(conn, course_id, user)
            _move_row(conn, "nexus_content_items", "module_id", int(module["id"]), item_id, direction)
            audit(conn, user["email"], "visual_studio_item_moved", "item", str(item_id), direction, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{int(module['id'])}", status_code=303)

    @app.post(f"{STUDIO_PREFIX}/items/{{item_id}}/duplicate", response_model=None)
    async def duplicate_item(item_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/items/{item_id}/edit")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course_id, item, module = academic_access.item_bundle(conn, item_id)
            _course_access(conn, course_id, user)
            _insert_item(
                conn,
                int(module["id"]),
                str(item.get("item_type") or "page"),
                f"{str(item.get('title') or 'Item')} — Copy",
                body_html=str(item.get("body_html") or ""),
                external_url=str(item.get("external_url") or ""),
                embed_url=str(item.get("embed_url") or ""),
                metadata=_metadata(item.get("metadata_json")),
                points=item.get("points"),
                due_at=item.get("due_at"),
                status="draft",
            )
            audit(conn, user["email"], "visual_studio_item_duplicated", "item", str(item_id), "", request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{int(module['id'])}", status_code=303)

    @app.post(f"{STUDIO_PREFIX}/items/{{item_id}}/toggle", response_model=None)
    async def toggle_item(item_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/items/{item_id}/edit")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course_id, item, module = academic_access.item_bundle(conn, item_id)
            _course_access(conn, course_id, user)
            next_state = "draft" if str(item.get("status")) == "published" else "published"
            execute(conn, "UPDATE nexus_content_items SET status=?,updated_at=? WHERE id=?", (next_state, utcnow(), item_id))
            audit(conn, user["email"], "visual_studio_item_status_changed", "item", str(item_id), next_state, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/modules/{int(module['id'])}", status_code=303)

    @app.post(f"{STUDIO_PREFIX}/modules/{{module_id}}/move", response_model=None)
    async def move_module(module_id: int, request: Request, direction: str = Form(...)):
        user = _author(request, f"{STUDIO_PREFIX}/modules/{module_id}")
        if isinstance(user, RedirectResponse):
            return user
        if direction not in {"up", "down"}:
            raise HTTPException(400, "Invalid direction.")
        with db() as conn:
            module = _module(conn, module_id)
            course_id = int(module["course_id"])
            _course_access(conn, course_id, user)
            _move_row(conn, "nexus_modules", "course_id", course_id, module_id, direction)
            audit(conn, user["email"], "visual_studio_module_moved", "module", str(module_id), direction, request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/courses/{course_id}", status_code=303)

    @app.post(f"{STUDIO_PREFIX}/modules/{{module_id}}/duplicate", response_model=None)
    async def duplicate_module(module_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/modules/{module_id}")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            module = _module(conn, module_id)
            course_id = int(module["course_id"])
            _course_access(conn, course_id, user)
            existing = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE course_id=?", (course_id,)))
            position = int(existing[0].get("total") or 0) + 1 if existing else 1
            now = utcnow()
            cur = execute(
                conn,
                """INSERT INTO nexus_modules
                   (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    course_id,
                    f"{str(module.get('title') or 'Module')} — Copy",
                    str(module.get("description") or ""),
                    str(module.get("learning_outcomes") or ""),
                    int(module.get("estimated_minutes") or 60),
                    position,
                    "draft",
                    now,
                    now,
                ),
            )
            new_module_id = int(getattr(cur, "lastrowid", 0) or 0)
            if not new_module_id:
                created = rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))
                new_module_id = int(created[0]["id"])
            source_items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
            for source in source_items:
                _insert_item(
                    conn,
                    new_module_id,
                    str(source.get("item_type") or "page"),
                    str(source.get("title") or "Item"),
                    body_html=str(source.get("body_html") or ""),
                    external_url=str(source.get("external_url") or ""),
                    embed_url=str(source.get("embed_url") or ""),
                    metadata=_metadata(source.get("metadata_json")),
                    points=source.get("points"),
                    due_at=source.get("due_at"),
                    status="draft",
                )
            audit(conn, user["email"], "visual_studio_module_duplicated", "module", str(module_id), str(new_module_id), request.client.host if request.client else "")
        return RedirectResponse(f"{STUDIO_PREFIX}/courses/{course_id}", status_code=303)

    app.openapi_schema = None
    print("NUVEDRA Visual Course Studio registered: visual authoring, local draft recovery, ordering, duplication, assessments, Google shortcuts, and student preview.", flush=True)
