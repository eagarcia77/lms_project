from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_go_live_governance_v8_module.py.txt")
MODULE = Path("app/microsoft365_go_live_governance_v8.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
CONSENT_V7 = Path("app/microsoft365_consent_wizard_v7.py")
EDUCATION_V6 = Path("app/microsoft365_education_sync_v6.py")
PRODUCTION_V3 = Path("app/microsoft365_production_v3.py")
TAG = "NUVEDRA_MICROSOFT365_GO_LIVE_GOVERNANCE_V8"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_go_live_governance_v8 import register_microsoft365_go_live_governance_v8\n"
    if import_line not in text:
        anchor = "from app.microsoft365_consent_wizard_v7 import register_microsoft365_consent_wizard_v7\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Go-Live Governance v8 requires Consent Wizard v7 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_go_live_governance_v8(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_consent_wizard_v7(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Go-Live Governance v8 could not locate the v7 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_consent_navigation() -> None:
    if not CONSENT_V7.is_file():
        raise RuntimeError("Microsoft 365 Go-Live Governance v8 requires generated Consent Wizard v7.")
    text = CONSENT_V7.read_text(encoding="utf-8")
    if TAG in text:
        return
    route_anchor = '@app.get("/admin/microsoft365/consent-wizard"'
    start = text.find(route_anchor)
    if start < 0:
        raise RuntimeError("Microsoft 365 Go-Live Governance v8 could not locate the Consent Wizard v7 route.")
    header_end = text.find("</header>", start)
    if header_end < 0:
        raise RuntimeError("Microsoft 365 Go-Live Governance v8 could not locate the Consent Wizard v7 header.")
    action = '<div class="studio-actions"><a class="studio-button" href="/admin/microsoft365/go-live">Go-Live Governance v8</a></div><!-- NUVEDRA_MICROSOFT365_GO_LIVE_GOVERNANCE_V8 -->'
    text = text[:header_end] + action + text[header_end:]
    CONSENT_V7.write_text(text, encoding="utf-8")


def patch_education_write_gates() -> None:
    if not EDUCATION_V6.is_file():
        raise RuntimeError("Microsoft 365 Go-Live Governance v8 requires generated Education Sync v6.")
    text = EDUCATION_V6.read_text(encoding="utf-8")
    import_line = "import app.microsoft365_go_live_governance_v8 as go_live\n"
    if import_line not in text:
        anchor = "import app.microsoft365_tenant_readiness_v5 as readiness\n"
        if anchor not in text:
            raise RuntimeError("Go-Live v8 could not locate the Education Sync v6 import anchor.")
        text = text.replace(anchor, anchor + import_line, 1)

    assignment_anchor = '            academic_access.require_course_role(conn, course_id, user["email"], academic_access.AUTHOR_ROLES)\n            _require_assignment_write(conn, user["email"])\n'
    assignment_replacement = '            academic_access.require_course_role(conn, course_id, user["email"], academic_access.AUTHOR_ROLES)\n            go_live.require_course_write_access(conn, course_id, "education_assignment")\n            _require_assignment_write(conn, user["email"])\n'
    if assignment_replacement not in text:
        count = text.count(assignment_anchor)
        if count < 2:
            raise RuntimeError(f"Go-Live v8 expected at least two Education assignment write anchors, found {count}.")
        text = text.replace(assignment_anchor, assignment_replacement)

    grade_anchor = '            academic_access.require_course_role(conn, course_id, user["email"], academic_access.AUTHOR_ROLES)\n            _require_grade_write(conn, user["email"])\n'
    grade_replacement = '            academic_access.require_course_role(conn, course_id, user["email"], academic_access.AUTHOR_ROLES)\n            go_live.require_course_write_access(conn, course_id, "education_grade_export")\n            _require_grade_write(conn, user["email"])\n'
    if grade_replacement not in text:
        if grade_anchor not in text:
            raise RuntimeError("Go-Live v8 could not locate the Education grade-export write anchor.")
        text = text.replace(grade_anchor, grade_replacement, 1)
    EDUCATION_V6.write_text(text, encoding="utf-8")


def patch_team_creation_gate() -> None:
    if not PRODUCTION_V3.is_file():
        raise RuntimeError("Microsoft 365 Go-Live Governance v8 requires generated Production v3.")
    text = PRODUCTION_V3.read_text(encoding="utf-8")
    import_line = "import app.microsoft365_go_live_governance_v8 as go_live\n"
    if import_line not in text:
        anchor = "import app.microsoft365_integration as m365\n"
        if anchor not in text:
            raise RuntimeError("Go-Live v8 could not locate the Production v3 import anchor.")
        text = text.replace(anchor, anchor + import_line, 1)
    route_anchor = '@app.post(f"{STUDIO_PREFIX}/courses/{course_id}/microsoft365/production/team", response_model=None)'
    start = text.find(route_anchor)
    if start < 0:
        raise RuntimeError("Go-Live v8 could not locate the controlled Team creation route.")
    role_anchor = '            course = academic_access.require_course_role(conn, course_id, user["email"], academic_access.AUTHOR_ROLES)\n'
    role_index = text.find(role_anchor, start)
    if role_index < 0:
        raise RuntimeError("Go-Live v8 could not locate Team creation course authorization.")
    gate = '            go_live.require_course_write_access(conn, course_id, "team_creation")\n'
    insert_at = role_index + len(role_anchor)
    if gate not in text[start:start + 3000]:
        text = text[:insert_at] + gate + text[insert_at:]
    PRODUCTION_V3.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Go-Live Governance v8 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_consent_navigation()
    patch_education_write_gates()
    patch_team_creation_gate()
    for path in (ACADEMIC_PORTAL, CONSENT_V7, EDUCATION_V6, PRODUCTION_V3):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("NUVEDRA Microsoft 365 Go-Live Governance & Pilot v8 installed: read-only default, controlled pilot allowlist, validated production promotion, and rollout gates for Team creation plus Microsoft Education assignment/grade writes.", flush=True)


if __name__ == "__main__":
    main()
