from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_portal.py"

OLD_NAV = '''def _navigation() -> str:
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
'''

CURRENT_NAV = '''def _navigation(role: str) -> str:
    all_roles = {"superadmin", "course_admin", "user_admin", "support", "auditor"}
    links = (
        ("/admin", "Panel general", "Inicio y operaciones", all_roles),
        ("/admin/authoring", "Diseño académico", "Cursos, módulos y evaluación", {"superadmin", "course_admin"}),
        ("/admin/authoring/innovation", "Innovación IA/XR", "IA, RA, VR, 360 y calidad", {"superadmin", "course_admin"}),
        ("/admin/courses", "Gestión de cursos", "Estados y supervisión", {"superadmin", "course_admin"}),
        ("/admin/enrollments", "Matrículas", "Participantes y roles", {"superadmin", "course_admin"}),
        ("/admin/roles", "Roles y permisos", "Matriz y asignación de accesos", {"superadmin", "user_admin"}),
        ("/admin/users", "Usuarios", "Administradores y permisos", {"superadmin", "user_admin"}),
        ("/admin/audit", "Auditoría", "Trazabilidad institucional", {"superadmin", "auditor"}),
        ("/admin/backup", "Respaldos", "Exportación de datos", {"superadmin", "course_admin", "auditor"}),
        ("/admin/system", "Sistema", "Servicios y diagnóstico", all_roles),
    )
    return "".join(
        f'<a class="portal-link" href="{href}" data-route="{href}"><strong>{label}</strong><small>{description}</small></a>'
        for href, label, description, allowed in links
        if role in allowed
    )
'''

NEW_NAV = '''def _navigation(role: str) -> str:
    all_roles = {"superadmin", "course_admin", "user_admin", "support", "auditor"}
    links = (
        ("/admin", "Panel general", "Inicio y operaciones", all_roles),
        ("/admin/home-content", "Portada y anuncios", "Banners, avisos y programación", {"superadmin", "course_admin"}),
        ("/admin/authoring", "Diseño académico", "Cursos, módulos y evaluación", {"superadmin", "course_admin"}),
        ("/admin/authoring/innovation", "Innovación IA/XR", "IA, RA, VR, 360 y calidad", {"superadmin", "course_admin"}),
        ("/admin/courses", "Gestión de cursos", "Estados y supervisión", {"superadmin", "course_admin"}),
        ("/admin/enrollments", "Matrículas", "Participantes y roles", {"superadmin", "course_admin"}),
        ("/admin/roles", "Roles y permisos", "Matriz y asignación de accesos", {"superadmin", "user_admin"}),
        ("/admin/users", "Usuarios", "Administradores y permisos", {"superadmin", "user_admin"}),
        ("/admin/audit", "Auditoría", "Trazabilidad institucional", {"superadmin", "auditor"}),
        ("/admin/backup", "Respaldos", "Exportación de datos", {"superadmin", "course_admin", "auditor"}),
        ("/admin/system", "Sistema", "Servicios y diagnóstico", all_roles),
    )
    return "".join(
        f'<a class="portal-link" href="{href}" data-route="{href}"><strong>{label}</strong><small>{description}</small></a>'
        for href, label, description, allowed in links
        if role in allowed
    )
'''

OLD_CALL = "    nav = _navigation()\n"
NEW_CALL = '    nav = _navigation(str(user.get("role") or ""))\n'
OLD_PEOPLE = '<a class="button" href="/admin/users">Usuarios</a><a class="button" href="/admin/enrollments">Matrículas</a>'
NEW_PEOPLE = '<a class="button" href="/admin/roles">Roles</a><a class="button" href="/admin/users">Usuarios</a><a class="button" href="/admin/enrollments">Matrículas</a>'


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    changed = 0
    if NEW_NAV not in source:
        if CURRENT_NAV in source:
            source = source.replace(CURRENT_NAV, NEW_NAV, 1)
        elif OLD_NAV in source:
            source = source.replace(OLD_NAV, NEW_NAV, 1)
        else:
            raise RuntimeError("No se encontró una navegación compatible del portal integrado.")
        changed += 1
    if NEW_CALL not in source:
        if OLD_CALL not in source:
            raise RuntimeError("No se encontró la llamada original de navegación.")
        source = source.replace(OLD_CALL, NEW_CALL, 1)
        changed += 1
    if NEW_PEOPLE not in source:
        if OLD_PEOPLE not in source:
            raise RuntimeError("No se encontró el bloque de Personas y acceso.")
        source = source.replace(OLD_PEOPLE, NEW_PEOPLE, 1)
        changed += 1
    if '"/admin/home-content"' not in source:
        raise RuntimeError("La navegación administrativa no incorporó Portada y anuncios.")
    TARGET.write_text(source, encoding="utf-8")
    compile(source, str(TARGET), "exec")
    print(f"Portal integrado actualizado con navegación por roles y gestión de portada; cambios: {changed}.", flush=True)


if __name__ == "__main__":
    main()
