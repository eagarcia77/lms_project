from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/course_copy_import_module.py.txt")
MODULE = Path("app/course_copy_import.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_COURSE_COPY_IMPORT_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.course_copy_import import register_course_copy_import\n"
    if import_line not in text:
        anchors = (
            "from app.rubrics_outcomes import register_rubrics_outcomes\n",
            "from app.assignments_submissions import register_assignments_submissions\n",
            "from app.discussions_collaboration import register_discussions_collaboration\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Course Copy & Import v1 could not locate an academic portal import anchor.")

    registration = "    register_course_copy_import(app)\n"
    if registration not in text:
        anchors = (
            "    register_rubrics_outcomes(app)\n",
            "    register_assignments_submissions(app)\n",
            "    register_discussions_collaboration(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Course Copy & Import v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_COURSE_COPY_IMPORT_V1
  function initializeCourseCopyImportLink() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!courseStudio || !courseMatch || courseStudio.querySelector('[data-course-copy-import-link]')) return;
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
    link.href = `/faculty/studio/courses/${courseMatch[1]}/copy`;
    link.dataset.courseCopyImportLink = 'v1';
    link.dataset.i18nEn = 'Copy / Import';
    link.dataset.i18nEs = 'Copiar / Importar';
    link.textContent = language() === 'es' ? 'Copiar / Importar' : 'Copy / Import';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Course Copy & Import v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeCourseCopyImportLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Course Copy & Import v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeCourseCopyImportLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Course Copy & Import v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    print("NUVEDRA Course Copy & Import v1 installed: new-course copy, selective import, draft safety, question/rubric/outcome preservation, and learner-data exclusion.", flush=True)


if __name__ == "__main__":
    main()
