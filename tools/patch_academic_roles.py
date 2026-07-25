from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE_FILE = ROOT / "app" / "role_management.py"
ADMIN_FILE = ROOT / "app" / "admin_console.py"
PORTAL_FILE = ROOT / "app" / "admin_portal.py"
SCRIPT_FILE = ROOT / "app" / "static" / "app.js"


def replace_once(source: str, old: str, new: str, label: str) -> tuple[str, int]:
    if new in source:
        return source, 0
    if old not in source:
        raise RuntimeError(f"No se encontró el bloque requerido para {label}.")
    return source.replace(old, new, 1), 1


def patch_roles() -> int:
    source = ROLE_FILE.read_text(encoding="utf-8")
    changes = 0
    old = '''    "auditor": {
        "label": "Auditor",
        "description": "Consulta trazabilidad, respaldos y evidencia institucional sin modificar cursos.",
        "areas": "Auditoría, respaldos y diagnóstico",
    },
}'''
    new = '''    "auditor": {
        "label": "Auditor",
        "description": "Consulta trazabilidad, respaldos y evidencia institucional sin modificar cursos.",
        "areas": "Auditoría, respaldos y diagnóstico",
    },
    "instructor": {
        "label": "Instructor",
        "description": "Imparte cursos, desarrolla contenido, facilita actividades y evalúa a sus estudiantes en los cursos asignados.",
        "areas": "Cursos asignados, módulos, contenido, evaluación y comunicación académica",
    },
    "student": {
        "label": "Estudiante",
        "description": "Accede a los cursos matriculados, contenido, actividades, foros, evaluaciones y experiencias inmersivas.",
        "areas": "Cursos matriculados, aprendizaje, entregas, foros y calificaciones",
    },
}'''
    source, count = replace_once(source, old, new, "roles académicos")
    changes += count

    substitutions = {
        'raise HTTPException(404, "Usuario administrativo no encontrado.")': 'raise HTTPException(404, "Usuario de la plataforma no encontrado.")',
        'create_role_options = _role_options("course_admin", str(actor.get("role")))': 'create_role_options = _role_options("student", str(actor.get("role")))',
        '<p>Los roles de plataforma controlan la administración general. Los roles de curso se asignan por matrícula y pueden ser diferentes para la misma persona en cursos distintos.</p>': '<p>Los roles de plataforma incluyen perfiles administrativos y académicos. Instructor y Estudiante no reciben acceso administrativo; sus permisos académicos se complementan con el rol asignado en cada matrícula.</p>',
        '<p>Las cuentas de esta sección administran la plataforma. Los estudiantes y profesores que entran con Google reciben sus funciones mediante las matrículas de curso.</p>': '<p>Esta sección reúne todas las cuentas institucionales. Los roles Instructor y Estudiante utilizan la plataforma académica y nunca reciben acceso a la consola administrativa por ese rol.</p>',
        '<section class="card"><h3>Crear cuenta administrativa</h3>': '<section class="card"><h3>Crear cuenta institucional</h3>',
        'Ya existe una cuenta administrativa con ese correo.': 'Ya existe una cuenta institucional con ese correo.',
        'return admin_console.page("Usuarios y roles", body, actor)': 'return admin_console.page("Usuarios institucionales y roles", body, actor)',
    }
    for old_text, new_text in substitutions.items():
        if new_text not in source:
            if old_text not in source:
                raise RuntimeError(f"No se encontró texto requerido en role_management.py: {old_text[:70]}")
            source = source.replace(old_text, new_text, 1)
            changes += 1

    ROLE_FILE.write_text(source, encoding="utf-8")
    return changes


def patch_admin_security() -> int:
    source = ADMIN_FILE.read_text(encoding="utf-8")
    changes = 0
    old_require = '''def require_admin(request: Request, allowed: set[str] | None = None) -> dict[str, Any]:
    user = session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Autenticación requerida")
    if allowed and user["role"] not in allowed and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Permiso insuficiente")
    return user'''
    new_require = '''def require_admin(request: Request, allowed: set[str] | None = None) -> dict[str, Any]:
    user = session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Autenticación requerida")
    if str(user.get("role") or "") not in ROLES:
        raise HTTPException(status_code=403, detail="Esta cuenta no tiene un rol administrativo.")
    if allowed and user["role"] not in allowed and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Permiso insuficiente")
    return user'''
    source, count = replace_once(source, old_require, new_require, "protección de require_admin")
    changes += count

    old_login = 'if not found or not found[0]["active"] or not verify_password(password, found[0]["password_hash"]):'
    new_login = 'if not found or not found[0]["active"] or str(found[0].get("role") or "") not in ROLES or not verify_password(password, found[0]["password_hash"]):'
    source, count = replace_once(source, old_login, new_login, "bloqueo de acceso administrativo académico")
    changes += count

    ADMIN_FILE.write_text(source, encoding="utf-8")
    return changes


def patch_portal() -> int:
    source = PORTAL_FILE.read_text(encoding="utf-8")
    changes = 0

    desired_nav = '("/admin/users", "Usuarios", "Administradores, instructores y estudiantes", {"superadmin", "user_admin"}),' 
    if desired_nav not in source:
        alternatives = (
            '("/admin/users", "Usuarios", "Administradores y permisos", {"superadmin", "user_admin"}),',
            '("/admin/users", "Usuarios", "Administradores y permisos"),',
        )
        for old_nav in alternatives:
            if old_nav in source:
                source = source.replace(old_nav, desired_nav, 1)
                changes += 1
                break
        else:
            raise RuntimeError("No se encontró el enlace de Usuarios en la navegación del portal.")

    replacements = {
        '"admins": _count(conn, "nexus_admin_users", "active=1"),': '"admins": _count(conn, "nexus_admin_users", "active=1 AND role IN (\'superadmin\',\'course_admin\',\'user_admin\',\'support\',\'auditor\')"),\n                "instructors": _count(conn, "nexus_admin_users", "active=1 AND role=\'instructor\'"),\n                "students": _count(conn, "nexus_admin_users", "active=1 AND role=\'student\'"),',
        '<div class="card metric"><strong>{metrics["admins"]}</strong>Administradores activos</div>': '<div class="card metric"><strong>{metrics["admins"]}</strong>Administradores activos</div>\n          <div class="card metric"><strong>{metrics["instructors"]}</strong>Instructores activos</div>\n          <div class="card metric"><strong>{metrics["students"]}</strong>Estudiantes activos</div>',
    }
    for old, new in replacements.items():
        if new not in source:
            if old not in source:
                raise RuntimeError(f"No se encontró el bloque del portal: {old[:70]}")
            source = source.replace(old, new, 1)
            changes += 1
    PORTAL_FILE.write_text(source, encoding="utf-8")
    return changes


def patch_profile() -> int:
    source = SCRIPT_FILE.read_text(encoding="utf-8")
    desired_statement = '$('.replace("'", '"') + '".profile-text small").textContent = state.me.platformRoleLabel || "Cuenta conectada";'
    # Keep the literal easy to validate and avoid depending on the previous label.
    desired_statement = '$(".profile-text small").textContent = state.me.platformRoleLabel || "Cuenta conectada";'
    if desired_statement in source:
        return 0

    # Replace any existing assignment to the profile subtitle, regardless of its
    # current wording or indentation.
    subtitle_pattern = re.compile(
        r'(?m)^(?P<indent>\s*)\$\(["\']\.profile-text small["\']\)\.textContent\s*=\s*[^;]+;\s*$'
    )
    match = subtitle_pattern.search(source)
    if match:
        indent = match.group("indent")
        source = subtitle_pattern.sub(indent + desired_statement, source, count=1)
        SCRIPT_FILE.write_text(source, encoding="utf-8")
        return 1

    # Some generated frontends omit the subtitle assignment. Insert it directly
    # after the profile name is populated, preserving the existing indentation.
    name_pattern = re.compile(
        r'(?m)^(?P<indent>\s*)\$\(["\']\.profile-text strong["\']\)\.textContent\s*=\s*[^;]+;\s*$'
    )
    name_match = name_pattern.search(source)
    if name_match:
        indent = name_match.group("indent")
        insertion = name_match.group(0) + "\n" + indent + desired_statement
        source = source[: name_match.start()] + insertion + source[name_match.end() :]
        SCRIPT_FILE.write_text(source, encoding="utf-8")
        return 1

    raise RuntimeError(
        "No se encontró un punto seguro del perfil para mostrar el rol académico. "
        "Se esperaba una asignación a .profile-text small o .profile-text strong."
    )


def validate() -> None:
    roles = ROLE_FILE.read_text(encoding="utf-8")
    admin = ADMIN_FILE.read_text(encoding="utf-8")
    portal = PORTAL_FILE.read_text(encoding="utf-8")
    script = SCRIPT_FILE.read_text(encoding="utf-8")
    required = {
        "role_management.py": ('"instructor": {', '"student": {', '"label": "Instructor"', '"label": "Estudiante"'),
        "admin_console.py": ('Esta cuenta no tiene un rol administrativo.', 'not in ROLES'),
        "admin_portal.py": ('Instructores activos', 'Estudiantes activos', 'Administradores, instructores y estudiantes'),
        "app.js": ('state.me.platformRoleLabel',),
    }
    content = {
        "role_management.py": roles,
        "admin_console.py": admin,
        "admin_portal.py": portal,
        "app.js": script,
    }
    missing = {
        name: [marker for marker in markers if marker not in content[name]]
        for name, markers in required.items()
    }
    missing = {name: values for name, values in missing.items() if values}
    if missing:
        raise RuntimeError(f"Integración de roles académicos incompleta: {missing}")


def main() -> None:
    changes = patch_roles() + patch_admin_security() + patch_portal() + patch_profile()
    validate()
    print(f"Roles institucionales Instructor y Estudiante incorporados; cambios: {changes}.", flush=True)


if __name__ == "__main__":
    main()
