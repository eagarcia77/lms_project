from __future__ import annotations

import html
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

import app.admin_console as admin_console
from app.admin_console import database_url, db, execute, require_admin, rows


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def _count(conn: Any, table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
    try:
        query = f"SELECT COUNT(*) AS total FROM {table}"
        if where:
            query += f" WHERE {where}"
        result = rows(execute(conn, query, params))
        return int(result[0].get("total") or 0) if result else 0
    except Exception:
        return 0


def _navigation() -> str:
    links = (
        ("/admin", "Panel general", "Inicio y operaciones"),
        ("/admin/authoring", "Diseño académico", "Cursos, módulos y evaluación"),
        ("/admin/authoring/innovation", "Innovación IA/XR", "IA, RA, VR, 360 y calidad"),
        ("/admin/courses", "Gestión de cursos", "Estados y supervisión"),
        ("/admin/enrollments", "Matrículas", "Participantes y roles"),
        ("/admin/users", "Usuarios", "Administradores y permisos"),
        ("/admin/audit", "Auditoría", "Trazabilidad institucional"),
        ("/admin/backup", "Respaldos", "Exportación de datos"),
        ("/admin/system", "Sistema", "Servicios y diagnóstico"),
    )
    return "".join(
        f'<a class="portal-link" href="{href}" data-route="{href}"><strong>{label}</strong><small>{description}</small></a>'
        for href, label, description in links
    )


def unified_page(title: str, body: str, user: dict[str, Any] | None = None) -> HTMLResponse:
    css = """
    :root{--navy:#09283d;--green:#007b5f;--gold:#fed141;--blue:#185adb;--ink:#172033;--muted:#586b7d;--soft:#f3f7f8;--line:#cbd7df;--white:#fff;--danger:#a61b1b;--focus:#ffbf47}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font:16px/1.55 Inter,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--soft)}
    a{color:#075985}.skip-link{position:absolute;left:-9999px;top:0;background:var(--gold);color:#111;padding:10px;z-index:20}.skip-link:focus{left:10px}
    .login-header{background:linear-gradient(120deg,var(--navy),var(--green));color:white;padding:24px 5vw}.login-main{width:min(1180px,92%);margin:32px auto}
    .portal-shell{min-height:100vh;display:grid;grid-template-columns:292px minmax(0,1fr)}
    .portal-sidebar{background:linear-gradient(180deg,var(--navy),#0c3d4b 58%,var(--green));color:white;padding:24px 18px;position:sticky;top:0;height:100vh;overflow:auto}
    .portal-brand{display:block;color:white;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.24);padding:0 10px 20px;margin-bottom:16px}.portal-brand strong{display:block;font-size:1.32rem}.portal-brand span{display:block;color:#dbeafe;margin-top:3px}
    .portal-nav{display:grid;gap:7px}.portal-link{color:white;text-decoration:none;padding:11px 12px;border-radius:11px;display:block}.portal-link strong,.portal-link small{display:block}.portal-link small{color:#cfe5eb;font-size:.78rem;margin-top:2px}.portal-link:hover,.portal-link[aria-current="page"]{background:rgba(255,255,255,.16);box-shadow:inset 4px 0 var(--gold)}
    .portal-account{border-top:1px solid rgba(255,255,255,.24);margin-top:18px;padding:16px 10px 0}.portal-account a{color:white}.portal-account small{display:block;color:#dbeafe}
    .portal-workspace{min-width:0}.portal-topbar{background:white;border-bottom:1px solid var(--line);padding:15px 3vw;display:flex;gap:16px;align-items:center;position:sticky;top:0;z-index:8}.portal-topbar h1{font-size:1.2rem;margin:0}.portal-topbar .platform-link{margin-left:auto;font-weight:800}.menu-button{display:none;border:0;background:var(--navy);color:white;border-radius:8px;padding:9px 12px}
    main{width:min(1320px,94%);margin:28px auto 60px}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:22px;margin:16px 0;box-shadow:0 8px 24px rgba(16,42,67,.07)}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.metric strong{font-size:2rem;color:var(--green);display:block}.metric a{font-weight:800}.operations .card{border-top:5px solid var(--green)}
    table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eaf2f4}
    label{font-weight:700;display:block;margin-top:12px}input,select,textarea{width:100%;padding:11px;border:1px solid #8093a7;border-radius:8px;font:inherit}textarea{min-height:90px}
    button,.button{display:inline-block;background:var(--blue);color:white;border:0;border-radius:9px;padding:11px 16px;font-weight:800;text-decoration:none;margin:8px 5px 0 0;cursor:pointer}.button.secondary{background:var(--green)}.danger{background:var(--danger)}
    .status{font-weight:800}.error{background:#ffe9e9;border-left:5px solid var(--danger);padding:12px}.notice{background:#e7f1ff;border-left:5px solid var(--blue);padding:12px}.badge{display:inline-block;border-radius:999px;background:#e2f3ee;padding:3px 9px;font-weight:800}
    a:focus,button:focus,input:focus,select:focus,textarea:focus{outline:4px solid var(--focus);outline-offset:2px}
    @media(max-width:920px){.portal-shell{display:block}.portal-sidebar{position:fixed;left:-310px;z-index:12;width:292px;transition:left .2s}.portal-sidebar.open{left:0}.menu-button{display:inline-block}.portal-topbar{padding:12px 4vw}table{display:block;overflow:auto}}
    """
    if not user:
        return HTMLResponse(
            f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_escape(title)} · NEXUS</title><style>{css}</style></head><body><a class="skip-link" href="#main-content">Saltar al contenido</a><header class="login-header"><h1>NEXUS EDU XR</h1><p>Plataforma institucional unificada</p></header><main id="main-content" class="login-main">{body}</main></body></html>'
        )

    nav = _navigation()
    user_name = _escape(user.get("full_name"))
    role = _escape(user.get("role"))
    script = """
    <script>
    (()=>{
      const current=location.pathname;
      const links=[...document.querySelectorAll('[data-route]')];
      const exact=links.find(link=>link.dataset.route===current);
      const selected=exact || links.filter(link=>current.startsWith(link.dataset.route + '/')).sort((a,b)=>b.dataset.route.length-a.dataset.route.length)[0];
      if(selected) selected.setAttribute('aria-current','page');
      const button=document.getElementById('portal-menu');
      const sidebar=document.getElementById('portal-sidebar');
      button?.addEventListener('click',()=>{const open=sidebar.classList.toggle('open');button.setAttribute('aria-expanded',String(open));});
    })();
    </script>
    """
    return HTMLResponse(
        f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_escape(title)} · NEXUS</title><style>{css}</style></head><body><a class="skip-link" href="#main-content">Saltar al contenido</a><div class="portal-shell"><aside id="portal-sidebar" class="portal-sidebar"><a class="portal-brand" href="/admin"><strong>NEXUS EDU XR</strong><span>Administración integral</span></a><nav class="portal-nav" aria-label="Administración principal">{nav}</nav><div class="portal-account"><strong>{user_name}</strong><small>{role}</small><p><a href="/">Abrir plataforma</a> · <a href="/admin/logout">Salir</a></p></div></aside><div class="portal-workspace"><header class="portal-topbar"><button id="portal-menu" class="menu-button" aria-controls="portal-sidebar" aria-expanded="false">Menú</button><h1>{_escape(title)}</h1><a class="platform-link" href="/">Vista de la plataforma</a></header><main id="main-content">{body}</main></div></div>{script}</body></html>'''
    )


def _replace_get_route(app: FastAPI, path: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and "GET" in set(getattr(route, "methods", set()) or set())
        )
    ]


def _patch_page_renderers() -> None:
    admin_console.page = unified_page
    try:
        import app.admin_system as admin_system
        admin_system.page = unified_page
    except Exception:
        pass
    try:
        import app.unified_authoring as unified_authoring
        unified_authoring.page = unified_page
    except Exception:
        pass
    try:
        import app.innovation_hub as innovation_hub
        innovation_hub.page = unified_page
    except Exception:
        pass
    try:
        import app.admin_authoring_v6 as authoring_v6
        authoring_v6.page = unified_page
    except Exception:
        pass


def register_admin_portal(app: FastAPI) -> None:
    _patch_page_renderers()
    _replace_get_route(app, "/admin")
    _replace_get_route(app, "/admin/courses")

    @app.get("/admin", response_class=HTMLResponse, response_model=None)
    async def integrated_dashboard(request: Request):
        user = require_admin(request)
        with db() as conn:
            metrics = {
                "courses": _count(conn, "nexus_admin_courses"),
                "active_courses": _count(conn, "nexus_admin_courses", "status='active'"),
                "modules": _count(conn, "nexus_modules"),
                "items": _count(conn, "nexus_content_items"),
                "xr": _count(conn, "nexus_content_items", "item_type IN ('ar','vr','360')"),
                "enrollments": _count(conn, "nexus_admin_enrollments"),
                "admins": _count(conn, "nexus_admin_users", "active=1"),
                "events": _count(conn, "nexus_admin_audit"),
            }
            recent_courses = rows(execute(conn, "SELECT id,course_code,title,status,updated_at FROM nexus_admin_courses ORDER BY updated_at DESC,id DESC LIMIT 6"))
            recent_events = rows(execute(conn, "SELECT actor_email,action,entity_type,created_at FROM nexus_admin_audit ORDER BY id DESC LIMIT 8"))

        course_rows = "".join(
            f'<tr><td><strong>{_escape(course["course_code"])}</strong><br>{_escape(course["title"])}</td><td><span class="badge">{_escape(course.get("status") or "draft")}</span></td><td><a href="/admin/authoring/courses/{course["id"]}">Diseñar</a> · <a href="/admin/authoring/innovation/courses/{course["id"]}">Innovación</a></td></tr>'
            for course in recent_courses
        ) or '<tr><td colspan="3">No hay cursos creados.</td></tr>'
        event_rows = "".join(
            f'<tr><td>{_escape(event.get("created_at"))}</td><td>{_escape(event.get("actor_email"))}</td><td>{_escape(event.get("action"))}</td><td>{_escape(event.get("entity_type"))}</td></tr>'
            for event in recent_events
        ) or '<tr><td colspan="4">No hay actividad registrada.</td></tr>'
        service_cards = (
            ("Base de datos", "PostgreSQL de Render" if database_url().startswith("postgres") else "SQLite local", True),
            ("Google Workspace", "Configurado" if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") else "Configuración pendiente", bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))),
            ("Inteligencia artificial", "Proveedor externo y alternativa local" if os.getenv("AI_BASE_URL") else "Asistente local gratuito activo", True),
            ("OpenDocument", "Collabora disponible" if os.getenv("COLLABORA_BASE_URL") else "Exportación ODT, ODP y ODS", True),
        )
        services = "".join(
            f'<div class="card"><h3>{_escape(name)}</h3><p class="status">{"Operativo" if ok else "Atención"}</p><p>{_escape(detail)}</p></div>'
            for name, detail, ok in service_cards
        )
        body = f'''
        <h2>Centro de operaciones de NEXUS EDU XR</h2>
        <p>Todos los componentes académicos, tecnológicos y administrativos se controlan desde este panel.</p>
        <div class="grid">
          <div class="card metric"><strong>{metrics["courses"]}</strong>Cursos totales<br><small>{metrics["active_courses"]} activos</small></div>
          <div class="card metric"><strong>{metrics["modules"]}</strong>Módulos</div>
          <div class="card metric"><strong>{metrics["items"]}</strong>Contenidos y evaluaciones</div>
          <div class="card metric"><strong>{metrics["xr"]}</strong>Experiencias RA/VR/360</div>
          <div class="card metric"><strong>{metrics["enrollments"]}</strong>Matrículas</div>
          <div class="card metric"><strong>{metrics["admins"]}</strong>Administradores activos</div>
        </div>
        <h2>Operaciones principales</h2>
        <div class="grid operations">
          <section class="card"><h3>Diseño académico</h3><p>Cree cursos, módulos, contenido, asignaciones, foros, exámenes y recursos Google.</p><a class="button secondary" href="/admin/authoring">Abrir Course Studio</a></section>
          <section class="card"><h3>IA y experiencias inmersivas</h3><p>Genere contenido con IA, incorpore RA, VR, 360, H5P y simulaciones, y revise accesibilidad.</p><a class="button secondary" href="/admin/authoring/innovation">Abrir Innovación IA/XR</a></section>
          <section class="card"><h3>Personas y acceso</h3><p>Administre usuarios, permisos, matrículas y roles dentro de los cursos.</p><a class="button" href="/admin/users">Usuarios</a><a class="button" href="/admin/enrollments">Matrículas</a></section>
          <section class="card"><h3>Gobernanza y continuidad</h3><p>Revise auditoría, estado de servicios y respaldos institucionales.</p><a class="button" href="/admin/system">Sistema</a><a class="button" href="/admin/audit">Auditoría</a><a class="button" href="/admin/backup">Respaldo</a></section>
        </div>
        <h2>Servicios integrados</h2><div class="grid">{services}</div>
        <div class="grid">
          <section class="card"><h3>Cursos recientes</h3><table><thead><tr><th>Curso</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{course_rows}</tbody></table><p><a class="button" href="/admin/courses">Ver todos los cursos</a></p></section>
          <section class="card"><h3>Actividad institucional reciente</h3><table><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Entidad</th></tr></thead><tbody>{event_rows}</tbody></table></section>
        </div>
        '''
        return unified_page("Panel general", body, user)

    @app.get("/admin/courses", response_class=HTMLResponse, response_model=None)
    async def integrated_courses(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses ORDER BY updated_at DESC,id DESC"))
            for course in courses:
                course["modules"] = _count(conn, "nexus_modules", "course_id=?", (course["id"],))
                course["enrollments"] = _count(conn, "nexus_admin_enrollments", "course_id=?", (course["id"],))
                module_ids = rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course["id"],)))
                course["items"] = sum(_count(conn, "nexus_content_items", "module_id=?", (module["id"],)) for module in module_ids)
        rows_html = "".join(
            f'''<tr><td><strong>{_escape(course["course_code"])}</strong><br>{_escape(course["title"])}</td><td>{_escape(course.get("term"))}</td><td><span class="badge">{_escape(course.get("status") or "draft")}</span></td><td>{course["modules"]}</td><td>{course["items"]}</td><td>{course["enrollments"]}</td><td><a class="button" href="/admin/authoring/courses/{course["id"]}">Diseñar</a><a class="button secondary" href="/admin/authoring/innovation/courses/{course["id"]}">IA/XR</a><form method="post" action="/admin/courses/{course["id"]}/status"><select name="status"><option value="draft">Borrador</option><option value="active">Activo</option><option value="completed">Completado</option><option value="archived">Archivado</option></select><button>Actualizar estado</button></form></td></tr>'''
            for course in courses
        ) or '<tr><td colspan="7">No hay cursos. Utilice Course Studio para crear el primero.</td></tr>'
        body = f'''
        <h2>Gestión integrada de cursos</h2>
        <p>La creación y el diseño académico se realizan en Course Studio; esta vista concentra supervisión, estado, matrículas e innovación.</p>
        <p><a class="button secondary" href="/admin/authoring">Crear o diseñar curso</a><a class="button" href="/admin/authoring/innovation">Centro de Innovación</a><a class="button" href="/admin/enrollments">Administrar matrículas</a></p>
        <section class="card"><table><thead><tr><th>Curso</th><th>Periodo</th><th>Estado</th><th>Módulos</th><th>Recursos</th><th>Matrículas</th><th>Administrar</th></tr></thead><tbody>{rows_html}</tbody></table></section>
        '''
        return unified_page("Gestión de cursos", body, user)

    print("Portal administrativo integral registrado.", flush=True)
