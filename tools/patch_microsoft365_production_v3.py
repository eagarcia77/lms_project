from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_production_v3_module.py.txt")
MODULE = Path("app/microsoft365_production_v3.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
EDUCATION_V2 = Path("app/microsoft365_education_v2.py")
TAG = "NUVEDRA_MICROSOFT365_PRODUCTION_V3"


def _normalize_source(source: str) -> str:
    # Keep the large template readable while avoiding a nested f-string expression in the SharePoint card renderer.
    start = source.find('        cards = "".join(')
    end = source.find('\n        writable =', start)
    if start < 0 or end < 0:
        raise RuntimeError("Microsoft 365 Production v3 could not locate the SharePoint card renderer.")
    replacement = '''        cards_list: list[str] = []
        for item in items:
            kind = "Folder" if item.get("folder") else "File"
            open_link = ""
            if item.get("webUrl"):
                safe_url = academic_access.esc(item.get("webUrl"), attr=True)
                open_link = f'<a class="studio-button studio-button--quiet" href="{safe_url}" target="_blank" rel="noopener noreferrer">Open in Microsoft 365</a>'
            cards_list.append(f'<article class="studio-panel"><p class="studio-eyebrow">{kind}</p><h3>{academic_access.esc(item.get("name"))}</h3>{open_link}</article>')
        cards = "".join(cards_list) or '<section class="studio-empty">No items found in the Team document library.</section>'
'''
    return source[:start] + replacement + source[end:]


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_production_v3 import register_microsoft365_production_v3\n"
    if import_line not in text:
        anchor = "from app.microsoft365_education_v2 import register_microsoft365_education_v2\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Production v3 requires Teams Education v2 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_production_v3(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_education_v2(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Production v3 could not locate the v2 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_v2_navigation() -> None:
    if not EDUCATION_V2.is_file():
        raise RuntimeError("Microsoft 365 Production v3 requires generated Teams Education v2.")
    text = EDUCATION_V2.read_text(encoding="utf-8")
    if TAG in text:
        return
    admin_old = '</div></header>{tenant_warning}<section class="studio-grid">'
    admin_new = '</div><div class="studio-actions"><a class="studio-button" href="/admin/microsoft365/production">Production v3</a></div></header><!-- NUVEDRA_MICROSOFT365_PRODUCTION_V3 -->{tenant_warning}<section class="studio-grid">'
    if admin_old not in text:
        raise RuntimeError("Microsoft 365 Production v3 could not locate the v2 admin navigation anchor.")
    text = text.replace(admin_old, admin_new, 1)
    course_old = '</div></header>{permission_note}<section class="studio-grid">'
    course_new = '</div><div class="studio-actions"><a class="studio-button" href="{STUDIO_PREFIX}/courses/{course_id}/microsoft365/production">Production v3</a></div></header>{permission_note}<section class="studio-grid">'
    if course_old not in text:
        raise RuntimeError("Microsoft 365 Production v3 could not locate the v2 course navigation anchor.")
    EDUCATION_V2.write_text(text.replace(course_old, course_new, 1), encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Production v3 source template is missing.")
    source = _normalize_source(SOURCE.read_text(encoding="utf-8"))
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_v2_navigation()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(EDUCATION_V2.read_text(encoding="utf-8"), str(EDUCATION_V2), "exec")
    print("NUVEDRA Microsoft 365 Production & Tenant Provisioning v3 installed: paginated Graph collections, granted-scope diagnostics, incremental additive roster synchronization, controlled Team creation, provisioning checks, and course SharePoint folders.", flush=True)


if __name__ == "__main__":
    main()
