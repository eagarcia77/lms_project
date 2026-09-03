from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_education_sync_v6_module.py.txt")
MODULE = Path("app/microsoft365_education_sync_v6.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
TENANT_V5 = Path("app/microsoft365_tenant_readiness_v5.py")
ASSIGNMENTS = Path("app/assignments_submissions.py")
TAG = "NUVEDRA_MICROSOFT365_EDUCATION_SYNC_V6"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_education_sync_v6 import register_microsoft365_education_sync_v6\n"
    if import_line not in text:
        anchor = "from app.microsoft365_tenant_readiness_v5 import register_microsoft365_tenant_readiness_v5\n"
        if anchor not in text:
            raise RuntimeError("Microsoft Education Sync v6 requires Tenant Readiness v5 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_education_sync_v6(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_tenant_readiness_v5(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft Education Sync v6 could not locate the v5 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_v5_navigation() -> None:
    if not TENANT_V5.is_file():
        raise RuntimeError("Microsoft Education Sync v6 requires generated Tenant Readiness v5.")
    text = TENANT_V5.read_text(encoding="utf-8")
    if TAG in text:
        return
    anchor = 'Read-only Microsoft Education readiness'
    if anchor not in text:
        raise RuntimeError("Microsoft Education Sync v6 could not locate the Tenant Readiness v5 course heading anchor.")
    # Add navigation only to the detailed course readiness page; v6 continues to rely on v5 for class linkage.
    hero = 'Link one of your own taught Microsoft education classes to this NUVEDRA course and inspect assignment metadata without writing to Microsoft Education.'</p></div></header>'
    if hero in text:
        replacement = 'Link one of your own taught Microsoft education classes to this NUVEDRA course and inspect assignment metadata without writing to Microsoft Education.</p></div><div class="studio-actions"><a class="studio-button" href="{STUDIO_PREFIX}/courses/{course_id}/microsoft365/education-sync">Education Sync v6</a></div></header><!-- NUVEDRA_MICROSOFT365_EDUCATION_SYNC_V6 -->'
        text = text.replace(hero, replacement, 1)
    else:
        # Fallback for small wording changes in the generated v5 template.
        marker = 'data-testid="microsoft365-education-readiness-v5"'
        if marker not in text:
            raise RuntimeError("Microsoft Education Sync v6 could not locate the v5 Education Readiness page.")
        text = text.replace(marker, marker + ' data-education-sync-v6="available"', 1)
    TENANT_V5.write_text(text, encoding="utf-8")


def patch_assignment_navigation() -> None:
    if not ASSIGNMENTS.is_file():
        raise RuntimeError("Microsoft Education Sync v6 requires generated Assignments & Submissions v2.")
    text = ASSIGNMENTS.read_text(encoding="utf-8")
    inbox_anchor = '<a class="studio-button" href="{STUDIO_PREFIX}/assignments/{item_id}/microsoft365">Microsoft 365 setup</a>'
    if inbox_anchor in text and "Microsoft Education sync" not in text:
        text = text.replace(inbox_anchor, inbox_anchor + '<a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/assignments/{item_id}/microsoft365/education-sync">Microsoft Education sync</a>', 1)
    ASSIGNMENTS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft Education Sync v6 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_v5_navigation()
    patch_assignment_navigation()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(TENANT_V5.read_text(encoding="utf-8"), str(TENANT_V5), "exec")
    compile(ASSIGNMENTS.read_text(encoding="utf-8"), str(ASSIGNMENTS), "exec")
    print("NUVEDRA Microsoft Education Assignments & Grade Integration v6 installed: explicit policy-gated assignment export/publish, canonical NUVEDRA grade export, Microsoft outcome synchronization, optional grade return, and audit history.", flush=True)


if __name__ == "__main__":
    main()
