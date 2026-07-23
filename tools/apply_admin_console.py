from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "runtime_entry.py"
MARKER = "# NEXUS_ADMIN_CONSOLE_V2"


def main() -> None:
    if not ENTRY.exists():
        raise RuntimeError(f"No se encontró {ENTRY}")
    source = ENTRY.read_text(encoding="utf-8")
    if MARKER in source:
        print("La consola administrativa y el diseñador académico ya están registrados.")
        return
    addition = '''\n\n# NEXUS_ADMIN_CONSOLE_V2\nfrom app.admin_console import register_admin_console\nfrom app.admin_course_authoring import register_admin_course_authoring\nregister_admin_console(app)\nregister_admin_course_authoring(app)\n'''
    # Elimina el registro V1 si una reconstrucción anterior lo hubiera añadido.
    old = '''\n\n# NEXUS_ADMIN_CONSOLE_V1\nfrom app.admin_console import register_admin_console\nregister_admin_console(app)\n'''
    source = source.replace(old, "")
    ENTRY.write_text(source.rstrip() + addition, encoding="utf-8")
    print("Consola administrativa y diseñador académico NEXUS registrados correctamente.")


if __name__ == "__main__":
    main()
