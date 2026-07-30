from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.academic_access as academic_access
import app.admin_console as admin_console
import app.admin_portal as admin_portal
import app.faculty_portal as faculty_portal
import app.google_hub_safe as google_hub_safe
import app.student_portal as student_portal
from app.admin_authoring_v6 import _template_modules
from app.admin_console import audit, db, execute, require_admin, rows, session_user, utcnow
from app.unified_authoring import PREFIX

STATIC_DIR = Path(__file__).resolve().parent / "static"
I18N_TAG = '<script src="/static/i18n.js" defer></script>'


def _remove_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def _inject_i18n(response: HTMLResponse, *, admin_identity: bool = False) -> HTMLResponse:
    raw = bytes(response.body).decode("utf-8", errors="replace")
    raw = raw.replace('<html lang="es">', '<html lang="en">', 1)
    if admin_identity:
        raw = raw.replace(
            '<a href="/portal/logout">Salir</a>',
            '<a href="/admin">Administración</a><a href="/admin/logout">Salir</a>',
            1,
        )
    if I18N_TAG not in raw:
        raw = raw.replace("</body>", f"{I18N_TAG}</body>", 1)
    headers = dict(response.headers)
    headers.pop("content-length", None)
    headers.pop("content-type", None)
    return HTMLResponse(raw, status_code=response.status_code, headers=headers)


def academic_user(request: Request) -> dict[str, Any] | None:
    """Resolve Google users first, then an authenticated administrator.

    Course permissions remain enrollment-based, so an administrator only receives
    instructor functions when that same email is enrolled as an instructor.
    """
    google = request.session.get("user")
    if isinstance(google, dict):
        email = str(google.get("email") or "").strip().lower()
        if email:
            resolved = dict(google)
            resolved["email"] = email
            resolved["_auth_source"] = "google"
            return resolved

    admin = session_user(request)
    if not admin:
        return None
    return {
        "id": f"admin:{admin.get('id')}",
        "name": str(admin.get("full_name") or admin.get("email") or "Administrator"),
        "email": str(admin.get("email") or "").strip().lower(),
        "picture": "",
        "admin_role": str(admin.get("role") or ""),
        "_auth_source": "admin",
    }


def _install_identity_resolution() -> None:
    academic_access.google_user = academic_user
    faculty_portal.google_user = academic_user
    student_portal.google_user = academic_user
    google_hub_safe.google_user = academic_user


def _install_page_renderers() -> None:
    original_portal_page = academic_access.portal_page
    original_admin_page = admin_portal.unified_page

    def enhanced_portal_page(
        title: str,
        body: str,
        user: dict[str, Any] | None = None,
    ) -> HTMLResponse:
        response = original_portal_page(title, body, user)
        return _inject_i18n(
            response,
            admin_identity=bool(user and user.get("_auth_source") == "admin"),
        )

    def enhanced_admin_page(
        title: str,
        body: str,
        user: dict[str, Any] | None = None,
    ) -> HTMLResponse:
        if user:
            email = html.escape(str(user.get("email") or ""), quote=True)
            body = re.sub(
                r'<label>Profesor<input type="email" name="instructor_email"></label>',
                (
                    '<label>Correo del instructor<input type="email" '
                    f'name="instructor_email" value="{email}"></label>'
                    '<p class="notice"><strong>Administrador e instructor:</strong> '
                    'puede conservar su propio correo para administrar el curso y también crear su contenido, '
                    'o sustituirlo por el correo de otro profesor.</p>'
                ),
                body,
                count=1,
            )
        response = original_admin_page(title, body, user)
        raw = bytes(response.body).decode("utf-8", errors="replace")
        raw = raw.replace('<html lang="es">', '<html lang="en">', 1)
        raw = raw.replace(
            '<a href="/">Abrir plataforma</a>',
            '<a href="/portal">Portal académico</a> · <a href="/">Abrir plataforma</a>',
            1,
        )
        if I18N_TAG not in raw:
            raw = raw.replace("</body>", f"{I18N_TAG}</body>", 1)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        return HTMLResponse(raw, status_code=response.status_code, headers=headers)

    academic_access.portal_page = enhanced_portal_page
    faculty_portal.portal_page = enhanced_portal_page
    student_portal.portal_page = enhanced_portal_page
    google_hub_safe.portal_page = enhanced_portal_page

    admin_portal.unified_page = enhanced_admin_page
    admin_console.page = enhanced_admin_page

    for module_name in (
        "app.admin_system",
        "app.unified_authoring",
        "app.innovation_hub",
        "app.course_workspace",
        "app.home_content",
        "app.role_management",
    ):
        try:
            module = __import__(module_name, fromlist=["page"])
            if hasattr(module, "page"):
                setattr(module, "page", enhanced_admin_page)
        except Exception:
            continue


def _register_course_assignment_routes(app: FastAPI) -> None:
    _remove_route(app, f"{PREFIX}/courses", "POST")
    _remove_route(app, f"{PREFIX}/courses/{{course_id}}/update", "POST")

    @app.post(f"{PREFIX}/courses", response_model=None)
    async def create_course_with_optional_admin_instructor(
        request: Request,
        course_code: str = Form(...),
        title: str = Form(...),
        description: str = Form(""),
        term: str = Form(""),
        instructor_email: str = Form(""),
        template: str = Form("blank"),
    ):
        admin = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        clean_title = title.strip()
        professor = instructor_email.strip().lower() or str(admin["email"]).strip().lower()
        if not code or not clean_title:
            raise HTTPException(400, "Course code and title are required.")

        with db() as conn:
            if rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE course_code=?", (code,))):
                raise HTTPException(409, "A course with this code already exists.")
            now = utcnow()
            course_id = academic_access._insert_course(
                conn,
                (code, clean_title, description.strip(), term.strip(), "draft", professor, admin["email"], now, now),
            )
            academic_access.assign_professor(conn, course_id, professor)
            if template != "blank":
                for position, (module_title, module_description, outcomes) in enumerate(
                    _template_modules(template, clean_title),
                    1,
                ):
                    execute(
                        conn,
                        """INSERT INTO nexus_modules
                           (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (course_id, module_title, module_description, outcomes, 60, position, "draft", now, now),
                    )
            audit(
                conn,
                admin["email"],
                "course_created_and_instructor_assigned",
                "course",
                str(course_id),
                professor,
                request.client.host if request.client else "",
            )
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)

    @app.post(f"{PREFIX}/courses/{{course_id}}/update", response_model=None)
    async def update_course_and_instructor(
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
        admin = require_admin(request, {"course_admin"})
        code = course_code.strip().upper()
        clean_title = title.strip()
        professor = instructor_email.strip().lower() or str(admin["email"]).strip().lower()
        if not code or not clean_title:
            raise HTTPException(400, "Course code and title are required.")
        if status not in academic_access.COURSE_STATES:
            raise HTTPException(400, "Invalid course status.")
        if start_date and end_date and start_date > end_date:
            raise HTTPException(400, "The end date cannot be earlier than the start date.")

        with db() as conn:
            course = academic_access._course(conn, course_id)
            duplicate = rows(
                execute(
                    conn,
                    "SELECT id FROM nexus_admin_courses WHERE course_code=? AND id<>?",
                    (code, course_id),
                )
            )
            if duplicate:
                raise HTTPException(409, "Another course already uses this code.")
            previous = str(course.get("instructor_email") or "").strip().lower()
            execute(
                conn,
                """UPDATE nexus_admin_courses
                   SET course_code=?,title=?,description=?,term=?,status=?,instructor_email=?,
                       start_date=?,end_date=?,updated_at=? WHERE id=?""",
                (
                    code,
                    clean_title,
                    description.strip(),
                    term.strip(),
                    status,
                    professor,
                    start_date.strip() or None,
                    end_date.strip() or None,
                    utcnow(),
                    course_id,
                ),
            )
            academic_access.assign_professor(conn, course_id, professor)
            if previous and previous != professor:
                execute(
                    conn,
                    """UPDATE nexus_admin_enrollments SET status='inactive'
                       WHERE course_id=? AND lower(user_email)=? AND course_role='instructor'""",
                    (course_id, previous),
                )
            audit(
                conn,
                admin["email"],
                "course_configuration_and_instructor_updated",
                "course",
                str(course_id),
                f"{code}:{professor}:{status}",
                request.client.host if request.client else "",
            )
        return RedirectResponse(f"{PREFIX}/courses/{course_id}", status_code=303)


def _register_bilingual_login(app: FastAPI) -> None:
    _remove_route(app, "/login", "GET")

    @app.get("/login", include_in_schema=False, response_class=HTMLResponse)
    async def bilingual_login() -> HTMLResponse:
        path = STATIC_DIR / "index.html"
        if not path.is_file():
            raise RuntimeError("NUVEDRA homepage was not found.")
        markup = path.read_text(encoding="utf-8")
        markup = markup.replace('<html lang="es">', '<html lang="en">', 1)
        if I18N_TAG not in markup:
            markup = markup.replace("</body>", f"{I18N_TAG}</body>", 1)
        return HTMLResponse(markup)


def register_platform_upgrade(app: FastAPI) -> None:
    if getattr(app.state, "nuvedra_platform_upgrade", False):
        return
    app.state.nuvedra_platform_upgrade = True
    _install_identity_resolution()
    _install_page_renderers()
    _register_course_assignment_routes(app)
    _register_bilingual_login(app)
    app.openapi_schema = None
    print(
        "NUVEDRA upgrade registered: English-first interface, Spanish switch, safe Google Hub, and administrator-instructor access.",
        flush=True,
    )
