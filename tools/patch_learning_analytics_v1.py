from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/learning_analytics_module.py.txt")
MODULE = Path("app/learning_analytics.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_LEARNING_ANALYTICS_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.learning_analytics import register_learning_analytics\n"
    if import_line not in text:
        anchors = (
            "from app.accessibility_checker import register_accessibility_checker\n",
            "from app.content_library import register_content_library\n",
            "from app.student_experience import register_student_experience\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Learning Analytics v1 could not locate an academic portal import anchor.")

    registration = "    register_learning_analytics(app)\n"
    if registration not in text:
        anchors = (
            "    register_accessibility_checker(app)\n",
            "    register_content_library(app)\n",
            "    register_student_experience(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Learning Analytics v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_LEARNING_ANALYTICS_V1
  function initializeLearningAnalyticsLink() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!courseStudio || !courseMatch || courseStudio.querySelector('[data-learning-analytics-link]')) return;
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
    link.href = `/faculty/studio/courses/${courseMatch[1]}/analytics`;
    link.dataset.learningAnalyticsLink = 'v1';
    link.dataset.i18nEn = 'Learning Analytics';
    link.dataset.i18nEs = 'Analítica de aprendizaje';
    link.textContent = language() === 'es' ? 'Analítica de aprendizaje' : 'Learning Analytics';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Learning Analytics v1 could not insert the Studio navigation function.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeLearningAnalyticsLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Learning Analytics v1 could not initialize its Studio navigation link.")
        text = text.replace(marker, "    initializeLearningAnalyticsLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Learning Analytics v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    print("NUVEDRA Learning Analytics v1 installed: instructor course metrics, attention indicators, overdue work, progress, grades, and CSV export.", flush=True)


if __name__ == "__main__":
    main()
