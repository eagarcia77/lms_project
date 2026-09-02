from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/microsoft365_integration_module.py.txt")
MODULE = Path("app/microsoft365_integration.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
GOOGLE_HUB = Path("app/google_hub_safe.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_MICROSOFT365_INTEGRATION_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.microsoft365_integration import register_microsoft365_integration\n"
    if import_line not in text:
        anchors = (
            "from app.external_accreditation_review_portal import register_external_accreditation_review_portal\n",
            "from app.accreditation_standards_crosswalk import register_accreditation_standards_crosswalk\n",
            "from app.google_hub_safe import register_portal_home_and_google\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Microsoft 365 Integration v1 could not locate an academic portal import anchor.")
    registration = "    register_microsoft365_integration(app)\n"
    if registration not in text:
        anchors = (
            "    register_external_accreditation_review_portal(app)\n",
            "    register_accreditation_standards_crosswalk(app)\n",
            "    register_portal_home_and_google(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Microsoft 365 Integration v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_portal_login_choices() -> None:
    text = GOOGLE_HUB.read_text(encoding="utf-8")
    marker = "NUVEDRA_MICROSOFT365_INTEGRATION_V1_LOGIN"
    if marker in text:
        return
    old = '''            body = \'\'\'<section class="card" style="max-width:680px;margin:auto"><h2>Acceso para profesores y estudiantes</h2><p>Utilice su cuenta institucional de Google. NUVEDRA mostrará únicamente los cursos y las funciones asignadas por el administrador.</p><a class="button" href="/portal/login">Continuar con Google</a></section>\'\'\'\n'''
    new = '''            # NUVEDRA_MICROSOFT365_INTEGRATION_V1_LOGIN\n            body = \'\'\'<section class="card" style="max-width:720px;margin:auto"><h2>Acceso para profesores y estudiantes</h2><p>Utilice su cuenta institucional. NUVEDRA mostrará únicamente los cursos y funciones asignados por el administrador.</p><a class="button" href="/portal/login">Continuar con Google</a><a class="button secondary" href="/portal/microsoft-connect">Continuar con Microsoft 365</a><p class="muted">Google y Microsoft 365 son opciones de identidad independientes; la institución puede habilitar una o ambas.</p></section>\'\'\'\n'''
    if old not in text:
        raise RuntimeError("Microsoft 365 Integration v1 could not locate the academic portal sign-in card.")
    GOOGLE_HUB.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_studio_link() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_MICROSOFT365_INTEGRATION_V1
  function initializeMicrosoft365Link() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!courseStudio || !courseMatch || courseStudio.querySelector('[data-microsoft365-link]')) return;
    const hero = courseStudio.querySelector('.studio-hero');
    if (!hero) return;
    let actions = hero.querySelector('.studio-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'studio-actions';
      hero.appendChild(actions);
    }
    const link = document.createElement('a');
    link.className = 'studio-button studio-button--quiet';
    link.href = `/faculty/studio/courses/${courseMatch[1]}/microsoft365`;
    link.dataset.microsoft365Link = 'v1';
    link.dataset.i18nEn = 'Microsoft 365';
    link.dataset.i18nEs = 'Microsoft 365';
    link.textContent = 'Microsoft 365';
    actions.appendChild(link);
  }

'''
        anchor = "  function start() {\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Integration v1 could not insert Course Studio navigation.")
        text = text.replace(anchor, block + anchor, 1)
    if "    initializeMicrosoft365Link();\n" not in text:
        anchor = "    initializeDrafts();\n"
        if anchor not in text:
            raise RuntimeError("Microsoft 365 Integration v1 could not initialize Course Studio navigation.")
        text = text.replace(anchor, "    initializeMicrosoft365Link();\n" + anchor, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Microsoft 365 Integration v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_portal_login_choices()
    patch_studio_link()
    compile(ACADEMIC_PORTAL.read_text(encoding="utf-8"), str(ACADEMIC_PORTAL), "exec")
    compile(GOOGLE_HUB.read_text(encoding="utf-8"), str(GOOGLE_HUB), "exec")
    print("NUVEDRA Microsoft 365 Integration v1 installed: Entra ID sign-in/connect, encrypted Microsoft Graph tokens, OneDrive, SharePoint, Content Library links, Teams-enabled Outlook events, and Course Studio navigation.", flush=True)


if __name__ == "__main__":
    main()
