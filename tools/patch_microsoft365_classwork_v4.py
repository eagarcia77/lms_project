from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_classwork_v4_module.py.txt")
MODULE = Path("app/microsoft365_classwork_v4.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
PRODUCTION_V3 = Path("app/microsoft365_production_v3.py")
ASSIGNMENTS = Path("app/assignments_submissions.py")
TAG = "NUVEDRA_MICROSOFT365_CLASSWORK_V4"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_classwork_v4 import register_microsoft365_classwork_v4\n"
    if import_line not in text:
        anchor = "from app.microsoft365_production_v3 import register_microsoft365_production_v3\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Classwork v4 requires Production v3 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_classwork_v4(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_production_v3(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Classwork v4 could not locate the v3 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_production_navigation() -> None:
    if not PRODUCTION_V3.is_file():
        raise RuntimeError("Microsoft 365 Classwork v4 requires generated Production v3.")
    text = PRODUCTION_V3.read_text(encoding="utf-8")
    if TAG in text:
        return
    old = "Production-safe pagination, actual granted-scope diagnostics, incremental non-destructive membership synchronization, controlled Team creation, and the Team-associated SharePoint document library.</p></div></header><section class=\"studio-grid\">"
    new = "Production-safe pagination, actual granted-scope diagnostics, incremental non-destructive membership synchronization, controlled Team creation, and the Team-associated SharePoint document library.</p></div><div class=\"studio-actions\"><a class=\"studio-button\" href=\"{STUDIO_PREFIX}/courses/{course_id}/microsoft365/classwork\">Classwork v4</a></div></header><!-- NUVEDRA_MICROSOFT365_CLASSWORK_V4 --><section class=\"studio-grid\">"
    if old not in text:
        raise RuntimeError("Microsoft 365 Classwork v4 could not locate the Production v3 course hero anchor.")
    PRODUCTION_V3.write_text(text.replace(old, new, 1), encoding="utf-8")


def _inject_header_action(text: str, testid: str, action_html: str, marker: str) -> str:
    """Insert a navigation action into a specific page hero without brittle full-HTML anchors."""
    page_anchor = f'data-testid="{testid}"'
    page_index = text.find(page_anchor)
    if page_index < 0:
        raise RuntimeError(f"Microsoft 365 Classwork v4 could not locate page {testid!r}.")
    header_index = text.find("<header", page_index)
    if header_index < 0:
        raise RuntimeError(f"Microsoft 365 Classwork v4 could not locate the hero header for {testid!r}.")
    header_end = text.find("</header>", header_index)
    if header_end < 0:
        raise RuntimeError(f"Microsoft 365 Classwork v4 could not locate the hero header boundary for {testid!r}.")
    if marker in text[header_index:header_end]:
        return text

    actions_anchor = '<div class="studio-actions">'
    actions_index = text.find(actions_anchor, header_index, header_end)
    tagged_action = f'<!-- {marker} -->' + action_html
    if actions_index >= 0:
        insert_at = actions_index + len(actions_anchor)
        return text[:insert_at] + tagged_action + text[insert_at:]

    actions = f'<div class="studio-actions">{tagged_action}</div>'
    return text[:header_end] + actions + text[header_end:]


def patch_assignment_navigation() -> None:
    if not ASSIGNMENTS.is_file():
        raise RuntimeError("Microsoft 365 Classwork v4 requires generated Assignments & Submissions v2.")
    text = ASSIGNMENTS.read_text(encoding="utf-8")

    text = _inject_header_action(
        text,
        "student-assignment-v2",
        '<a class="studio-button studio-button--quiet" href="/learn/assignments/{item_id}/microsoft365">Microsoft 365 work</a>',
        "NUVEDRA_MICROSOFT365_CLASSWORK_V4_STUDENT",
    )
    text = _inject_header_action(
        text,
        "course-assignments-v2",
        '<a class="studio-button" href="{STUDIO_PREFIX}/courses/{course_id}/microsoft365/classwork">Microsoft 365 Classwork</a>',
        "NUVEDRA_MICROSOFT365_CLASSWORK_V4_COURSE",
    )
    text = _inject_header_action(
        text,
        "assignment-submission-inbox-v2",
        '<a class="studio-button" href="{STUDIO_PREFIX}/assignments/{item_id}/microsoft365">Microsoft 365 setup</a>',
        "NUVEDRA_MICROSOFT365_CLASSWORK_V4_INBOX",
    )
    ASSIGNMENTS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Classwork v4 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_production_navigation()
    patch_assignment_navigation()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(PRODUCTION_V3.read_text(encoding="utf-8"), str(PRODUCTION_V3), "exec")
    compile(ASSIGNMENTS.read_text(encoding="utf-8"), str(ASSIGNMENTS), "exec")
    print("NUVEDRA Microsoft 365 Classwork & Assignments v4 installed: Microsoft templates, validated student work links, canonical assignment turn-in, metadata snapshots, and Gradebook linkage.", flush=True)


if __name__ == "__main__":
    main()
