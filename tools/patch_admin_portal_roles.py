from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_portal.py"

OLD_LINK = '        ("/admin/users", "Usuarios", "Administradores y permisos"),\n'
NEW_LINKS = (
    '        ("/admin/roles", "Roles y permisos", "Matriz y asignación de accesos"),\n'
    '        ("/admin/users", "Usuarios", "Administradores y permisos"),\n'
)
OLD_PEOPLE = '<a class="button" href="/admin/users">Usuarios</a><a class="button" href="/admin/enrollments">Matrículas</a>'
NEW_PEOPLE = '<a class="button" href="/admin/roles">Roles</a><a class="button" href="/admin/users">Usuarios</a><a class="button" href="/admin/enrollments">Matrículas</a>'


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    changed = 0
    if NEW_LINKS not in source:
        if OLD_LINK not in source:
            raise RuntimeError("No se encontró el enlace de Usuarios en el portal integrado.")
        source = source.replace(OLD_LINK, NEW_LINKS, 1)
        changed += 1
    if NEW_PEOPLE not in source:
        if OLD_PEOPLE not in source:
            raise RuntimeError("No se encontró el bloque de Personas y acceso.")
        source = source.replace(OLD_PEOPLE, NEW_PEOPLE, 1)
        changed += 1
    TARGET.write_text(source, encoding="utf-8")
    compile(source, str(TARGET), "exec")
    print(f"Portal integrado actualizado con gestión de roles; cambios: {changed}.", flush=True)


if __name__ == "__main__":
    main()
