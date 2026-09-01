from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/accessibility_checker_module.py.txt")
MODULE = Path("app/accessibility_checker.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
COURSE_EDITOR = Path("app/course_editor_access.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_ACCESSIBILITY_CHECKER_V1"


def _insert_after(text: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"Accessibility Checker v1 could not find {label}: {anchor[:180]!r}")
    return text.replace(anchor, anchor + addition, 1)


def _insert_before(text: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"Accessibility Checker v1 could not find {label}: {anchor[:180]!r}")
    return text.replace(anchor, addition + anchor, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    if "from app.accessibility_checker import register_accessibility_checker" not in text:
        if "from app.content_library import register_content_library\n" in text:
            text = _insert_after(
                text,
                "from app.content_library import register_content_library\n",
                "from app.accessibility_checker import register_accessibility_checker\n",
                "Content Library import",
            )
        else:
            marker = "\n\ndef register_academic_portal(app: FastAPI) -> None:\n"
            text = _insert_before(
                text,
                marker,
                "from app.accessibility_checker import register_accessibility_checker\n",
                "academic portal registration function",
            )

    if "register_accessibility_checker(app)" not in text:
        if "    register_content_library(app)\n" in text:
            text = _insert_after(
                text,
                "    register_content_library(app)\n",
                "    register_accessibility_checker(app)\n",
                "Content Library registration",
            )
        else:
            marker = "    print("
            text = _insert_before(
                text,
                marker,
                "    register_accessibility_checker(app)\n",
                "academic portal status print",
            )

    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_course_editor() -> None:
    text = COURSE_EDITOR.read_text(encoding="utf-8")
    if "import app.accessibility_checker as accessibility_checker" not in text:
        if "import app.academic_access as academic_access\n" in text:
            text = _insert_after(
                text,
                "import app.academic_access as academic_access\n",
                "import app.accessibility_checker as accessibility_checker\n",
                "academic access import",
            )
        else:
            text = _insert_after(
                text,
                "from fastapi.responses import HTMLResponse, RedirectResponse\n",
                "\nimport app.accessibility_checker as accessibility_checker\n",
                "FastAPI response import",
            )

    if "NUVEDRA_ACCESSIBILITY_CHECKER_V1 publication gate" not in text:
        anchor = '            metadata["assessment"] = {"response_type": assessment_response_type, "attempts": max(1, attempts), "time_limit": max(0, time_limit), "rubric": rubric.strip()} if item_type == "assessment" else {}\n'
        block = '''            # NUVEDRA_ACCESSIBILITY_CHECKER_V1 publication gate
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
        text = _insert_after(text, anchor, block, "item assessment metadata update")

    if "accessibility_checker.check_item_row(item)" not in text:
        anchor = '            next_state = "draft" if str(item.get("status")) == "published" else "published"\n'
        block = '''            if next_state == "published":
                accessibility_report = accessibility_checker.check_item_row(item)
                if accessibility_report["blocking"]:
                    raise HTTPException(
                        409,
                        "Accessibility check failed before publication: "
                        + accessibility_checker.blocking_summary(accessibility_report),
                    )
'''
        text = _insert_after(text, anchor, block, "quick publish state change")

    COURSE_EDITOR.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
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
            raise RuntimeError("Accessibility Checker v1 could not locate Course Studio start().")
        text = text.replace(marker, functions + marker, 1)

    if "    initializeAccessibilityCheckerLinks();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Accessibility Checker v1 could not locate Course Studio initialization.")
        text = text.replace(marker, "    initializeAccessibilityCheckerLinks();\n" + marker, 1)

    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Accessibility Checker v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_course_editor()
    patch_studio_js()
    print(
        "NUVEDRA Accessibility Checker v1 installed deterministically: WCAG-oriented reports and publication gates enabled.",
        flush=True,
    )


if __name__ == "__main__":
    main()
