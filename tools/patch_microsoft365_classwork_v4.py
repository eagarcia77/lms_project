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


def _patch_student_assignment_action(text: str) -> str:
    """Add Microsoft 365 work to the assignment hero without assuming prior hero buttons."""
    if "NUVEDRA_MICROSOFT365_CLASSWORK_V4_ASSIGNMENT" in text:
        return text

    root_marker = 'data-testid="student-assignment-v2"'
    root_index = text.find(root_marker)
    if root_index < 0:
        raise RuntimeError("Microsoft 365 Classwork v4 could not locate the student assignment view.")

    header_start = text.find('<header class="studio-hero', root_index)
    if header_start < 0:
        raise RuntimeError("Microsoft 365 Classwork v4 could not locate the student assignment hero.")
    header_end = text.find("</header>", header_start)
    if header_end < 0:
        raise RuntimeError("Microsoft 365 Classwork v4 could not locate the end of the student assignment hero.")

    action = '<a class="studio-button studio-button--quiet" href="/learn/assignments/{item_id}/microsoft365">Microsoft 365 work</a><!-- NUVEDRA_MICROSOFT365_CLASSWORK_V4_ASSIGNMENT -->'
    action_container = '<div class="studio-actions">'
    action_index = text.find(action_container, header_start, header_end)
    if action_index >= 0:
        insert_at = action_index + len(action_container)
        return text[:insert_at] + action + text[insert_at:]

    block = '<div class="studio-actions">' + action + '</div>'
    return text[:header_end] + block + text[header_end:]


def patch_assignment_navigation() -> None:
    if not ASSIGNMENTS.is_file():
        raise RuntimeError("Microsoft 365 Classwork v4 requires generated Assignments & Submissions v2.")
    text = ASSIGNMENTS.read_text(encoding="utf-8")
    text = _patch_student_assignment_action(text)

    course_old = '<div class="studio-actions"><a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/courses/{course_id}/gradebook" data-i18n-en="Gradebook" data-i18n-es="Calificaciones">Gradebook</a></div></header><section class="studio-grid">{cards}</section>'
    course_new = '<div class="studio-actions"><a class="studio-button" href="{STUDIO_PREFIX}/courses/{course_id}/microsoft365/classwork">Microsoft 365 Classwork</a><a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/courses/{course_id}/gradebook" data-i18n-en="Gradebook" data-i18n-es="Calificaciones">Gradebook</a></div></header><section class="studio-grid">{cards}</section>'
    if course_old in text:
        text = text.replace(course_old, course_new, 1)

    inbox_old = '<div class="studio-actions"><a class="studio-button" href="{STUDIO_PREFIX}/courses/{course_id}/gradebook" data-i18n-en="Open Gradebook" data-i18n-es="Abrir calificaciones">Open Gradebook</a></div></header><section class="studio-grid">{content}</section>'
    inbox_new = '<div class="studio-actions"><a class="studio-button" href="{STUDIO_PREFIX}/assignments/{item_id}/microsoft365">Microsoft 365 setup</a><a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/courses/{course_id}/gradebook" data-i18n-en="Open Gradebook" data-i18n-es="Abrir calificaciones">Open Gradebook</a></div></header><section class="studio-grid">{content}</section>'
    if inbox_old in text:
        text = text.replace(inbox_old, inbox_new, 1)
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
