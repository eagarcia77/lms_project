from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.admin_console as admin_console
from app.academic_access import assign_professor
from app.admin_console import audit, db, execute, require_admin, rows, utcnow
from app.unified_authoring import PREFIX, _course, _module


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


def _has_instructor_access(conn: Any, course_id: int, email: str) -> bool:
    found = rows(
        execute(
            conn,
            """SELECT id FROM nexus_admin_enrollments
               WHERE course_id=? AND lower(user_email)=? AND course_role IN
               ('instructor','teaching_assistant','course_builder','facilitator')
               AND status='active'""",
            (course_id, email.strip().lower()),
        )
    )
    return bool(found)


def _grant_instructor_access(conn: Any, course_id: int, email: str) -> None:
    """Give an administrator course-level instructor access without replacing the primary instructor."""
    assign_professor(conn, course_id, email.strip().lower())


def register_course_editor_access(app: FastAPI) -> None:
    """Restore a complete edit path after the administrative course page overrides the workspace page."""
    if getattr(app.state, "nuvedra_course_editor_access", False):
        return
    app.state.nuvedra_course_editor_access = True

    _remove_route(app, f"{PREFIX}/courses/{{course_id}}", "GET")

    @app.get(f"{PREFIX}/courses/{{course_id}}", response_class=HTMLResponse, response_model=None)
    async def editable_course_page(course_id: int, request: Request):
        admin = require_admin(request, {"course_admin"})
        admin_email = str(admin.get("email") or "").strip().lower()

        with db() as conn:
            course = _course(conn, course_id)
            modules = rows(
                execute(
                    conn,
                    """SELECT m.*,
                       (SELECT COUNT(*) FROM nexus_content_items i WHERE i.module_id=m.id) AS item_total
                       FROM nexus_modules m WHERE m.course_id=? ORDER BY m.position,m.id""",
                    (course_id,),
                )
            )
            instructor_access = _has_instructor_access(conn, course_id, admin_email)
            enrollment_counts = rows(
                execute(
                    conn,
                    """SELECT course_role,COUNT(*) AS total FROM nexus_admin_enrollments
                       WHERE course_id=? AND status='active' GROUP BY course_role""",
                    (course_id,),
                )
            )

        counts = {str(row["course_role"]): int(row.get("total") or 0) for row in enrollment_counts}
        access_message = (
            '<p class="success"><strong>Acceso docente activo.</strong> Puede abrir el editor del profesor y modificar módulos, contenido y evaluaciones.</p>'
            if instructor_access
            else '<p class="notice"><strong>Acceso docente pendiente.</strong> Use el botón “Editar contenido del curso” para añadirse como instructor de este curso sin reemplazar al profesor principal.</p>'
        )

        module_rows = "".join(
            f"""
            <tr>
              <td><strong>{int(module.get('position') or 1)}. {_esc(module['title'])}</strong><br><small>{_esc(module.get('description'))}</small></td>
              <td>{_esc(module.get('status') or 'draft')}</td>
              <td>{int(module.get('item_total') or 0)}</td>
              <td>
                <form method="post" action="{PREFIX}/modules/{int(module['id'])}/open-editor" style="display:inline">
                  <button type="submit">Editar contenido</button>
                </form>
                <a class="button secondary" href="{PREFIX}/modules/{int(module['id'])}">Studio administrativo</a>
              </td>
            </tr>
            """
            for module in modules
        ) or '<tr><td colspan="4">El curso todavía no contiene módulos. Abra el editor del profesor para crear el primero.</td></tr>'

        body = f"""
        <p><a href="{PREFIX}">&larr; Todos los cursos</a></p>
        <h2>{_esc(course['course_code'])}: {_esc(course['title'])}</h2>
        <p class="notice"><strong>Flujo de trabajo:</strong> el administrador configura el curso y las matrículas. El instructor crea módulos, contenido y evaluaciones. Un administrador también puede trabajar como instructor mediante el botón de acceso docente.</p>
        {access_message}

        <div class="grid">
          <section class="card">
            <h3>Editar configuración del curso</h3>
            <form method="post" action="{PREFIX}/courses/{course_id}/update">
              <label>Código<input name="course_code" required maxlength="40" value="{_esc(course['course_code'], attr=True)}"></label>
              <label>Título<input name="title" required maxlength="180" value="{_esc(course['title'], attr=True)}"></label>
              <label>Descripción<textarea name="description">{_esc(course.get('description'))}</textarea></label>
              <label>Periodo<input name="term" value="{_esc(course.get('term'), attr=True)}"></label>
              <label>Profesor responsable<input type="email" name="instructor_email" value="{_esc(course.get('instructor_email'), attr=True)}"></label>
              <div class="grid">
                <label>Inicio<input type="date" name="start_date" value="{_esc(course.get('start_date'), attr=True)}"></label>
                <label>Fin<input type="date" name="end_date" value="{_esc(course.get('end_date'), attr=True)}"></label>
              </div>
              <label>Estado<select name="status">
                <option value="draft"{_selected(course.get('status'), 'draft')}>Borrador</option>
                <option value="active"{_selected(course.get('status'), 'active')}>Activo para estudiantes</option>
                <option value="archived"{_selected(course.get('status'), 'archived')}>Archivado</option>
              </select></label>
              <button type="submit">Guardar configuración</button>
            </form>
          </section>

          <section class="card">
            <h3>Editar contenido del curso</h3>
            <p>Abra una vista sencilla para crear y editar módulos, páginas, archivos, enlaces, Google Workspace, actividades y assessments.</p>
            <form method="post" action="{PREFIX}/courses/{course_id}/open-editor">
              <button type="submit">Abrir editor del profesor</button>
            </form>
            <p><strong>Profesor principal:</strong><br>{_esc(course.get('instructor_email') or 'Sin asignar')}</p>
            <p><span class="badge">{counts.get('instructor', 0)} instructores</span> <span class="badge">{counts.get('student', 0)} estudiantes</span> <span class="badge">{counts.get('observer', 0)} observadores</span></p>
            <a class="button secondary" href="/admin/enrollments">Administrar matrículas</a>
            <a class="button secondary" href="{PREFIX}/courses/{course_id}/google-hub">Google Hub</a>
            <a class="button secondary" href="{PREFIX}/courses/{course_id}/emerging">Tecnologías emergentes</a>
          </section>
        </div>

        <h2>Módulos y contenido</h2>
        <section class="card"><table>
          <thead><tr><th>Módulo</th><th>Estado</th><th>Elementos</th><th>Acciones</th></tr></thead>
          <tbody>{module_rows}</tbody>
        </table></section>
        """
        return admin_console.page("Editar curso y contenido", body, admin)

    @app.post(f"{PREFIX}/courses/{{course_id}}/open-editor", response_model=None)
    async def open_course_editor(course_id: int, request: Request):
        admin = require_admin(request, {"course_admin"})
        email = str(admin.get("email") or "").strip().lower()
        with db() as conn:
            course = _course(conn, course_id)
            if not _has_instructor_access(conn, course_id, email):
                _grant_instructor_access(conn, course_id, email)
                audit(
                    conn,
                    email,
                    "administrator_enabled_as_instructor",
                    "course",
                    str(course_id),
                    str(course.get("course_code") or ""),
                    request.client.host if request.client else "",
                )
        return RedirectResponse(f"/faculty/courses/{course_id}", status_code=303)

    @app.post(f"{PREFIX}/modules/{{module_id}}/open-editor", response_model=None)
    async def open_module_editor(module_id: int, request: Request):
        admin = require_admin(request, {"course_admin"})
        email = str(admin.get("email") or "").strip().lower()
        with db() as conn:
            module = _module(conn, module_id)
            course_id = int(module["course_id"])
            if not _has_instructor_access(conn, course_id, email):
                _grant_instructor_access(conn, course_id, email)
                audit(
                    conn,
                    email,
                    "administrator_enabled_as_instructor",
                    "course",
                    str(course_id),
                    f"module:{module_id}",
                    request.client.host if request.client else "",
                )
        return RedirectResponse(f"/faculty/modules/{module_id}", status_code=303)

    app.openapi_schema = None
    print("NUVEDRA course editing restored: administrators can edit settings and open the instructor content editor.", flush=True)
