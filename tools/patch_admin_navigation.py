from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_console.py"

OLD = """<nav><a href=\"/admin\">Resumen</a><a href=\"/admin/courses\">Cursos</a><a href=\"/admin/users\">Usuarios</a><a href=\"/admin/enrollments\">Matrículas</a><a href=\"/admin/audit\">Auditoría</a><a href=\"/admin/backup\">Respaldo</a><a href=\"/admin/logout\">Salir</a></nav>"""
NEW = """<nav><a href=\"/admin\">Resumen</a><a href=\"/admin/authoring\">Diseño de cursos</a><a href=\"/admin/courses\">Cursos</a><a href=\"/admin/users\">Usuarios</a><a href=\"/admin/enrollments\">Matrículas</a><a href=\"/admin/audit\">Auditoría</a><a href=\"/admin/backup\">Respaldo</a><a href=\"/admin/system\">Sistema</a><a href=\"/admin/logout\">Salir</a></nav>"""


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    if NEW in source:
        print("La navegación administrativa ya está actualizada.")
        return
    if OLD not in source:
        raise RuntimeError("No se encontró la navegación administrativa esperada.")
    TARGET.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
    compile(TARGET.read_text(encoding="utf-8"), str(TARGET), "exec")
    print("Navegación administrativa unificada.")


if __name__ == "__main__":
    main()
