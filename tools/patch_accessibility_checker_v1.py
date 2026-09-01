from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/accessibility_checker_module.py.txt")
MODULE = Path("app/accessibility_checker.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
COURSE_EDITOR = Path("app/course_editor_access.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_ACCESSIBILITY_CHECKER_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Accessibility Checker v1 patch could not find {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.content_library import register_content_library\n",
        "from app.content_library import register_content_library\nfrom app.accessibility_checker import register_accessibility_checker\n",
        "Accessibility Checker import",
    )
    text = replace_once(
        text,
        '    register_content_library(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2, Gradebook v2, Student Experience v2 y Content Library v1.", flush=True)\n',
        '    register_content_library(app)\n    register_accessibility_checker(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2, Gradebook v2, Student Experience v2, Content Library v1 y Accessibility Checker v1.", flush=True)\n',
        "Accessibility Checker registration",
    )
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_course_editor() -> None:
    text = COURSE_EDITOR.read_text(encoding="utf-8")
    if "import app.accessibility_checker as accessibility_checker" not in text:
        text = replace_once(
            text,
            "import app.academic_access as academic_access\n",
            "import app.academic_access as academic_access\nimport app.accessibility_checker as accessibility_checker\n",
            "Course Studio accessibility import",
        )

    update_marker = '            metadata["assessment"] = {"response_type": assessment_response_type, "attempts": max(1, attempts), "time_limit": max(0, time_limit), "rubric": rubric.strip()} if item_type == "assessment" else {}\n'
    update_block = '''            metadata["assessment"] = {"response_type": assessment_response_type, "attempts": max(1, attempts), "time_limit": max(0, time_limit), "rubric": rubric.strip()} if item_type == "assessment" else {}
            # NUVEDRA_ACCESSIBILITY_CHECKER_V1 publication gate
            if status == "published":
                accessibility_report = accessibility_checker.check_item_payload(
                    item_type=item_type,
                    title=title.strip(),
                    body_html=body_html,
                    external_url=external_url,
                    embed_url=embed_url,
                    metadata=metadata,
                )
                if accessibility_report["blocking"]:
                    raise HTTPException(
                        409,
                        "Accessibility check failed before publication: "
                        + accessibility_checker.blocking_summary(accessibility_report),
                    )
'''
    if "NUVEDRA_ACCESSIBILITY_CHECKER_V1 publication gate" not in text:
        text = replace_once(text, update_marker, update_block, "item edit publication gate")

    toggle_marker = '            next_state = "draft" if str(item.get("status")) == "published" else "published"\n'
    toggle_block = '''            next_state = "draft" if str(item.get("status")) == "published" else "published"
            if next_state == "published":
                accessibility_report = accessibility_checker.check_item_row(item)
                if accessibility_report["blocking"]:
                    raise HTTPException(
                        409,
                        "Accessibility check failed before publication: "
                        + accessibility_checker.blocking_summary(accessibility_report),
                    )
'''
    if 'accessibility_checker.check_item_row(item)' not in text:
        text = replace_once(text, toggle_marker, toggle_block, "quick publish accessibility gate")

    COURSE_EDITOR.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG in text:
        return
    functions = r'''
  // NUVEDRA_ACCESSIBILITY_CHECKER_V1
  function initializeAccessibilityCheckerLinks() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (courseStudio && courseMatch && !courseStudio.querySelector('[data-accessibility-link="course"]')) {
      const hero = courseStudio.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) {
          actions = document.createElement('div');
          actions.className = 'studio-actions';
          hero.appendChild(actions);
        }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/faculty/studio/courses/${courseMatch[1]}/accessibility`;
        link.dataset.accessibilityLink = 'course';
        link.dataset.i18nEn = 'Accessibility Check';
        link.dataset.i18nEs = 'Verificar accesibilidad';
        link.textContent = language() === 'es' ? 'Verificar accesibilidad' : 'Accessibility Check';
        actions.appendChild(link);
      }
    }

    const itemEditor = document.querySelector('[data-testid="visual-item-editor"]');
    const itemMatch = window.location.pathname.match(/^\/faculty\/studio\/items\/(\d+)\/edit$/);
    if (itemEditor && itemMatch && !itemEditor.querySelector('[data-accessibility-link="item"]')) {
      const hero = itemEditor.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) {
          actions = document.createElement('div');
          actions.className = 'studio-actions';
          hero.appendChild(actions);
        }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/faculty/studio/items/${itemMatch[1]}/accessibility`;
        link.dataset.accessibilityLink = 'item';
        link.dataset.i18nEn = 'Accessibility Check';
        link.dataset.i18nEs = 'Verificar accesibilidad';
        link.textContent = language() === 'es' ? 'Verificar accesibilidad' : 'Accessibility Check';
        actions.appendChild(link);
      }
    }
  }

'''
    marker = "  function start() {\n"
    if marker not in text:
        raise RuntimeError("Accessibility Checker v1 could not insert Studio navigation links.")
    text = text.replace(marker, functions + marker, 1)
    init_old = "    initializeContentLibraryLink();\n    initializeDrafts();\n"
    init_new = "    initializeContentLibraryLink();\n    initializeAccessibilityCheckerLinks();\n    initializeDrafts();\n"
    text = replace_once(text, init_old, init_new, "Accessibility Checker Studio initialization")
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Accessibility Checker v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_course_editor()
    patch_studio_js()
    print("NUVEDRA Accessibility Checker v1 installed: automated WCAG-oriented checks, Studio reports, and pre-publication blocking.", flush=True)


if __name__ == "__main__":
    main()
