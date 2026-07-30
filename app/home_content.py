from __future__ import annotations

import html
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.admin_console import (
    audit,
    database_url,
    db,
    execute,
    require_admin,
    rows,
    session_user,
    utcnow,
)

CONTENT_TYPES = {"banner", "announcement"}
STATUSES = {"draft", "published"}
ALLOWED_ADMIN_ROLES = {"course_admin"}


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _safe_url(value: str, *, allow_empty: bool = True) -> str:
    value = (value or "").strip()
    if not value and allow_empty:
        return ""
    if value.startswith(("/", "#")):
        return value
    parsed = urlparse(value)
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return value
    raise HTTPException(status_code=400, detail="La dirección debe comenzar con /, #, https:// o http://.")


def ensure_home_content_schema() -> None:
    identity = "INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY"
    if not database_url().startswith("postgres"):
        identity = "INTEGER PRIMARY KEY AUTOINCREMENT"

    statement = f"""
    CREATE TABLE IF NOT EXISTS nuvedra_home_content (
        id {identity},
        content_type TEXT NOT NULL,
        badge TEXT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        image_url TEXT,
        cta_label TEXT,
        cta_url TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        sort_order INTEGER NOT NULL DEFAULT 0,
        starts_at TEXT,
        ends_at TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """
    with db() as conn:
        execute(conn, statement)
        existing = rows(execute(conn, "SELECT COUNT(*) AS total FROM nuvedra_home_content"))[0]["total"]
        if int(existing or 0) == 0:
            now = utcnow()
            seed = [
                (
                    "banner",
                    "PLATAFORMA XR",
                    "Explora el aprendizaje inmersivo",
                    "Tecnología XR, inteligencia artificial y contenido adaptativo para transformar la educación.",
                    "/static/assets/nuvedra-hero.svg",
                    "Descubre NUVEDRA",
                    "#announcements-title",
                    "published",
                    1,
                    "",
                    "",
                    "system",
                    now,
                    now,
                ),
                (
                    "banner",
                    "INTELIGENCIA ADAPTATIVA",
                    "Aprendizaje que responde a cada estudiante",
                    "Analítica académica, rutas personalizadas y apoyo oportuno desde una sola plataforma.",
                    "/static/assets/nuvedra-hero.svg",
                    "Explorar analítica",
                    "#view-analytics",
                    "published",
                    2,
                    "",
                    "",
                    "system",
                    now,
                    now,
                ),
                (
                    "banner",
                    "INNOVACIÓN DOCENTE",
                    "Diseña experiencias educativas de próxima generación",
                    "Integra Google Workspace, realidad aumentada, realidad virtual y recursos interactivos.",
                    "/static/assets/nuvedra-hero.svg",
                    "Abrir Course Studio",
                    "/course-studio",
                    "published",
                    3,
                    "",
                    "",
                    "system",
                    now,
                    now,
                ),
                (
                    "announcement",
                    "EVENTO DESTACADO",
                    "Semana de la Innovación Educativa",
                    "Conferencias, demostraciones y experiencias prácticas sobre IA, XR y diseño educativo.",
                    "",
                    "Ver agenda",
                    "#upcoming-title",
                    "published",
                    1,
                    "",
                    "",
                    "system",
                    now,
                    now,
                ),
                (
                    "announcement",
                    "NOTICIAS",
                    "NUVEDRA incorpora nuevas aulas inmersivas",
                    "Experiencias colaborativas y accesibles para conectar la teoría con la práctica.",
                    "",
                    "Leer más",
                    "#announcements-title",
                    "published",
                    2,
                    "",
                    "",
                    "system",
                    now,
                    now,
                ),
                (
                    "announcement",
                    "TALLER DESTACADO",
                    "Diseño de experiencias de aprendizaje XR",
                    "Taller práctico para docentes que desean integrar experiencias inmersivas en sus cursos.",
                    "",
                    "Ver detalles",
                    "#upcoming-title",
                    "published",
                    3,
                    "",
                    "",
                    "system",
                    now,
                    now,
                ),
            ]
            for item in seed:
                execute(
                    conn,
                    """
                    INSERT INTO nuvedra_home_content (
                        content_type,badge,title,body,image_url,cta_label,cta_url,status,
                        sort_order,starts_at,ends_at,created_by,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    item,
                )


def _published_rows(content_type: str) -> list[dict[str, Any]]:
    now = utcnow()
    with db() as conn:
        data = rows(
            execute(
                conn,
                """
                SELECT id,content_type,badge,title,body,image_url,cta_label,cta_url,
                       status,sort_order,starts_at,ends_at,updated_at
                FROM nuvedra_home_content
                WHERE content_type=? AND status='published'
                  AND (starts_at IS NULL OR starts_at='' OR starts_at<=?)
                  AND (ends_at IS NULL OR ends_at='' OR ends_at>=?)
                ORDER BY sort_order ASC,id ASC
                """,
                (content_type, now, now),
            )
        )
    return data


def _edit_form(item: dict[str, Any] | None = None) -> str:
    item = item or {}
    item_id = _escape(item.get("id"))
    content_type = str(item.get("content_type") or "announcement")
    status = str(item.get("status") or "draft")
    type_options = "".join(
        f'<option value="{value}"{" selected" if value == content_type else ""}>{"Banner principal" if value == "banner" else "Anuncio"}</option>'
        for value in ("announcement", "banner")
    )
    status_options = "".join(
        f'<option value="{value}"{" selected" if value == status else ""}>{"Publicado" if value == "published" else "Borrador"}</option>'
        for value in ("draft", "published")
    )
    return f"""
    <section class="card">
      <h2>{'Editar contenido' if item_id else 'Crear contenido para la portada'}</h2>
      <p>Los cambios publicados aparecen automáticamente en la página principal de NUVEDRA.</p>
      <form method="post" action="/admin/home-content/save">
        <input type="hidden" name="item_id" value="{item_id}">
        <div class="grid">
          <label>Tipo<select name="content_type" required>{type_options}</select></label>
          <label>Estado<select name="status" required>{status_options}</select></label>
          <label>Orden<input type="number" name="sort_order" min="0" max="999" value="{_escape(item.get('sort_order') or 0)}"></label>
        </div>
        <label>Etiqueta corta<input name="badge" maxlength="60" value="{_escape(item.get('badge'))}" placeholder="NOTICIAS, EVENTO, PLATAFORMA XR"></label>
        <label>Título<input name="title" maxlength="140" required value="{_escape(item.get('title'))}"></label>
        <label>Descripción<textarea name="body" maxlength="1200" required>{_escape(item.get('body'))}</textarea></label>
        <label>Imagen o arte visual<input name="image_url" value="{_escape(item.get('image_url'))}" placeholder="/static/assets/imagen.svg o https://..."></label>
        <div class="grid">
          <label>Texto del botón<input name="cta_label" maxlength="60" value="{_escape(item.get('cta_label'))}"></label>
          <label>Enlace del botón<input name="cta_url" value="{_escape(item.get('cta_url'))}" placeholder="/ruta, #seccion o https://..."></label>
        </div>
        <div class="grid">
          <label>Publicar desde<input type="datetime-local" name="starts_at" value="{_escape(str(item.get('starts_at') or '')[:16])}"></label>
          <label>Publicar hasta<input type="datetime-local" name="ends_at" value="{_escape(str(item.get('ends_at') or '')[:16])}"></label>
        </div>
        <button type="submit">Guardar contenido</button>
        <a class="button secondary" href="/admin/home-content">Limpiar formulario</a>
        <a class="button secondary" href="/" target="_blank" rel="noopener">Ver portada</a>
      </form>
    </section>
    """


def register_home_content(app: FastAPI) -> None:
    ensure_home_content_schema()

    @app.get("/api/home-content", response_class=JSONResponse)
    async def public_home_content() -> dict[str, Any]:
        return {
            "banners": _published_rows("banner"),
            "announcements": _published_rows("announcement"),
        }

    @app.get("/admin/home-content", response_class=HTMLResponse, response_model=None)
    async def home_content_admin(request: Request, edit: int | None = None):
        user = session_user(request)
        if not user:
            return RedirectResponse("/admin/login", status_code=303)
        user = require_admin(request, ALLOWED_ADMIN_ROLES)

        with db() as conn:
            content = rows(
                execute(
                    conn,
                    "SELECT * FROM nuvedra_home_content ORDER BY content_type,sort_order,id",
                )
            )
            selected = None
            if edit is not None:
                found = rows(execute(conn, "SELECT * FROM nuvedra_home_content WHERE id=?", (edit,)))
                selected = found[0] if found else None

        table_rows = "".join(
            f"""
            <tr>
              <td><strong>{_escape(item.get('title'))}</strong><br><small>{_escape(item.get('badge'))}</small></td>
              <td>{'Banner' if item.get('content_type') == 'banner' else 'Anuncio'}</td>
              <td><span class="badge">{'Publicado' if item.get('status') == 'published' else 'Borrador'}</span></td>
              <td>{_escape(item.get('sort_order'))}</td>
              <td>
                <a class="button" href="/admin/home-content?edit={item['id']}">Editar</a>
                <form method="post" action="/admin/home-content/{item['id']}/toggle" style="display:inline">
                  <button class="button secondary" type="submit">{'Ocultar' if item.get('status') == 'published' else 'Publicar'}</button>
                </form>
                <form method="post" action="/admin/home-content/{item['id']}/delete" style="display:inline" onsubmit="return confirm('¿Eliminar este contenido?')">
                  <button class="danger" type="submit">Eliminar</button>
                </form>
              </td>
            </tr>
            """
            for item in content
        ) or '<tr><td colspan="5">No hay contenido configurado.</td></tr>'

        body = f"""
        <h2>Portada, anuncios y banners</h2>
        <p>Administre el carrusel principal y los anuncios destacados sin editar manualmente el HTML.</p>
        {_edit_form(selected)}
        <section class="card">
          <h2>Contenido configurado</h2>
          <table>
            <thead><tr><th>Contenido</th><th>Tipo</th><th>Estado</th><th>Orden</th><th>Acciones</th></tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
        </section>
        """
        from app.admin_portal import unified_page

        return unified_page("Portada y anuncios", body, user)

    @app.post("/admin/home-content/save")
    async def save_home_content(
        request: Request,
        item_id: str = Form(""),
        content_type: str = Form(...),
        badge: str = Form(""),
        title: str = Form(...),
        body: str = Form(...),
        image_url: str = Form(""),
        cta_label: str = Form(""),
        cta_url: str = Form(""),
        status: str = Form("draft"),
        sort_order: int = Form(0),
        starts_at: str = Form(""),
        ends_at: str = Form(""),
    ):
        user = require_admin(request, ALLOWED_ADMIN_ROLES)
        if content_type not in CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="Tipo de contenido inválido.")
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail="Estado inválido.")
        title = title.strip()
        body = body.strip()
        if len(title) < 3 or len(body) < 3:
            raise HTTPException(status_code=400, detail="El título y la descripción son requeridos.")
        image_url = _safe_url(image_url)
        cta_url = _safe_url(cta_url)
        now = utcnow()
        values = (
            content_type,
            badge.strip(),
            title,
            body,
            image_url,
            cta_label.strip(),
            cta_url,
            status,
            max(0, min(int(sort_order), 999)),
            starts_at.strip(),
            ends_at.strip(),
            now,
        )
        with db() as conn:
            if item_id.strip():
                execute(
                    conn,
                    """
                    UPDATE nuvedra_home_content
                    SET content_type=?,badge=?,title=?,body=?,image_url=?,cta_label=?,cta_url=?,
                        status=?,sort_order=?,starts_at=?,ends_at=?,updated_at=?
                    WHERE id=?
                    """,
                    values + (int(item_id),),
                )
                entity_id = item_id
                action = "home_content_updated"
            else:
                execute(
                    conn,
                    """
                    INSERT INTO nuvedra_home_content (
                        content_type,badge,title,body,image_url,cta_label,cta_url,status,
                        sort_order,starts_at,ends_at,created_by,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    values[:-1] + (user["email"], now, now),
                )
                entity_id = title
                action = "home_content_created"
            audit(
                conn,
                user["email"],
                action,
                "home_content",
                str(entity_id),
                title,
                request.client.host if request.client else "",
            )
        return RedirectResponse("/admin/home-content", status_code=303)

    @app.post("/admin/home-content/{item_id}/toggle")
    async def toggle_home_content(item_id: int, request: Request):
        user = require_admin(request, ALLOWED_ADMIN_ROLES)
        with db() as conn:
            found = rows(execute(conn, "SELECT status,title FROM nuvedra_home_content WHERE id=?", (item_id,)))
            if not found:
                raise HTTPException(status_code=404, detail="Contenido no encontrado.")
            status = "draft" if found[0]["status"] == "published" else "published"
            execute(
                conn,
                "UPDATE nuvedra_home_content SET status=?,updated_at=? WHERE id=?",
                (status, utcnow(), item_id),
            )
            audit(
                conn,
                user["email"],
                "home_content_status_changed",
                "home_content",
                str(item_id),
                status,
                request.client.host if request.client else "",
            )
        return RedirectResponse("/admin/home-content", status_code=303)

    @app.post("/admin/home-content/{item_id}/delete")
    async def delete_home_content(item_id: int, request: Request):
        user = require_admin(request, ALLOWED_ADMIN_ROLES)
        with db() as conn:
            found = rows(execute(conn, "SELECT title FROM nuvedra_home_content WHERE id=?", (item_id,)))
            if not found:
                raise HTTPException(status_code=404, detail="Contenido no encontrado.")
            execute(conn, "DELETE FROM nuvedra_home_content WHERE id=?", (item_id,))
            audit(
                conn,
                user["email"],
                "home_content_deleted",
                "home_content",
                str(item_id),
                found[0]["title"],
                request.client.host if request.client else "",
            )
        return RedirectResponse("/admin/home-content", status_code=303)
