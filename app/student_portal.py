from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.academic_access import ASSESSMENT_TYPES, STUDENT_ROLES, esc, google_user, item_bundle, login_redirect, portal_page, require_course_role
from app.admin_authoring_v6 import safe_url
from app.admin_console import audit, db, execute, rows, utcnow


def _module_html(module: dict, items: list[dict]) -> str:
    links = "".join(
        f'<li><a href="/learn/items/{item["id"]}">{esc(item["title"])}</a> <small>({esc(item.get("item_type"))})</small></li>'
        for item in items
    ) or "<li>No hay contenido publicado.</li>"
    return f'<section class="card module"><h3>{int(module.get("position") or 1)}. {esc(module["title"])}</h3><p>{esc(module.get("description"))}</p><ul>{links}</ul></section>'


def register_student_portal(app: FastAPI) -> None:
    @app.get("/learn/courses/{course_id}", response_class=HTMLResponse, response_model=None)
    async def student_course(course_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/courses/{course_id}")
        with db() as conn:
            access = require_course_role(conn, course_id, user["email"], STUDENT_ROLES)
            if str(access.get("course_status")) != "active":
                raise HTTPException(403, "El curso todavía no está disponible.")
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? AND status='published' ORDER BY position,id", (course_id,)))
            sections: list[str] = []
            for module in modules:
                items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? AND status='published' ORDER BY position,id", (module["id"],)))
                sections.append(_module_html(module, items))
        content = "".join(sections) or '<p class="notice">El profesor todavía no ha publicado módulos.</p>'
        body = f'<p><a href="/portal">&larr; Mis cursos</a></p><h2>{esc(access["course_code"])}: {esc(access["title"])}</h2><p>{esc(access.get("description"))}</p>{content}'
        return portal_page("Curso", body, user)

    @app.get("/learn/items/{item_id}", response_class=HTMLResponse, response_model=None)
    async def student_item(item_id: int, request: Request):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/items/{item_id}")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            access = require_course_role(conn, course_id, user["email"], STUDENT_ROLES)
            if str(access.get("course_status")) != "active" or str(item.get("status")) != "published" or str(module.get("status")) != "published":
                raise HTTPException(403, "El contenido no está publicado.")
            submissions = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, user["email"])))
        external = ""
        if item.get("external_url"):
            external = f'<p><a class="button secondary" href="{esc(item.get("external_url"), attr=True)}" target="_blank" rel="noopener">Abrir recurso</a></p>'
        embed = ""
        if item.get("embed_url"):
            embed = f'<iframe src="{esc(item.get("embed_url"), attr=True)}" title="{esc(item.get("title"), attr=True)}" allow="fullscreen; xr-spatial-tracking"></iframe>'
        assessment = ""
        if str(item.get("item_type")) in ASSESSMENT_TYPES:
            existing = submissions[0] if submissions else {}
            saved = '<p class="success">Su respuesta está guardada. Puede actualizarla mientras la evaluación esté disponible.</p>' if submissions else ""
            assessment = f'''<section class="card"><h3>Responder evaluación</h3>{saved}<form method="post" action="/learn/items/{item_id}/submit"><label>Respuesta<textarea name="response_text" required>{esc(existing.get("response_text"))}</textarea></label><label>Enlace de evidencia (opcional)<input type="url" name="response_url" value="{esc(existing.get("response_url"), attr=True)}"></label><button>Guardar y entregar</button></form></section>'''
        body = f'<p><a href="/learn/courses/{course_id}">&larr; Volver al curso</a></p><section class="card content-body"><span class="badge">{esc(item.get("item_type"))}</span><h2>{esc(item["title"])}</h2>{item.get("body_html") or ""}{external}{embed}</section>{assessment}'
        return portal_page("Contenido", body, user)

    @app.post("/learn/items/{item_id}/submit", response_model=None)
    async def submit_assessment(item_id: int, request: Request, response_text: str = Form(...), response_url: str = Form("")):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/items/{item_id}")
        response = response_text.strip()
        if not response:
            raise HTTPException(400, "La respuesta no puede estar vacía.")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            access = require_course_role(conn, course_id, user["email"], {"student"})
            if str(access.get("course_status")) != "active" or str(item.get("item_type")) not in ASSESSMENT_TYPES or str(item.get("status")) != "published" or str(module.get("status")) != "published":
                raise HTTPException(403, "Esta evaluación no está disponible.")
            evidence = safe_url(response_url) or None
            found = rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, user["email"])))
            if found:
                execute(conn, "UPDATE nuvedra_submissions SET response_text=?,response_url=?,status='submitted',updated_at=? WHERE id=?", (response, evidence, utcnow(), found[0]["id"]))
            else:
                now = utcnow()
                execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)", (item_id, user["email"], response, evidence, "submitted", now, now))
            audit(conn, user["email"], "student_assessment_submitted", "item", str(item_id), "submitted", request.client.host if request.client else "")
        return RedirectResponse(f"/learn/items/{item_id}", status_code=303)
