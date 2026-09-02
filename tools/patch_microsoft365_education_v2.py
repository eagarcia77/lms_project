from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_education_v2_module.py.txt")
MODULE = Path("app/microsoft365_education_v2.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
MICROSOFT365 = Path("app/microsoft365_integration.py")
TAG = "NUVEDRA_MICROSOFT365_EDUCATION_V2"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_education_v2 import register_microsoft365_education_v2\n"
    if import_line not in text:
        anchor = "from app.microsoft365_integration import register_microsoft365_integration\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Education v2 requires Microsoft 365 Integration v1 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_education_v2(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_integration(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Education v2 could not locate the v1 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_microsoft365_workspace() -> None:
    if not MICROSOFT365.is_file():
        raise RuntimeError("Microsoft 365 Education v2 requires generated Microsoft 365 Integration v1.")
    text = MICROSOFT365.read_text(encoding="utf-8")
    if TAG in text:
        return
    old = '</div></header>{config_note}<section class="studio-grid">{_connection_panel(connection, next_path)}'
    new = '</div><div class="studio-actions"><a class="studio-button" href="{STUDIO_PREFIX}/courses/{course_id}/microsoft365/education" data-microsoft365-education-v2="true">Institutional Teams</a></div></header><!-- NUVEDRA_MICROSOFT365_EDUCATION_V2 -->{config_note}<section class="studio-grid">{_connection_panel(connection, next_path)}'
    if old not in text:
        raise RuntimeError("Microsoft 365 Education v2 could not locate the Microsoft 365 workspace hero anchor.")
    MICROSOFT365.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Education v2 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_microsoft365_workspace()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(MICROSOFT365.read_text(encoding="utf-8"), str(MICROSOFT365), "exec")
    print("NUVEDRA Microsoft 365 Institutional Setup & Teams Education v2 installed: admin readiness diagnostics, course Team linking, additive roster synchronization, channels, student access, and audit history.", flush=True)


if __name__ == "__main__":
    main()
