from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_console.py"

OLD = """<nav><a href=\"/admin\">Resumen</a><a href=\"/admin/courses\">Cursos</a><a href=\"/admin/users\">Usuarios</a><a href=\"/admin/enrollments\">Matrículas</a><a href=\"/admin/audit\">Auditoría</a><a href=\"/admin/backup\">Respaldo</a><a href=\"/admin/logout\">Salir</a></nav>"""
CURRENT = """<nav><a href=\"/admin\">Resumen</a><a href=\"/admin/authoring\">Diseño de cursos</a><a href=\"/admin/courses\">Cursos</a><a href=\"/admin/users\">Usuarios</a><a href=\"/admin/enrollments\">Matrículas</a><a href=\"/admin/audit\">Auditoría</a><a href=\"/admin/backup\">Respaldo</a><a href=\"/admin/system\">Sistema</a><a href=\"/admin/logout\">Salir</a></nav>"""
NEW = """<nav><a href=\"/admin\">Resumen</a><a href=\"/admin/authoring\">Diseño de cursos</a><a href=\"/admin/authoring/innovation\">Innovación IA/XR</a><a href=\"/admin/courses\">Cursos</a><a href=\"/admin/users\">Usuarios</a><a href=\"/admin/enrollments\">Matrículas</a><a href=\"/admin/audit\">Auditoría</a><a href=\"/admin/backup\">Respaldo</a><a href=\"/admin/system\">Sistema</a><a href=\"/admin/logout\">Salir</a></nav>"""


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    if NEW in source:
        print("La navegación administrativa ya incluye Innovación IA/XR.")
        return
    if CURRENT in source:
        source = source.replace(CURRENT, NEW, 1)
    elif OLD in source:
        source = source.replace(OLD, NEW, 1)
    else:
        raise RuntimeError("No se encontró la navegación administrativa esperada.")
    TARGET.write_text(source, encoding="utf-8")
    compile(source, str(TARGET), "exec")
    print("Navegación administrativa unificada con Innovación IA/XR.")


if __name__ == "__main__":
    main()
