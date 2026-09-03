from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_consent_wizard_v7_module.py.txt")
MODULE = Path("app/microsoft365_consent_wizard_v7.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
TENANT_V5 = Path("app/microsoft365_tenant_readiness_v5.py")
TAG = "NUVEDRA_MICROSOFT365_CONSENT_WIZARD_V7"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_consent_wizard_v7 import register_microsoft365_consent_wizard_v7\n"
    if import_line not in text:
        anchor = "from app.microsoft365_education_sync_v6 import register_microsoft365_education_sync_v6\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Consent Wizard v7 requires Education Sync v6 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_consent_wizard_v7(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_education_sync_v6(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Consent Wizard v7 could not locate the v6 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_tenant_readiness_navigation() -> None:
    if not TENANT_V5.is_file():
        raise RuntimeError("Microsoft 365 Consent Wizard v7 requires generated Tenant Readiness v5.")
    text = TENANT_V5.read_text(encoding="utf-8")
    if TAG in text:
        return
    route_anchor = '@app.get("/admin/microsoft365/tenant-readiness"'
    start = text.find(route_anchor)
    if start < 0:
        raise RuntimeError("Microsoft 365 Consent Wizard v7 could not locate the Tenant Readiness v5 admin route.")
    header_end = text.find("</header>", start)
    if header_end < 0:
        raise RuntimeError("Microsoft 365 Consent Wizard v7 could not locate the Tenant Readiness v5 admin header.")
    action = '<div class="studio-actions"><a class="studio-button" href="/admin/microsoft365/consent-wizard">Consent Wizard v7</a></div><!-- NUVEDRA_MICROSOFT365_CONSENT_WIZARD_V7 -->'
    text = text[:header_end] + action + text[header_end:]
    TENANT_V5.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Consent Wizard v7 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_tenant_readiness_navigation()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(TENANT_V5.read_text(encoding="utf-8"), str(TENANT_V5), "exec")
    print("NUVEDRA Microsoft 365 Production Configuration & Consent Wizard v7 installed: Entra/Render setup inventory, tenant-specific admin consent handoff, requested-vs-effective scope diagnostics, read-only service probes, and governed write gates.", flush=True)


if __name__ == "__main__":
    main()
