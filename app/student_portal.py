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
        classroom = ""
        try:
            metadata = __import__("json").loads(item.get("metadata_json") or "{}")
        except (ValueError, TypeError):
            metadata = {}
        if item.get("item_type") == "vr" and metadata.get("technology") == "webxr_classroom":
            room_style = metadata.get("room_style", "classroom")
            accent = "#047857" if room_style == "lab" else "#4338ca"
            classroom = f"""<section class="card" aria-label="Aula virtual inmersiva">
<h3>Aula WebXR · {esc(item.get("title"))}</h3>
<p>Utiliza el ratón para explorar el aula. En Meta Quest, abre esta página en el navegador del visor y selecciona el botón de entrada a VR si está disponible. También puedes seguir las instrucciones de la clase sin visor.</p>
<script src="https://aframe.io/releases/1.8.0/aframe.min.js"></script>
<div style="width:100%;height:480px;position:relative;background:#e7ecf5;border-radius:14px;overflow:hidden">
<a-scene embedded vr-mode-ui="enabled: true" renderer="antialias: true" background="color: #E7ECF5">
<a-sky color="#E7ECF5"></a-sky><a-plane position="0 0 -4" rotation="-90 0 0" width="18" height="18" color="#cbd5e1"></a-plane>
<a-box position="0 2 -7" width="7" height="2.5" depth="0.12" color="{accent}"></a-box>
<a-text value="NUVEDRA - Aula virtual" align="center" width="5" color="#FFFFFF" position="0 2.8 -6.91"></a-text>
<a-text value="Explora y aprende" align="center" width="4" color="#FFFFFF" position="0 2 -6.91"></a-text>
<a-box position="-2 0.55 -3.5" width="1.4" height="0.15" depth="0.9" color="#64748b"></a-box>
<a-box position="2 0.55 -3.5" width="1.4" height="0.15" depth="0.9" color="#64748b"></a-box>
<a-box position="0 0.55 -4.7" width="1.4" height="0.15" depth="0.9" color="#64748b"></a-box>
<a-entity position="0 1.6 1"><a-camera><a-cursor color="{accent}"></a-cursor></a-camera></a-entity>
</a-scene></div><p id="xr-classroom-status" role="status">Si no aparece el aula, comprueba WebGL y la carga del motor A-Frame. El texto de la actividad permanece disponible.</p>
<script>
(function () {{
  const scene = document.querySelector('a-scene');
  const status = document.getElementById('xr-classroom-status');
  if (!scene || !status) return;
  scene.addEventListener('loaded', () => {{
    status.textContent = 'Aula 3D cargada. Usa el botón VR de la escena para solicitar el modo inmersivo si tu dispositivo lo permite.';
  }}, {{ once: true }});
  scene.addEventListener('renderstart', () => {{
    status.textContent = 'Escena 3D lista para explorar. El modo VR depende del visor y del navegador.';
  }}, {{ once: true }});
  scene.addEventListener('webglcontextlost', () => {{
    status.textContent = 'Se perdió el contexto gráfico WebGL. Recarga la página o utiliza la alternativa textual.';
  }});
}})();
</script>
</section>"""
        discussion = ""
        if str(item.get("item_type")) in {"vr", "discussion"}:
            with db() as conn:
                posts = rows(execute(conn, "SELECT author_email,body,created_at FROM nexus_forum_posts WHERE item_id=? ORDER BY id DESC LIMIT 100", (item_id,)))
            rendered = "".join(
                f'<article class="card"><strong>{esc(post["author_email"])}</strong><p style="white-space:pre-wrap">{esc(post["body"])}</p><small>{esc(post["created_at"])}</small></article>'
                for post in posts
            ) or '<p class="notice">Todavía no hay aportaciones. Inicia la conversación sobre esta experiencia.</p>'
            composer = (
                f'<form method="post" action="/learn/items/{item_id}/discuss"><label>Tu aportación<textarea name="body" required maxlength="5000" placeholder="Comparte una observación o pregunta sobre la actividad."></textarea></label><button>Publicar aportación</button></form>'
                if str(access.get("course_role")) == "student"
                else '<p class="notice">Puedes leer las aportaciones, pero tu rol no permite publicar.</p>'
            )
            discussion = f'<section class="card" aria-label="Comunidad de aprendizaje"><h3>Comunidad de aprendizaje</h3><p>Conversación vinculada a esta actividad. Evita compartir información personal o confidencial.</p>{composer}{rendered}</section>'
        assessment = ""
        if str(item.get("item_type")) in ASSESSMENT_TYPES and str(access.get("course_role")) == "student":
            existing = submissions[0] if submissions else {}
            saved = '<p class="success">Su respuesta está guardada. Puede actualizarla mientras la evaluación esté disponible.</p>' if submissions else ""
            assessment = f'''<section class="card"><h3>Responder evaluación</h3>{saved}<form method="post" action="/learn/items/{item_id}/submit"><label>Respuesta<textarea name="response_text" required>{esc(existing.get("response_text"))}</textarea></label><label>Enlace de evidencia (opcional)<input type="url" name="response_url" value="{esc(existing.get("response_url"), attr=True)}"></label><button>Guardar y entregar</button></form></section>'''
        elif str(item.get("item_type")) in ASSESSMENT_TYPES:
            assessment = '<p class="notice">El rol de observador permite consultar la evaluación, pero no enviar respuestas.</p>'
        body = f'<p><a href="/learn/courses/{course_id}">&larr; Volver al curso</a></p><section class="card content-body"><span class="badge">{esc(item.get("item_type"))}</span><h2>{esc(item["title"])}</h2>{item.get("body_html") or ""}{external}{embed}</section>{classroom}{discussion}{assessment}'
        return portal_page("Contenido", body, user)

    @app.post("/learn/items/{item_id}/discuss", response_model=None)
    async def student_discussion_post(item_id: int, request: Request, body: str = Form(...)):
        user = google_user(request)
        if not user:
            return login_redirect(f"/learn/items/{item_id}")
        clean = body.strip()
        if not clean or len(clean) > 5000:
            raise HTTPException(400, "La aportación debe contener entre 1 y 5000 caracteres.")
        with db() as conn:
            course_id, item, module = item_bundle(conn, item_id)
            access = require_course_role(conn, course_id, user["email"], {"student"})
            if (str(access.get("course_status")) != "active"
                or str(item.get("status")) != "published"
                or str(module.get("status")) != "published"
                or str(item.get("item_type")) not in {"vr", "discussion"}):
                raise HTTPException(403, "La comunidad no está disponible.")
            execute(conn, "INSERT INTO nexus_forum_posts (item_id,author_email,body,created_at) VALUES (?,?,?,?)", (item_id, user["email"], clean, utcnow()))
            audit(conn, user["email"], "student_discussion_post_created", "item", str(item_id), "", request.client.host if request.client else "")
        return RedirectResponse(f"/learn/items/{item_id}", status_code=303)

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
