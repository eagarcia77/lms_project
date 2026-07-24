from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.admin_console as admin_console
from app.admin_console import (
    audit,
    db,
    execute,
    hash_password,
    require_admin,
    rows,
    utcnow,
)

PLATFORM_ROLES: dict[str, dict[str, Any]] = {
    "superadmin": {
        "label": "Superadministrador",
        "description": "Control total, seguridad, configuración y asignación de otros superadministradores.",
        "areas": "Todas las áreas",
    },
    "course_admin": {
        "label": "Administrador académico",
        "description": "Cursos, módulos, contenido, evaluación, innovación IA/XR, matrículas y respaldos.",
        "areas": "Diseño académico, IA/XR, cursos y matrículas",
    },
    "user_admin": {
        "label": "Administrador de usuarios",
        "description": "Crea cuentas administrativas, asigna roles no privilegiados y administra accesos.",
        "areas": "Usuarios, roles y permisos",
    },
    "support": {
        "label": "Soporte técnico",
        "description": "Apoyo operativo limitado sin capacidad para cambiar roles privilegiados.",
        "areas": "Soporte y diagnóstico autorizado",
    },
    "auditor": {
        "label": "Auditor",
        "description": "Consulta trazabilidad, respaldos y evidencia institucional sin modificar cursos.",
        "areas": "Auditoría, respaldos y diagnóstico",
    },
}

COURSE_ROLES: dict[str, str] = {
    "instructor": "Profesor o instructor",
    "teaching_assistant": "Asistente docente",
    "course_builder": "Diseñador o constructor del curso",
    "facilitator": "Facilitador",
    "student": "Estudiante",
    "observer": "Observador",
}


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def _replace_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def _user_by_id(conn: Any, user_id: int) -> dict[str, Any]:
    found = rows(
        execute(
            conn,
            "SELECT id,email,full_name,role,active,must_change_password,created_at,last_login FROM nexus_admin_users WHERE id=?",
            (user_id,),
        )
    )
    if not found:
        raise HTTPException(404, "Usuario administrativo no encontrado.")
    return found[0]


def _enrollment_by_id(conn: Any, enrollment_id: int) -> dict[str, Any]:
    found = rows(
        execute(
            conn,
            "SELECT id,course_id,user_email,course_role,status,created_at FROM nexus_admin_enrollments WHERE id=?",
            (enrollment_id,),
        )
    )
    if not found:
        raise HTTPException(404, "Matrícula no encontrada.")
    return found[0]


def _active_superadmins(conn: Any) -> int:
    result = rows(
        execute(
            conn,
            "SELECT COUNT(*) AS total FROM nexus_admin_users WHERE role='superadmin' AND active=1",
        )
    )
    return int(result[0].get("total") or 0) if result else 0


def _require_user_manager(request: Request) -> dict[str, Any]:
    return require_admin(request, {"user_admin"})


def _can_manage(actor: dict[str, Any], target: dict[str, Any]) -> bool:
    return actor.get("role") == "superadmin" or target.get("role") != "superadmin"


def _guard_privileged_change(
    conn: Any,
    actor: dict[str, Any],
    target: dict[str, Any],
    *,
    new_role: str | None = None,
    new_active: int | None = None,
) -> None:
    if not _can_manage(actor, target):
        raise HTTPException(403, "Solo un superadministrador puede modificar otro superadministrador.")
    if new_role == "superadmin" and actor.get("role") != "superadmin":
        raise HTTPException(403, "Solo un superadministrador puede asignar ese rol.")
    if target.get("email") == actor.get("email"):
        if new_role is not None and new_role != target.get("role"):
            raise HTTPException(400, "No puede cambiar su propio rol durante una sesión activa.")
        if new_active == 0:
            raise HTTPException(400, "No puede suspender su propia cuenta.")
    removes_superadmin = target.get("role") == "superadmin" and (
        (new_role is not None and new_role != "superadmin")
        or new_active == 0
    )
    if removes_superadmin and _active_superadmins(conn) <= 1:
        raise HTTPException(400, "Debe permanecer por lo menos un superadministrador activo.")


def _role_options(selected: str, actor_role: str) -> str:
    available = PLATFORM_ROLES.items()
    if actor_role != "superadmin":
        available = [(key, value) for key, value in available if key != "superadmin"]
    return "".join(
        f'<option value="{key}"{" selected" if key == selected else ""}>{_escape(info["label"])}</option>'
        for key, info in available
    )


def _course_role_options(selected: str = "student") -> str:
    return "".join(
        f'<option value="{key}"{" selected" if key == selected else ""}>{_escape(label)}</option>'
        for key, label in COURSE_ROLES.items()
    )


def register_role_management(app: FastAPI) -> None:
    for method in ("GET", "POST"):
        _replace_route(app, "/admin/users", method)
        _replace_route(app, "/admin/enrollments", method)

    @app.get("/admin/roles", response_class=HTMLResponse, response_model=None)
    async def roles_dashboard(request: Request):
        user = _require_user_manager(request)
        with db() as conn:
            platform_counts = rows(
                execute(
                    conn,
                    "SELECT role,COUNT(*) AS total,SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) AS active_total FROM nexus_admin_users GROUP BY role ORDER BY role",
                )
            )
            course_counts = rows(
                execute(
                    conn,
                    "SELECT course_role,COUNT(*) AS total FROM nexus_admin_enrollments GROUP BY course_role ORDER BY course_role",
                )
            )
        counts = {str(row["role"]): row for row in platform_counts}
        role_cards = "".join(
            f'''<section class="card"><h3>{_escape(info["label"])}</h3><p>{_escape(info["description"])}</p><p><strong>Áreas:</strong> {_escape(info["areas"])}</p><p><span class="badge">{int(counts.get(key, {}).get("total") or 0)} cuentas</span> <span class="badge">{int(counts.get(key, {}).get("active_total") or 0)} activas</span></p></section>'''
            for key, info in PLATFORM_ROLES.items()
        )
        course_rows = "".join(
            f'<tr><td>{_escape(COURSE_ROLES.get(str(row["course_role"]), row["course_role"]))}</td><td>{int(row.get("total") or 0)}</td></tr>'
            for row in course_counts
        ) or '<tr><td colspan="2">Todavía no hay roles asignados en cursos.</td></tr>'
        matrix_rows = "".join(
            f'<tr><td><strong>{_escape(info["label"])}</strong><br><small>{_escape(key)}</small></td><td>{_escape(info["areas"])}</td><td>{_escape(info["description"])}</td></tr>'
            for key, info in PLATFORM_ROLES.items()
        )
        body = f'''
        <h2>Roles y permisos</h2>
        <p>Los roles de plataforma controlan la administración general. Los roles de curso se asignan por matrícula y pueden ser diferentes para la misma persona en cursos distintos.</p>
        <p><a class="button" href="/admin/users">Administrar cuentas</a><a class="button secondary" href="/admin/enrollments">Asignar roles de curso</a></p>
        <div class="grid">{role_cards}</div>
        <section class="card"><h3>Matriz de permisos de plataforma</h3><table><thead><tr><th>Rol</th><th>Áreas principales</th><th>Alcance</th></tr></thead><tbody>{matrix_rows}</tbody></table></section>
        <section class="card"><h3>Distribución de roles dentro de cursos</h3><table><thead><tr><th>Rol de curso</th><th>Asignaciones</th></tr></thead><tbody>{course_rows}</tbody></table></section>
        <p class="notice">Protección activa: no se puede suspender o degradar al último superadministrador activo.</p>
        '''
        return admin_console.page("Roles y permisos", body, user)

    @app.get("/admin/users", response_class=HTMLResponse, response_model=None)
    async def users_page(request: Request):
        actor = _require_user_manager(request)
        with db() as conn:
            users = rows(
                execute(
                    conn,
                    """SELECT u.id,u.email,u.full_name,u.role,u.active,u.must_change_password,u.created_at,u.last_login,
                    (SELECT COUNT(*) FROM nexus_admin_enrollments e WHERE e.user_email=u.email) AS course_roles
                    FROM nexus_admin_users u ORDER BY u.active DESC,u.full_name,u.email""",
                )
            )
        create_role_options = _role_options("course_admin", str(actor.get("role")))
        user_rows: list[str] = []
        for target in users:
            manageable = _can_manage(actor, target)
            role_form = ""
            status_form = ""
            reset_form = ""
            if manageable:
                role_form = f'''<form method="post" action="/admin/users/{target["id"]}/role"><label>Rol de plataforma<select name="role">{_role_options(str(target["role"]), str(actor.get("role")))}</select></label><button>Guardar rol</button></form>'''
                status_label = "Suspender" if int(target.get("active") or 0) else "Activar"
                status_value = 0 if int(target.get("active") or 0) else 1
                status_form = f'''<form method="post" action="/admin/users/{target["id"]}/status"><input type="hidden" name="active" value="{status_value}"><button class="{"danger" if status_value == 0 else ""}">{status_label}</button></form>'''
                reset_form = f'''<form method="post" action="/admin/users/{target["id"]}/force-password-reset"><button>Exigir cambio de contraseña</button></form>'''
            else:
                role_form = '<p class="notice">Solo otro superadministrador puede modificar esta cuenta.</p>'
            user_rows.append(
                f'''<tr><td><strong>{_escape(target["full_name"])}</strong><br>{_escape(target["email"])}</td><td><span class="badge">{_escape(PLATFORM_ROLES.get(str(target["role"]), {}).get("label", target["role"]))}</span><br>{"Activa" if int(target.get("active") or 0) else "Suspendida"}<br>{"Cambio de contraseña pendiente" if int(target.get("must_change_password") or 0) else "Contraseña confirmada"}</td><td>{int(target.get("course_roles") or 0)} roles de curso<br><small>Último acceso: {_escape(target.get("last_login") or "Nunca")}</small></td><td>{role_form}{status_form}{reset_form}</td></tr>'''
            )
        body = f'''
        <h2>Usuarios, roles y acceso</h2>
        <p>Las cuentas de esta sección administran la plataforma. Los estudiantes y profesores que entran con Google reciben sus funciones mediante las matrículas de curso.</p>
        <p><a class="button secondary" href="/admin/roles">Ver matriz de roles</a><a class="button" href="/admin/enrollments">Roles dentro de cursos</a></p>
        <div class="grid">
          <section class="card"><h3>Crear cuenta administrativa</h3><form method="post" action="/admin/users"><label>Nombre completo<input name="full_name" required maxlength="160"></label><label>Correo electrónico<input type="email" name="email" required></label><label>Rol<select name="role">{create_role_options}</select></label><label>Contraseña temporal<input type="password" name="password" minlength="12" required></label><button>Crear cuenta</button></form></section>
          <section class="card"><h3>Controles de seguridad</h3><p>Cada cuenta nueva debe cambiar la contraseña temporal. Los cambios de rol, suspensión, reactivación y restablecimiento quedan registrados en Auditoría.</p></section>
        </div>
        <section class="card"><table><thead><tr><th>Usuario</th><th>Acceso</th><th>Participación</th><th>Administrar</th></tr></thead><tbody>{"".join(user_rows)}</tbody></table></section>
        '''
        return admin_console.page("Usuarios y roles", body, actor)

    @app.post("/admin/users", response_model=None)
    async def create_user(
        request: Request,
        full_name: str = Form(...),
        email: str = Form(...),
        role: str = Form(...),
        password: str = Form(...),
    ):
        actor = _require_user_manager(request)
        if role not in PLATFORM_ROLES:
            raise HTTPException(400, "Rol de plataforma inválido.")
        if role == "superadmin" and actor.get("role") != "superadmin":
            raise HTTPException(403, "Solo un superadministrador puede crear otro superadministrador.")
        if len(password) < 12:
            raise HTTPException(400, "La contraseña temporal debe tener 12 caracteres o más.")
        normalized = email.strip().lower()
        if not normalized or not full_name.strip():
            raise HTTPException(400, "Nombre y correo electrónico son obligatorios.")
        with db() as conn:
            existing = rows(execute(conn, "SELECT id FROM nexus_admin_users WHERE email=?", (normalized,)))
            if existing:
                raise HTTPException(409, "Ya existe una cuenta administrativa con ese correo.")
            execute(
                conn,
                "INSERT INTO nexus_admin_users (email,full_name,password_hash,role,active,must_change_password,created_at) VALUES (?,?,?,?,?,?,?)",
                (normalized, full_name.strip(), hash_password(password), role, 1, 1, utcnow()),
            )
            audit(conn, actor["email"], "admin_user_created", "admin_user", normalized, role, request.client.host if request.client else "")
        return RedirectResponse("/admin/users", status_code=303)

    @app.post("/admin/users/{user_id}/role", response_model=None)
    async def update_user_role(user_id: int, request: Request, role: str = Form(...)):
        actor = _require_user_manager(request)
        if role not in PLATFORM_ROLES:
            raise HTTPException(400, "Rol de plataforma inválido.")
        with db() as conn:
            target = _user_by_id(conn, user_id)
            _guard_privileged_change(conn, actor, target, new_role=role)
            execute(conn, "UPDATE nexus_admin_users SET role=? WHERE id=?", (role, user_id))
            audit(conn, actor["email"], "admin_role_changed", "admin_user", str(user_id), f"{target['role']}->{role}", request.client.host if request.client else "")
        return RedirectResponse("/admin/users", status_code=303)

    @app.post("/admin/users/{user_id}/status", response_model=None)
    async def update_user_status(user_id: int, request: Request, active: int = Form(...)):
        actor = _require_user_manager(request)
        if active not in {0, 1}:
            raise HTTPException(400, "Estado de usuario inválido.")
        with db() as conn:
            target = _user_by_id(conn, user_id)
            _guard_privileged_change(conn, actor, target, new_active=active)
            execute(conn, "UPDATE nexus_admin_users SET active=? WHERE id=?", (active, user_id))
            audit(conn, actor["email"], "admin_user_status_changed", "admin_user", str(user_id), "active" if active else "suspended", request.client.host if request.client else "")
        return RedirectResponse("/admin/users", status_code=303)

    @app.post("/admin/users/{user_id}/force-password-reset", response_model=None)
    async def force_password_reset(user_id: int, request: Request):
        actor = _require_user_manager(request)
        with db() as conn:
            target = _user_by_id(conn, user_id)
            if not _can_manage(actor, target):
                raise HTTPException(403, "Solo un superadministrador puede modificar otro superadministrador.")
            execute(conn, "UPDATE nexus_admin_users SET must_change_password=1 WHERE id=?", (user_id,))
            audit(conn, actor["email"], "admin_password_reset_required", "admin_user", str(user_id), target["email"], request.client.host if request.client else "")
        return RedirectResponse("/admin/users", status_code=303)

    @app.get("/admin/enrollments", response_class=HTMLResponse, response_model=None)
    async def enrollments_page(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT id,course_code,title FROM nexus_admin_courses ORDER BY title,course_code"))
            enrollments = rows(
                execute(
                    conn,
                    """SELECT e.id,e.course_id,e.user_email,e.course_role,e.status,e.created_at,c.course_code,c.title
                    FROM nexus_admin_enrollments e JOIN nexus_admin_courses c ON c.id=e.course_id
                    ORDER BY c.title,e.user_email""",
                )
            )
        course_options = "".join(
            f'<option value="{course["id"]}">{_escape(course["course_code"])} · {_escape(course["title"])}</option>'
            for course in courses
        )
        enrollment_rows = "".join(
            f'''<tr><td><strong>{_escape(item["course_code"])}</strong><br>{_escape(item["title"])}</td><td>{_escape(item["user_email"])}</td><td><form method="post" action="/admin/enrollments/{item["id"]}/role"><select name="course_role">{_course_role_options(str(item["course_role"]))}</select><button>Guardar rol</button></form></td><td><span class="badge">{_escape(item["status"])}</span><form method="post" action="/admin/enrollments/{item["id"]}/status"><input type="hidden" name="status" value="{"inactive" if item["status"] == "active" else "active"}"><button>{"Suspender" if item["status"] == "active" else "Activar"}</button></form></td><td><form method="post" action="/admin/enrollments/{item["id"]}/delete"><button class="danger">Retirar del curso</button></form></td></tr>'''
            for item in enrollments
        ) or '<tr><td colspan="5">Todavía no hay matrículas.</td></tr>'
        body = f'''
        <h2>Matrículas y roles de curso</h2>
        <p>Una persona puede tener funciones diferentes en cursos distintos. Por ejemplo, puede ser instructor en un curso y estudiante u observador en otro.</p>
        <p><a class="button secondary" href="/admin/roles">Matriz de roles</a><a class="button" href="/admin/users">Cuentas administrativas</a></p>
        <section class="card"><h3>Asignar o actualizar un rol de curso</h3><form method="post" action="/admin/enrollments"><label>Curso<select name="course_id" required>{course_options}</select></label><label>Correo del usuario<input type="email" name="user_email" required></label><label>Rol de curso<select name="course_role">{_course_role_options()}</select></label><button>Asignar rol</button></form></section>
        <section class="card"><table><thead><tr><th>Curso</th><th>Usuario</th><th>Rol</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{enrollment_rows}</tbody></table></section>
        '''
        return admin_console.page("Matrículas y roles", body, user)

    @app.post("/admin/enrollments", response_model=None)
    async def create_or_update_enrollment(
        request: Request,
        course_id: int = Form(...),
        user_email: str = Form(...),
        course_role: str = Form("student"),
    ):
        actor = require_admin(request, {"course_admin"})
        if course_role not in COURSE_ROLES:
            raise HTTPException(400, "Rol de curso inválido.")
        normalized = user_email.strip().lower()
        if not normalized:
            raise HTTPException(400, "El correo electrónico es obligatorio.")
        with db() as conn:
            course = rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE id=?", (course_id,)))
            if not course:
                raise HTTPException(404, "Curso no encontrado.")
            existing = rows(
                execute(
                    conn,
                    "SELECT id,course_role FROM nexus_admin_enrollments WHERE course_id=? AND user_email=?",
                    (course_id, normalized),
                )
            )
            if existing:
                execute(
                    conn,
                    "UPDATE nexus_admin_enrollments SET course_role=?,status='active' WHERE id=?",
                    (course_role, existing[0]["id"]),
                )
                action = "course_role_reassigned"
                entity_id = str(existing[0]["id"])
                details = f"{existing[0]['course_role']}->{course_role}:{normalized}"
            else:
                execute(
                    conn,
                    "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                    (course_id, normalized, course_role, "active", utcnow()),
                )
                action = "enrollment_created"
                entity_id = str(course_id)
                details = f"{normalized}:{course_role}"
            audit(conn, actor["email"], action, "course_enrollment", entity_id, details, request.client.host if request.client else "")
        return RedirectResponse("/admin/enrollments", status_code=303)

    @app.post("/admin/enrollments/{enrollment_id}/role", response_model=None)
    async def update_course_role(enrollment_id: int, request: Request, course_role: str = Form(...)):
        actor = require_admin(request, {"course_admin"})
        if course_role not in COURSE_ROLES:
            raise HTTPException(400, "Rol de curso inválido.")
        with db() as conn:
            enrollment = _enrollment_by_id(conn, enrollment_id)
            execute(conn, "UPDATE nexus_admin_enrollments SET course_role=? WHERE id=?", (course_role, enrollment_id))
            audit(conn, actor["email"], "course_role_changed", "course_enrollment", str(enrollment_id), f"{enrollment['course_role']}->{course_role}", request.client.host if request.client else "")
        return RedirectResponse("/admin/enrollments", status_code=303)

    @app.post("/admin/enrollments/{enrollment_id}/status", response_model=None)
    async def update_enrollment_status(enrollment_id: int, request: Request, status: str = Form(...)):
        actor = require_admin(request, {"course_admin"})
        if status not in {"active", "inactive"}:
            raise HTTPException(400, "Estado de matrícula inválido.")
        with db() as conn:
            _enrollment_by_id(conn, enrollment_id)
            execute(conn, "UPDATE nexus_admin_enrollments SET status=? WHERE id=?", (status, enrollment_id))
            audit(conn, actor["email"], "enrollment_status_changed", "course_enrollment", str(enrollment_id), status, request.client.host if request.client else "")
        return RedirectResponse("/admin/enrollments", status_code=303)

    @app.post("/admin/enrollments/{enrollment_id}/delete", response_model=None)
    async def delete_enrollment(enrollment_id: int, request: Request):
        actor = require_admin(request, {"course_admin"})
        with db() as conn:
            enrollment = _enrollment_by_id(conn, enrollment_id)
            execute(conn, "DELETE FROM nexus_admin_enrollments WHERE id=?", (enrollment_id,))
            audit(conn, actor["email"], "enrollment_removed", "course_enrollment", str(enrollment_id), f"{enrollment['user_email']}:{enrollment['course_role']}", request.client.host if request.client else "")
        return RedirectResponse("/admin/enrollments", status_code=303)

    print("Gestión segura de roles de plataforma y curso registrada.", flush=True)
