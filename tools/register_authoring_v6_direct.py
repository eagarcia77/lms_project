from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "runtime_entry.py"
GOOGLE_API = ROOT / "app" / "google_api.py"
ADMIN_CONSOLE = ROOT / "app" / "admin_console.py"


def patch_runtime() -> None:
    source = ENTRY.read_text(encoding="utf-8")
    block = (
        "\n\n# NEXUS_AUTHORING_STUDIO_V6_DIRECT\n"
        "from app.admin_authoring_v6 import register_authoring_v6\n"
        "register_authoring_v6(app)\n"
    )
    if "# NEXUS_AUTHORING_STUDIO_V6_DIRECT" not in source:
        source = source.rstrip() + block
    ENTRY.write_text(source, encoding="utf-8")


def patch_google_scopes() -> None:
    source = GOOGLE_API.read_text(encoding="utf-8")
    anchor = '    "https://www.googleapis.com/auth/calendar.events",'
    scopes = (
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/presentations",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/forms.body",
    )
    additions = "\n".join(f'    "{scope}",' for scope in scopes if scope not in source)
    if additions:
        if anchor not in source:
            raise RuntimeError("No se encontró el punto de inserción de permisos de Google.")
        source = source.replace(anchor, anchor + "\n" + additions, 1)
    GOOGLE_API.write_text(source, encoding="utf-8")


def patch_navigation() -> None:
    source = ADMIN_CONSOLE.read_text(encoding="utf-8")
    needle = '<a href="/admin/courses">Cursos</a>'
    addition = needle + '<a href="/admin/authoring">Course Studio</a>'
    if addition not in source:
        if needle not in source:
            raise RuntimeError("No se encontró la navegación administrativa.")
        source = source.replace(needle, addition, 1)
    ADMIN_CONSOLE.write_text(source, encoding="utf-8")


def main() -> None:
    target = ROOT / "app" / "admin_authoring_v6.py"
    if not target.exists():
        raise RuntimeError("Falta app/admin_authoring_v6.py")
    compile(target.read_text(encoding="utf-8"), str(target), "exec")
    patch_runtime()
    patch_google_scopes()
    patch_navigation()
    print("Course Studio V6 registrado desde código fuente directo.")


if __name__ == "__main__":
    main()
