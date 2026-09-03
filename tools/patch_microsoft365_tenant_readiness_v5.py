from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_tenant_readiness_v5_module.py.txt")
MODULE = Path("app/microsoft365_tenant_readiness_v5.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
MICROSOFT365 = Path("app/microsoft365_integration.py")
PRODUCTION_V3 = Path("app/microsoft365_production_v3.py")
CLASSWORK_V4 = Path("app/microsoft365_classwork_v4.py")
TAG = "NUVEDRA_MICROSOFT365_TENANT_READINESS_V5"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_tenant_readiness_v5 import register_microsoft365_tenant_readiness_v5\n"
    if import_line not in text:
        anchor = "from app.microsoft365_classwork_v4 import register_microsoft365_classwork_v4\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Tenant Readiness v5 requires Classwork v4 in academic_portal.py.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_microsoft365_tenant_readiness_v5(app)\n"
    if registration not in text:
        anchor = "    register_microsoft365_classwork_v4(app)\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Tenant Readiness v5 could not locate the Classwork v4 registration anchor.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_microsoft_login_policy() -> None:
    if not MICROSOFT365.is_file():
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 requires generated Microsoft 365 Integration v1.")
    text = MICROSOFT365.read_text(encoding="utf-8")
    if TAG in text:
        return
    anchor = '''        cfg = _config()\n        state = secrets.token_urlsafe(32)\n'''
    replacement = '''        cfg = _config()\n        # NUVEDRA_MICROSOFT365_TENANT_READINESS_V5\n        require_institution = str(os.getenv("MICROSOFT_REQUIRE_INSTITUTION_TENANT", "")).strip().lower() in {"1", "true", "yes", "on"}\n        if require_institution and str(cfg.get("tenant") or "").strip().lower() in {"", "common", "organizations", "consumers"}:\n            raise HTTPException(503, "Microsoft institutional sign-in requires a specific MICROSOFT_TENANT_ID when MICROSOFT_REQUIRE_INSTITUTION_TENANT is enabled.")\n        state = secrets.token_urlsafe(32)\n'''
    if anchor not in text:
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 could not locate the Microsoft OAuth login policy anchor.")
    text = text.replace(anchor, replacement, 1)

    email_anchor = '''        if not email or "@" not in email:\n            raise HTTPException(400, "Microsoft account did not provide a usable email address.")\n        current = academic_access.google_user(request)\n'''
    email_replacement = '''        if not email or "@" not in email:\n            raise HTTPException(400, "Microsoft account did not provide a usable email address.")\n        allowed_domains = {part.strip().lower() for part in str(os.getenv("MICROSOFT_ALLOWED_DOMAINS", "") or "").replace(",", " ").split() if part.strip()}\n        if allowed_domains and email.rsplit("@", 1)[-1].lower() not in allowed_domains:\n            raise HTTPException(403, "This Microsoft account domain is not allowed by MICROSOFT_ALLOWED_DOMAINS.")\n        current = academic_access.google_user(request)\n'''
    if email_anchor not in text:
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 could not locate the Microsoft OAuth email policy anchor.")
    MICROSOFT365.write_text(text.replace(email_anchor, email_replacement, 1), encoding="utf-8")


def patch_navigation() -> None:
    if not PRODUCTION_V3.is_file() or not CLASSWORK_V4.is_file():
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 requires generated Production v3 and Classwork v4 modules.")
    production = PRODUCTION_V3.read_text(encoding="utf-8")
    admin_old = 'Validate the configured Entra tenant against live Microsoft Graph, inspect scopes actually returned for the connected identity, and test the least-privilege Microsoft Education read-only APIs without granting consent or changing tenant resources.'
    # The v5 module owns the detailed readiness page. Production v3 only needs a navigation action.
    prod_anchor = 'Review the actual delegated scopes returned for connected identities, run read-only Graph probes, and monitor course Team synchronization without exposing access tokens, refresh tokens, client secrets, or encryption keys.</p></div></header>'
    prod_new = 'Review the actual delegated scopes returned for connected identities, run read-only Graph probes, and monitor course Team synchronization without exposing access tokens, refresh tokens, client secrets, or encryption keys.</p></div><div class="studio-actions"><a class="studio-button" href="/admin/microsoft365/tenant-readiness">Tenant Readiness v5</a></div></header>'
    if prod_anchor in production:
        production = production.replace(prod_anchor, prod_new, 1)
    elif "Tenant Readiness v5" not in production:
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 could not locate the Production v3 admin navigation anchor.")
    PRODUCTION_V3.write_text(production, encoding="utf-8")

    classwork = CLASSWORK_V4.read_text(encoding="utf-8")
    class_anchor = 'Attach Word, Excel, PowerPoint, PDF, or other OneDrive/SharePoint files to NUVEDRA assignments and collect validated Microsoft 365 work links while keeping NUVEDRA Gradebook canonical.</p></div></header>'
    class_new = 'Attach Word, Excel, PowerPoint, PDF, or other OneDrive/SharePoint files to NUVEDRA assignments and collect validated Microsoft 365 work links while keeping NUVEDRA Gradebook canonical.</p></div><div class="studio-actions"><a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/courses/{course_id}/microsoft365/education-readiness">Education Readiness v5</a></div></header>'
    if class_anchor in classwork:
        classwork = classwork.replace(class_anchor, class_new, 1)
    elif "Education Readiness v5" not in classwork:
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 could not locate the Classwork v4 navigation anchor.")
    CLASSWORK_V4.write_text(classwork, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Tenant Readiness v5 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_microsoft_login_policy()
    patch_navigation()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(MICROSOFT365.read_text(encoding="utf-8"), str(MICROSOFT365), "exec")
    compile(PRODUCTION_V3.read_text(encoding="utf-8"), str(PRODUCTION_V3), "exec")
    compile(CLASSWORK_V4.read_text(encoding="utf-8"), str(CLASSWORK_V4), "exec")
    print("NUVEDRA Microsoft 365 Live Tenant Readiness & Education v5 installed: institution-tenant enforcement, optional domain allowlist, live tenant readiness diagnostics, effective scope evidence, and read-only Microsoft Education class linkage.", flush=True)


if __name__ == "__main__":
    main()
